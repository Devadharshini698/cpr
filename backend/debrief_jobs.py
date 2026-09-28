"""Durable MySQL jobs with immutable inputs, bounded retries and lease recovery."""
import asyncio
import json
import logging
import uuid

import aiomysql
from debriefing import __version__
from debriefing.engine import DebriefEngine, _hash, rule_fingerprint, report_fingerprint
from debriefing.contracts import RULE_SET, Session

logger = logging.getLogger(__name__)


class JobStore:
    def __init__(self, pool): self.pool = pool

    async def initialize(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""CREATE TABLE IF NOT EXISTS debrief_jobs (
                    job_id VARCHAR(64) PRIMARY KEY, session_code VARCHAR(100) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'queued', input_json LONGTEXT NOT NULL,
                    result_json LONGTEXT, error_message TEXT, attempts INT NOT NULL DEFAULT 0,
                    lease_token VARCHAR(40), lease_until DATETIME, superseded_by VARCHAR(64),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX debrief_job_session (session_code, created_at), INDEX debrief_job_status (status, lease_until)
                )""")
                await cur.execute("SHOW COLUMNS FROM debrief_jobs LIKE 'superseded_by'")
                if not await cur.fetchone():
                    await cur.execute(
                        "ALTER TABLE debrief_jobs ADD COLUMN superseded_by VARCHAR(64) NULL AFTER lease_until"
                    )
            await conn.commit()

    async def enqueue(self, session):
        data = Session.model_validate(session).model_dump(mode="json")
        job_id = _hash([__version__, RULE_SET, rule_fingerprint(), report_fingerprint(), data])
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""INSERT IGNORE INTO debrief_jobs (job_id, session_code, input_json)
                    VALUES (%s, %s, %s)""", (job_id, data["session_id"], json.dumps(data)))
                created = cur.rowcount == 1
                if created:
                    # A later transcript-bearing snapshot is authoritative for
                    # its session.  Earlier jobs must never overwrite it if
                    # they finish after audio transcription.
                    await cur.execute("""UPDATE debrief_jobs
                        SET superseded_by=%s,
                            status=CASE WHEN status IN ('queued', 'running') THEN 'superseded' ELSE status END,
                            lease_until=NULL, updated_at=UTC_TIMESTAMP()
                        WHERE session_code=%s AND job_id<>%s AND superseded_by IS NULL""",
                        (job_id, data["session_id"], job_id))
                # An explicit retry request revives failed work; completed/running work is idempotent.
                await cur.execute("""UPDATE debrief_jobs SET status='queued', attempts=0, error_message=NULL,
                    updated_at=UTC_TIMESTAMP() WHERE job_id=%s AND status='failed'""", (job_id,))
                await cur.execute("SELECT job_id, status FROM debrief_jobs WHERE job_id=%s", (job_id,))
                result = await cur.fetchone()
            await conn.commit()
        return result

    async def latest(self, session_code):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""SELECT * FROM debrief_jobs WHERE session_code=%s AND superseded_by IS NULL
                    ORDER BY created_at DESC, updated_at DESC, job_id DESC LIMIT 1""", (session_code,))
                return await cur.fetchone()

    async def claim(self):
        token = uuid.uuid4().hex
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # Recovered jobs are retried at most three times, including process crashes.
                await cur.execute("""UPDATE debrief_jobs SET status='failed', error_message='Worker lease expired after three attempts',
                    updated_at=UTC_TIMESTAMP() WHERE status='running' AND lease_until < UTC_TIMESTAMP() AND attempts>=3""")
                await cur.execute("""SELECT job_id FROM debrief_jobs WHERE superseded_by IS NULL AND attempts<3 AND
                    (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP()))
                    ORDER BY created_at LIMIT 1""")
                row = await cur.fetchone()
                if not row:
                    await conn.commit()
                    return None
                await cur.execute("""UPDATE debrief_jobs SET status='running', attempts=attempts+1,
                    lease_token=%s, lease_until=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 2 MINUTE), updated_at=UTC_TIMESTAMP()
                    WHERE job_id=%s AND superseded_by IS NULL AND attempts<3 AND
                    (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP()))""", (token, row["job_id"]))
                if cur.rowcount != 1:
                    await conn.commit()
                    return None
                await cur.execute("SELECT * FROM debrief_jobs WHERE job_id=%s", (row["job_id"],))
                job = await cur.fetchone()
            await conn.commit()
        return job

    async def renew(self, job):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""UPDATE debrief_jobs SET lease_until=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 2 MINUTE)
                    WHERE job_id=%s AND lease_token=%s AND status='running' AND superseded_by IS NULL""", (job["job_id"], job["lease_token"]))
                owned = cur.rowcount == 1
            await conn.commit()
        return owned

    async def complete(self, job, result):
        """Mark the job row as completed, then persist the report via save_debrief_report_async.

        Using save_debrief_report_async (from database.py) rather than an inline
        subquery INSERT guarantees that:
          • the sessions FK lookup uses the same fallback logic as the rest of the
            codebase (creates an orphan sessions row if the session has already been
            deleted rather than leaving session_id NULL),
          • the ON DUPLICATE KEY UPDATE is keyed on the UNIQUE session_code column
            (already present in the schema), not on the surrogate PK.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.begin()
                async with conn.cursor() as cur:
                    await cur.execute(
                        """UPDATE debrief_jobs SET status='completed', result_json=%s,
                        error_message=NULL, lease_until=NULL, updated_at=UTC_TIMESTAMP()
                        WHERE job_id=%s AND lease_token=%s AND status='running' AND superseded_by IS NULL""",
                        (json.dumps(result), job["job_id"], job["lease_token"]),
                    )
                    if cur.rowcount != 1:
                        await conn.rollback()
                        return False
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

        # Persist the report using the canonical helper that handles the sessions FK
        # lookup with a fallback, matching the existing codebase behaviour.
        from database import save_debrief_report_async
        report_payload = {
            **result,
            "session_code": job["session_code"],
            "status": "COMPLETED",
        }
        await save_debrief_report_async(report_payload)
        return True

    async def fail(self, job, error):
        status = "failed" if job["attempts"] >= 3 else "queued"
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """UPDATE debrief_jobs SET status=%s, error_message=%s, lease_until=NULL,
                    updated_at=UTC_TIMESTAMP() WHERE job_id=%s AND lease_token=%s AND status='running' AND superseded_by IS NULL""",
                    (status, str(error)[:2000], job["job_id"], job["lease_token"]),
                )
            await conn.commit()


async def run_one(store, engine=None):
    job = await store.claim()
    if not job:
        return False
    engine = engine or DebriefEngine()

    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            if not await store.renew(job):
                return

    task = asyncio.create_task(heartbeat())
    completed = False
    try:
        result = await asyncio.to_thread(engine.generate, json.loads(job["input_json"]))
        completed = await store.complete(job, result)

        if completed:
            # Fix 5 — push a debrief_completed event so the frontend can stop
            # polling immediately instead of waiting up to 2.5 s for the next tick.
            try:
                from socket_manager import sio
                await sio.emit(
                    "debrief_completed",
                    {
                        "session_code": job["session_code"],
                        "overall_score": result.get("overall_score"),
                        "grade": result.get("grade"),
                        "score_status": result.get("score_status", "not_assessed"),
                    },
                    room=job["session_code"],
                )
            except Exception as ws_exc:
                # A failed emit must never abort the worker loop.
                logger.warning("debrief_completed emit failed for %s: %s", job["session_code"], ws_exc)

    except Exception as exc:
        logger.exception("Debrief job %s failed", job["job_id"])
        await store.fail(job, exc)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return True


async def worker_loop(store):
    while True:
        try:
            if not await run_one(store):
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Debrief worker unavailable; retrying")
            await asyncio.sleep(5)
