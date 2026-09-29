"""Durable audio transcription jobs that feed canonical debrief session logs."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

import aiomysql

from debrief_adapter import DebriefAdapter
from debrief_jobs import JobStore

logger = logging.getLogger(__name__)


class AudioDebriefJobStore:
    def __init__(self, pool):
        self.pool = pool

    async def initialize(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""CREATE TABLE IF NOT EXISTS debrief_audio_jobs (
                    job_id VARCHAR(64) PRIMARY KEY, session_code VARCHAR(100) NOT NULL,
                    audio_path VARCHAR(1000) NOT NULL, audio_source VARCHAR(20) NOT NULL,
                    language_mode VARCHAR(20), status VARCHAR(20) NOT NULL DEFAULT 'queued',
                    audio_offset_ms INT NOT NULL DEFAULT 0,
                    segment_count INT, debrief_job_id VARCHAR(64), error_message TEXT,
                    attempts INT NOT NULL DEFAULT 0, lease_token VARCHAR(40), lease_until DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX audio_job_session (session_code, created_at),
                    INDEX audio_job_status (status, lease_until)
                )""")
                await cur.execute("SHOW COLUMNS FROM debrief_audio_jobs LIKE 'audio_offset_ms'")
                if not await cur.fetchone():
                    await cur.execute(
                        "ALTER TABLE debrief_audio_jobs ADD COLUMN audio_offset_ms INT NOT NULL DEFAULT 0 AFTER language_mode"
                    )
            await conn.commit()

    async def enqueue(
        self, session_code: str, audio_path: Path, source: str,
        language_mode: str | None, audio_offset_ms: int = 0,
    ):
        job_id = uuid.uuid4().hex
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""INSERT INTO debrief_audio_jobs
                    (job_id, session_code, audio_path, audio_source, language_mode, audio_offset_ms)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                    (job_id, session_code, str(audio_path), source, language_mode, audio_offset_ms))
                await cur.execute("SELECT * FROM debrief_audio_jobs WHERE job_id=%s", (job_id,))
                row = await cur.fetchone()
            await conn.commit()
        return row

    async def latest(self, session_code: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""SELECT * FROM debrief_audio_jobs WHERE session_code=%s
                    ORDER BY created_at DESC LIMIT 1""", (session_code,))
                return await cur.fetchone()

    async def claim(self):
        token = uuid.uuid4().hex
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""UPDATE debrief_audio_jobs SET status='failed',
                    error_message='Worker lease expired after three attempts', updated_at=UTC_TIMESTAMP()
                    WHERE status='running' AND lease_until<UTC_TIMESTAMP() AND attempts>=3""")
                await cur.execute("""SELECT job_id FROM debrief_audio_jobs WHERE attempts<3 AND
                    (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP()))
                    ORDER BY created_at LIMIT 1""")
                row = await cur.fetchone()
                if not row:
                    await conn.commit()
                    return None
                await cur.execute("""UPDATE debrief_audio_jobs SET status='running', attempts=attempts+1,
                    lease_token=%s, lease_until=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 15 MINUTE),
                    updated_at=UTC_TIMESTAMP() WHERE job_id=%s AND attempts<3 AND
                    (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP()))""",
                    (token, row['job_id']))
                if cur.rowcount != 1:
                    await conn.commit()
                    return None
                await cur.execute("SELECT * FROM debrief_audio_jobs WHERE job_id=%s", (row['job_id'],))
                job = await cur.fetchone()
            await conn.commit()
        return job

    async def complete(self, job, segment_count: int, debrief_job_id: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""UPDATE debrief_audio_jobs SET status='completed', segment_count=%s,
                    debrief_job_id=%s, error_message=NULL, lease_until=NULL, updated_at=UTC_TIMESTAMP()
                    WHERE job_id=%s AND lease_token=%s AND status='running'""",
                    (segment_count, debrief_job_id, job['job_id'], job['lease_token']))
                complete = cur.rowcount == 1
                if complete:
                    await cur.execute("""UPDATE live_audio_recorders SET status='completed',
                        error_message=NULL, updated_at=UTC_TIMESTAMP() WHERE audio_job_id=%s""", (job['job_id'],))
                    await cur.execute("""UPDATE live_audio_recordings SET status='completed',
                        error_message=NULL, updated_at=UTC_TIMESTAMP() WHERE audio_job_id=%s""", (job['job_id'],))
            await conn.commit()
        return complete

    async def renew(self, job):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""UPDATE debrief_audio_jobs
                    SET lease_until=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 15 MINUTE)
                    WHERE job_id=%s AND lease_token=%s AND status='running'""",
                    (job['job_id'], job['lease_token']))
                owned = cur.rowcount == 1
            await conn.commit()
        return owned

    async def fail(self, job, error):
        status = 'failed' if job['attempts'] >= 3 else 'queued'
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""UPDATE debrief_audio_jobs SET status=%s, error_message=%s,
                    lease_until=NULL, updated_at=UTC_TIMESTAMP() WHERE job_id=%s AND lease_token=%s
                    AND status='running'""", (status, str(error)[:2000], job['job_id'], job['lease_token']))
                recorder_status = 'failed' if status == 'failed' else 'queued'
                await cur.execute("""UPDATE live_audio_recorders SET status=%s, error_message=%s,
                    updated_at=UTC_TIMESTAMP() WHERE audio_job_id=%s""",
                    (recorder_status, str(error)[:2000], job['job_id']))
                await cur.execute("""UPDATE live_audio_recordings SET status=%s, error_message=%s,
                    updated_at=UTC_TIMESTAMP() WHERE audio_job_id=%s""",
                    (recorder_status, str(error)[:2000], job['job_id']))
            await conn.commit()


def _log_entries(job, segments: list[dict]) -> list[dict]:
    source = 'lapel_audio' if job['audio_source'] == 'lapel' else 'ceiling_audio'
    offset_ms = max(0, int(job.get('audio_offset_ms') or 0))
    return [{
        'segment_id': f"audio_{job['job_id']}_{index}",
        'timestamp_ms': offset_ms + int(segment.get('timestamp_ms', 0)),
        'end_ms': offset_ms + int(segment.get('end_ms', segment.get('timestamp_ms', 0))),
        'event': str(segment.get('text', '')),
        'speaker_label': str(segment.get('speaker_label', segment.get('speaker', 'unknown'))),
        'speaker_name': segment.get('speaker_name') or None,
        'actor_role': str(segment.get('role', 'unknown')),
        'role_evidence': str(segment.get('role_evidence', 'inferred')),
        'source': source,
        'confidence': float(segment.get('confidence', 0.0)),
        'audio_job_id': job['job_id'],
        'audio_offset_ms': offset_ms,
        'diarization_status': segment.get('diarization_status', 'unknown'),
    } for index, segment in enumerate(segments) if str(segment.get('text', '')).strip()]


async def run_one(store: AudioDebriefJobStore):
    job = await store.claim()
    if not job:
        return False
    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            if not await store.renew(job):
                return
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        path = Path(job['audio_path']).resolve()
        if not path.is_file():
            raise FileNotFoundError('Uploaded audio file is no longer available.')
        # Loading model weights can take tens of seconds. Keep construction as
        # well as inference off the ASGI event loop so status/report requests
        # and lease heartbeats remain responsive while audio is processing.
        def process_audio():
            from debriefing.ingestion.audio_pipeline import AudioPipeline, WHISPER_AVAILABLE
            if not WHISPER_AVAILABLE:
                raise RuntimeError('Audio transcription is unavailable: install the audio dependency extra (faster-whisper).')
            pipeline = AudioPipeline()
            return pipeline.process(str(path), session_id=job['session_code'], language_mode=job.get('language_mode'))
        segments = await asyncio.to_thread(process_audio)
        if not await store.renew(job):
            return True  # A recovered worker owns this job; discard stale output.
        entries = _log_entries(job, segments)
        if not entries:
            raise RuntimeError('No intelligible speech was detected in the uploaded audio.')

        async with store.pool.acquire() as conn:
            await conn.begin()
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT lease_token,status FROM debrief_audio_jobs WHERE job_id=%s FOR UPDATE", (job['job_id'],))
                owner = await cur.fetchone()
                if not owner or owner['lease_token'] != job['lease_token'] or owner['status'] != 'running':
                    await conn.rollback()
                    return True
                await cur.execute("SELECT * FROM sessions WHERE session_code=%s FOR UPDATE", (job['session_code'],))
                session = await cur.fetchone()
                if not session:
                    raise RuntimeError('Session was deleted before audio processing completed.')
                current = session.get('event_log') or []
                if isinstance(current, str):
                    current = json.loads(current)
                # A retry replaces only this job's own segments, never simulator events or other uploads.
                current = [entry for entry in current if entry.get('audio_job_id') != job['job_id']]
                current.extend(entries)
                await cur.execute("UPDATE sessions SET event_log=%s WHERE id=%s", (json.dumps(current), session['id']))
            await conn.commit()

        canonical = DebriefAdapter().convert({**session, 'event_log': current}, event_log=current)
        debrief_job = await JobStore(store.pool).enqueue(canonical)
        if not await store.complete(job, len(entries), debrief_job['job_id']):
            return True
        from socket_manager import sio
        # Feed completed transcript lines into the instructor Timeline when it
        # is still open. They are already durable in sessions.event_log.
        for entry in entries:
            await sio.emit('session_event', entry, room=job['session_code'])
        await sio.emit('live_audio_status', {
            'session_code': job['session_code'], 'audio_job_id': job['job_id'],
            'recorder_status': 'completed', 'segment_count': len(entries),
        }, room=job['session_code'])
        await sio.emit('audio_debrief_completed', {
            'session_code': job['session_code'], 'audio_job_id': job['job_id'],
            'segment_count': len(entries), 'debrief_job_id': debrief_job['job_id'],
        }, room=job['session_code'])
    except Exception as exc:
        logger.exception('Audio debrief job %s failed', job['job_id'])
        await store.fail(job, exc)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning('Audio lease heartbeat interrupted')
    return True


async def worker_loop(store: AudioDebriefJobStore):
    while True:
        try:
            if not await run_one(store):
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Audio debrief worker unavailable; retrying')
            await asyncio.sleep(5)
