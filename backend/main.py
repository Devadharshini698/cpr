"""FastAPI app + Socket.IO mount -- main entry point."""

import random
import string
import json
import re
import secrets
import hashlib
import traceback
import asyncio
import os
import uuid
from debrief_jobs import JobStore, worker_loop
from audio_debrief_jobs import AudioDebriefJobStore, worker_loop as audio_worker_loop
from debrief_adapter import DebriefAdapter
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import socketio
import aiomysql
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_authenticated_user,
    require_instructor,
    require_student,
)
from database import (
    init_db,
    get_db_pool
)
from models import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    DEFAULT_MONITOR_STATE,
    PARAMETER_SPEC,
)
from ecg_state import ECGStateUpdate
import socket_manager as sm
from socket_manager import sio, emit_session_ended, load_scenarios_to_cache
from simman_engine.state_machine import engine, get_session_engine, stop_session_engines
from simman_engine.rhythm_intelligence import intelligence_payload

VOICE_NOTES_DIR = Path(__file__).parent / "uploads" / "voice_notes"
DEBRIEF_AUDIO_DIR = Path(__file__).parent / "uploads" / "debrief_audio"
LIVE_AUDIO_DIR = Path(__file__).parent / "uploads" / "live_audio"
SYNTHETIC_AUDIO_DIR = Path(__file__).parent / "uploads" / "synthetic_audio"
DEBRIEFING_PATH = Path(__file__).resolve().parent / "debriefing"
MAX_DEBRIEF_AUDIO_BYTES = 200 * 1024 * 1024
DEBRIEF_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}
MAX_DEBRIEF_JSON_BYTES = 2 * 1024 * 1024
SYNTHETIC_TEST_REPORT_DIR = Path(__file__).resolve().parent.parent / "output" / "synthetic_vf_test"
SYNTHETIC_TEST_REPORT_JSON = SYNTHETIC_TEST_REPORT_DIR / "synthetic_vf_report.json"
SYNTHETIC_TEST_PDF = SYNTHETIC_TEST_REPORT_DIR / "SYNTH_VF_TEST_01_3b560c34eecc6ac3753d_debrief.pdf"


def _slugify(value: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_")
    return (slug or "item")[:max_len]


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await load_scenarios_to_cache()
    await engine.start()
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT username FROM users WHERE username IN ('instructor', 'student')")
            existing_rows = await cur.fetchall()
            existing_users = {r["username"] for r in existing_rows}

            if os.getenv("ENABLE_DEMO_USERS", "false").lower() == "true" and "instructor" not in existing_users:
                await cur.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                    ("instructor", hash_password("instructor123"), "instructor", datetime.utcnow())
                )
            if os.getenv("ENABLE_DEMO_USERS", "false").lower() == "true" and "student" not in existing_users:
                await cur.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                    ("student", hash_password("student123"), "student", datetime.utcnow())
                )
            await conn.commit()

            await cur.execute("SELECT COUNT(*) as count FROM users")
            res = await cur.fetchone()
            print(f"[INIT] Users in database: {res['count']}")
    jobs = JobStore(pool)
    await jobs.initialize()
    worker = asyncio.create_task(worker_loop(jobs))
    audio_jobs = AudioDebriefJobStore(pool)
    await audio_jobs.initialize()
    audio_worker = asyncio.create_task(audio_worker_loop(audio_jobs))
    try:
        yield
    finally:
        audio_worker.cancel()
        try:
            await audio_worker
        except asyncio.CancelledError:
            pass
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        await engine.stop()
        await stop_session_engines()



# ── App Setup ─────────────────────────────────────────────────────

api_app = FastAPI(title="AI Simulation Monitor", lifespan=lifespan)

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api_app.get("/", tags=["Service status"])
async def service_status():
    """Human-friendly confirmation for users opening the backend URL directly."""
    return {
        "service": "AI Simulation Monitor API",
        "status": "running",
        "docs": "/docs",
        "debrief_audio": "enabled",
    }


# ── Auth Routes ───────────────────────────────────────────────────

@api_app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE username = %s", (body.username,))
            user = await cur.fetchone()

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username, password, or role.")

    if body.role and user["role"] != body.role:
        raise HTTPException(status_code=401, detail="Invalid username, password, or role.")

    expires_delta = timedelta(days=7) if body.remember_me else timedelta(hours=24)

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "id": user["id"],
    }, expires_delta=expires_delta)

    max_age_seconds = int(expires_delta.total_seconds())
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        max_age=max_age_seconds,
        path="/",
    )

    session_code = None
    if user["role"] == "instructor":
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT session_code FROM sessions WHERE created_by = %s AND is_active = 1", 
                    (user["id"],)
                )
                session = await cur.fetchone()
                if session:
                    session_code = session["session_code"]

    return TokenResponse(
        access_token=token,
        role=user["role"],
        user=UserResponse(id=user["id"], username=user["username"], role=user["role"]),
        session_code=session_code,
    )


@api_app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out successfully"}


@api_app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
    }


@api_app.get("/dashboard/user-data")
async def get_dashboard_user_data(user: dict = Depends(get_current_user)):
    """Fetch real dashboard statistics and user sessions scoped to the authenticated user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 1. Total simulations conducted by user
            await cur.execute("SELECT COUNT(*) AS count FROM sessions WHERE created_by = %s", (user["id"],))
            tot_row = await cur.fetchone()
            total_simulations = tot_row["count"] if tot_row else 0

            # 2. Today's sessions
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            await cur.execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE created_by = %s AND started_at >= %s",
                (user["id"], today_start)
            )
            today_row = await cur.fetchone()
            todays_sessions = today_row["count"] if today_row else 0

            # 3. Completed sessions
            await cur.execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE created_by = %s AND is_active = 0",
                (user["id"],)
            )
            comp_row = await cur.fetchone()
            completed_sessions = comp_row["count"] if comp_row else 0

            # 4. Pending debriefs (active sessions or completed without debrief)
            await cur.execute(
                """SELECT COUNT(*) AS count FROM sessions s
                   LEFT JOIN debrief_reports dr ON dr.session_code = s.session_code
                   WHERE s.created_by = %s AND (dr.id IS NULL OR dr.status != 'COMPLETED')""",
                (user["id"],)
            )
            pend_row = await cur.fetchone()
            pending_debriefs = pend_row["count"] if pend_row else 0

            # 5. Fetch recent sessions belonging to this user
            await cur.execute(
                """SELECT s.id, s.session_code, s.started_at, s.ended_at, s.is_active,
                          s.current_scenario_json, s.team_name, dr.overall_score, dr.grade, dr.status as debrief_status
                   FROM sessions s
                   LEFT JOIN debrief_reports dr ON dr.session_code = s.session_code
                   WHERE s.created_by = %s
                   ORDER BY s.started_at DESC
                   LIMIT 10""",
                (user["id"],)
            )
            session_rows = await cur.fetchall()

    recent_sessions = []
    for row in session_rows:
        spec = json.loads(row["current_scenario_json"]) if row.get("current_scenario_json") else {}
        scenario_title = spec.get("title") or spec.get("name") or "Clinical Simulation Session"
        
        # Calculate duration
        start = row.get("started_at")
        end = row.get("ended_at")
        duration_str = "In Progress"
        if start and end:
            diff_mins = max(1, int((end - start).total_seconds() / 60))
            duration_str = f"{diff_mins} Minutes"
        elif start:
            diff_mins = max(1, int((datetime.utcnow() - start).total_seconds() / 60))
            duration_str = f"{diff_mins} Mins (Running)"

        # Status string
        if row["is_active"]:
          status_str = "Active"
        elif row.get("debrief_status") == "COMPLETED":
          status_str = "Completed"
        else:
          status_str = "Pending Debrief"

        # Score string
        if row.get("overall_score") is not None:
          score_str = f"{int(row['overall_score'])}%"
        elif row["is_active"]:
          score_str = "In Progress"
        else:
          score_str = "Pending"

        date_str = start.strftime("%d %b %Y") if start else datetime.utcnow().strftime("%d %b %Y")
        patient_str = f"{row.get('team_name') or 'Resus Team'} (Code: {row['session_code']})"

        recent_sessions.append({
            "id": row["id"],
            "session_code": row["session_code"],
            "name": scenario_title,
            "date": date_str,
            "status": status_str,
            "duration": duration_str,
            "patient": patient_str,
            "score": score_str
        })

    return {
        "stats": {
            "total_simulations": total_simulations,
            "todays_sessions": todays_sessions,
            "completed_sessions": completed_sessions,
            "pending_debriefs": pending_debriefs,
        },
        "recent_sessions": recent_sessions,
    }


@api_app.post("/auth/register")
async def register(body: RegisterRequest):
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
        
    role = body.role if body.role in ("instructor", "student") else "student"
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM users WHERE username = %s", (body.username,))
            existing = await cur.fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")

            await cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                (body.username, hash_password(body.password), role, datetime.utcnow())
            )
            await conn.commit()
            
    return {"message": f"User '{body.username}' registered successfully with role '{role}'"}




@api_app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Return the current logged-in user's real profile + session stats."""
    pool = await get_db_pool()
    created_at = None
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, username, role, created_at FROM users WHERE username = %s",
                (user.get("username"),)
            )
            row = await cur.fetchone()
            if row:
                created_at = row["created_at"].isoformat() if row.get("created_at") else None

            await cur.execute("SELECT COUNT(*) AS c FROM sessions WHERE created_by = %s", (user["id"],))
            total = (await cur.fetchone())["c"]

    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "created_at": created_at,
        "total_sessions": total,
    }


@api_app.post("/auth/request-password-reset")
async def request_password_reset(body: dict):
    """Generate a real, expiring reset token. No SMTP is configured, so the
    caller (frontend) is responsible for turning this into a shareable link."""
    username = str(body.get("username", "")).strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = await cur.fetchone()
            if not row:
                # Don't reveal whether the username exists.
                return {"message": "If that username exists, a reset token was generated."}

            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            expires = datetime.utcnow() + timedelta(minutes=30)

            await cur.execute(
                "UPDATE users SET reset_token_hash = %s, reset_token_expires = %s WHERE id = %s",
                (token_hash, expires, row["id"])
            )

    return {
        "message": "If that username exists, a reset token was generated.",
        "token": token,
        "expires_in_minutes": 30,
    }


@api_app.post("/auth/reset-password")
async def reset_password(body: dict):
    token = str(body.get("token", "")).strip()
    new_password = str(body.get("new_password", ""))
    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token and new_password are required")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, reset_token_expires FROM users WHERE reset_token_hash = %s",
                (token_hash,)
            )
            row = await cur.fetchone()
            if not row or not row.get("reset_token_expires") or row["reset_token_expires"] < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Invalid or expired reset token")

            await cur.execute(
                "UPDATE users SET password_hash = %s, reset_token_hash = NULL, reset_token_expires = NULL WHERE id = %s",
                (hash_password(new_password), row["id"])
            )

    return {"message": "Password updated successfully"}


@api_app.get("/api/user/preferences")
async def get_user_preferences(user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT preferences FROM users WHERE id = %s", (user["id"],))
            row = await cur.fetchone()

    prefs = json.loads(row["preferences"]) if row and row.get("preferences") else {}
    defaults = {"audio_alarms": True, "nibp_tones": True, "auto_debrief": True}
    return {**defaults, **prefs}


@api_app.put("/api/user/preferences")
async def update_user_preferences(body: dict, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT preferences FROM users WHERE id = %s", (user["id"],))
            row = await cur.fetchone()
            existing = json.loads(row["preferences"]) if row and row.get("preferences") else {}
            merged = {**existing, **body}
            await cur.execute(
                "UPDATE users SET preferences = %s WHERE id = %s",
                (json.dumps(merged), user["id"])
            )

    defaults = {"audio_alarms": True, "nibp_tones": True, "auto_debrief": True}
    return {**defaults, **merged}


# ── Meta Routes ───────────────────────────────────────────────────

@api_app.get("/meta/parameter-spec")
async def get_parameter_spec():
    """Return parameter spec — drives every frontend control dynamically."""
    return PARAMETER_SPEC


# ── Session Routes ────────────────────────────────────────────────

def _generate_code(length=6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


@api_app.post("/session/create")
async def create_session(user: dict = Depends(require_instructor)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT session_code FROM sessions WHERE created_by = %s AND is_active = 1",
                (user["id"],)
            )
            existing = await cur.fetchone()
            if existing:
                return {
                    "session_code": existing["session_code"],
                    "message": "Existing active session returned",
                }

            code = _generate_code()
            event_log = json.dumps([{"timestamp": datetime.utcnow().isoformat(), "event": "Session created"}])
            history = json.dumps([])
            
            await cur.execute(
                """INSERT INTO sessions 
                   (session_code, created_by, started_at, is_active, event_log, history) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (code, user["id"], datetime.utcnow(), True, event_log, history)
            )
            session_id = cur.lastrowid

            state = dict(DEFAULT_MONITOR_STATE)
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = user["username"]
            
            await cur.execute(
                "INSERT INTO monitor_state (session_id, state_data) VALUES (%s, %s)",
                (session_id, json.dumps(state))
            )

    return {"session_code": code, "message": "New session created"}


@api_app.post("/session/create-audio-only")
async def create_audio_only_session(user: dict = Depends(require_instructor)):
    """Start a recording/debrief session without launching a patient simulator."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT session_code, current_scenario_json FROM sessions WHERE created_by=%s AND is_active=1",
                (user["id"],),
            )
            for active in await cur.fetchall():
                raw_spec = active.get("current_scenario_json") or "{}"
                try:
                    active_spec = json.loads(raw_spec) if isinstance(raw_spec, str) else raw_spec
                except (TypeError, ValueError):
                    active_spec = {}
                if isinstance(active_spec, dict) and active_spec.get("mode") == "audio_only":
                    return {"session_code": active["session_code"], "mode": "audio_only", "reused": True}
            code = _generate_code()
            spec = {"title": "Audio-only team debrief", "rhythm_type": "unknown", "mode": "audio_only"}
            await cur.execute(
                """INSERT INTO sessions
                   (session_code, created_by, started_at, is_active, event_log, history, current_scenario_json)
                   VALUES (%s, %s, %s, 1, %s, %s, %s)""",
                (code, user["id"], datetime.utcnow(), json.dumps([]), json.dumps([]), json.dumps(spec)),
            )
        await conn.commit()
    return {"session_code": code, "mode": "audio_only"}


@api_app.get("/session/{session_code}/state")
async def get_session_state(session_code: str, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            if not state_row:
                raise HTTPException(status_code=404, detail="Monitor state not found")

    state = json.loads(state_row["state_data"])
    state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()
    return state


@api_app.get("/session/{session_code}/info")
async def get_session_info(session_code: str, user: dict = Depends(get_current_user)):
    """Return basic session timing and status info."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, session_code, started_at, ended_at, is_active FROM sessions WHERE session_code = %s",
                (session_code,)
            )
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_code": session["session_code"],
        "started_at": session["started_at"].isoformat() if session["started_at"] else None,
        "ended_at": session["ended_at"].isoformat() if session["ended_at"] else None,
        "is_active": bool(session["is_active"]),
    }


@api_app.post("/session/student-join")
async def student_join(body: dict):
    """Anonymous or student portal access endpoint for active sessions."""
    session_code = body.get("session_code", "").strip().upper()
    if not session_code:
        raise HTTPException(status_code=400, detail="Session code is required")
        
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, is_active FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            if not session.get("is_active", True):
                raise HTTPException(status_code=400, detail="Session has ended")

    student_token = create_access_token({"sub": f"student_{uuid.uuid4().hex[:6]}", "role": "student", "session_code": session_code})
    return {"token": student_token, "session_code": session_code, "role": "student"}


@api_app.get("/session/{session_code}/log")
async def get_session_log(session_code: str, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
    event_log = json.loads(session["event_log"]) if session["event_log"] else []
    return {"event_log": event_log}


def _save_voice_note(session_code: str, scope_slug: str, audio: UploadFile, audio_bytes: bytes) -> str:
    """Persist an uploaded voice-note recording to disk and return its public URL."""
    VOICE_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".webm"
    if audio.filename and "." in audio.filename:
        candidate = "." + audio.filename.rsplit(".", 1)[-1].lower()
        if len(candidate) <= 6:
            ext = candidate
    filename = f"{_slugify(session_code)}_{scope_slug}_{int(datetime.utcnow().timestamp() * 1000)}{ext}"
    (VOICE_NOTES_DIR / filename).write_bytes(audio_bytes)
    return f"/api/voice-notes/{filename}"


@api_app.get("/api/voice-notes/{filename}")
async def get_voice_note(filename: str, user: dict = Depends(get_current_user)):
    safe_name = Path(filename).name  # strip any path traversal
    path = VOICE_NOTES_DIR / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Voice note not found")
    return FileResponse(path=str(path))


@api_app.post("/api/session/{session_code}/upload-audio", status_code=202)
async def upload_debrief_audio(
    session_code: str,
    audio: UploadFile = File(...),
    source: str = Form("ceiling"),
    language_mode: Optional[str] = Form(None),
    audio_offset_ms: int = Form(0),
    user: dict = Depends(require_instructor),
):
    """Queue a room or lapel recording for transcription and communication scoring.

    Audio is deliberately accepted only after a session ends: the resulting
    transcript is appended to the immutable simulator log and a new debrief is
    queued from that combined evidence set.
    """
    session = await _debrief_session(session_code, user, write=True)
    if session.get("is_active"):
        raise HTTPException(status_code=409, detail="End the session before uploading debrief audio")
    source = source.lower().strip()
    if source not in {"ceiling", "lapel"}:
        raise HTTPException(status_code=422, detail="source must be 'ceiling' or 'lapel'")
    if language_mode is not None:
        language_mode = language_mode.lower().strip()
        if language_mode not in {"english", "tamil", "tanglish"}:
            raise HTTPException(status_code=422, detail="language_mode must be english, tamil, tanglish, or omitted")
    if audio_offset_ms < 0:
        raise HTTPException(status_code=422, detail="audio_offset_ms must be zero or greater")
    if session.get("started_at") and session.get("ended_at"):
        duration_ms = int((session["ended_at"] - session["started_at"]).total_seconds() * 1000)
        if audio_offset_ms > duration_ms:
            raise HTTPException(status_code=422, detail="Audio start offset is outside the simulation duration")
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in DEBRIEF_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    content = await audio.read(MAX_DEBRIEF_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Audio upload is empty")
    if len(content) > MAX_DEBRIEF_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio upload exceeds the 200 MB limit")
    DEBRIEF_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{_slugify(session_code)}_{uuid.uuid4().hex}{suffix}"
    path = DEBRIEF_AUDIO_DIR / safe_name
    path.write_bytes(content)
    job = await AudioDebriefJobStore(await get_db_pool()).enqueue(
        session_code, path, source, language_mode, audio_offset_ms
    )
    return {
        "session_code": session_code,
        "audio_job_id": job["job_id"],
        "status": job["status"],
        "audio_offset_ms": audio_offset_ms,
        "message": "Audio accepted; transcription and an updated debrief are queued.",
    }


@api_app.get("/api/session/{session_code}/upload-audio/status")
async def get_debrief_audio_status(session_code: str, user: dict = Depends(get_current_user)):
    await _debrief_session(session_code, user)
    job = await AudioDebriefJobStore(await get_db_pool()).latest(session_code)
    if not job:
        raise HTTPException(status_code=404, detail="No debrief audio upload found for this session")
    return {
        "audio_job_id": job["job_id"], "status": job["status"],
        "segment_count": job.get("segment_count"), "debrief_job_id": job.get("debrief_job_id"),
        "audio_offset_ms": job.get("audio_offset_ms", 0),
        "error": job.get("error_message"),
    }


@api_app.post("/api/session/{session_code}/upload-debrief-json", status_code=202)
async def upload_debrief_json(
    session_code: str,
    input_file: UploadFile = File(...),
    user: dict = Depends(require_instructor),
):
    """Import timestamped structured evidence and queue a debrief without audio.

    The accepted JSON is either an array of events or ``{"events": [...]}``.
    Imported entries are marked ``json_input`` so replacing a test fixture never
    overwrites simulator events, uploaded audio, or manually logged actions.
    """
    session = await _debrief_session(session_code, user, write=True)
    if session.get("is_active"):
        raise HTTPException(status_code=409, detail="End the session before importing debrief JSON")
    if Path(input_file.filename or "").suffix.lower() != ".json":
        raise HTTPException(status_code=415, detail="Upload a .json file")
    raw = await input_file.read(MAX_DEBRIEF_JSON_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=422, detail="JSON input is empty")
    if len(raw) > MAX_DEBRIEF_JSON_BYTES:
        raise HTTPException(status_code=413, detail="JSON input exceeds the 2 MB limit")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc.msg if hasattr(exc, 'msg') else str(exc)}")

    entries = parsed.get("events") if isinstance(parsed, dict) else parsed
    if not isinstance(entries, list) or not entries:
        raise HTTPException(status_code=422, detail="JSON must be a non-empty event array or an object with an 'events' array")
    if len(entries) > 5000:
        raise HTTPException(status_code=422, detail="JSON contains more than 5,000 events")

    normalized = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail=f"Event {index + 1} must be an object")
        value = entry.get("timestamp_ms", entry.get("start_ms", entry.get("timestamp")))
        try:
            timestamp_ms = int(float(value))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"Event {index + 1} requires numeric timestamp_ms")
        if timestamp_ms < 0:
            raise HTTPException(status_code=422, detail=f"Event {index + 1} timestamp_ms cannot be negative")
        try:
            end_ms = int(float(entry.get("end_ms", timestamp_ms)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"Event {index + 1} has invalid end_ms")
        if end_ms < timestamp_ms:
            raise HTTPException(status_code=422, detail=f"Event {index + 1} end_ms precedes timestamp_ms")
        event_text = entry.get("event", entry.get("text", entry.get("event_type")))
        if not isinstance(event_text, str) or not event_text.strip():
            raise HTTPException(status_code=422, detail=f"Event {index + 1} requires a non-empty event or text value")
        normalized.append({
            **entry,
            "event": event_text.strip(),
            "timestamp_ms": timestamp_ms,
            "end_ms": end_ms,
            # JSON is an instructor-provided structured input, represented by
            # the existing canonical ``manual`` source. ``json_input`` below
            # remains the internal replacement marker.
            "source": "manual" if entry.get("source") == "json_input" else entry.get("source", "manual"),
            "json_input": True,
            "json_input_index": index,
        })

    current = session.get("event_log") or []
    if isinstance(current, str):
        current = json.loads(current)
    current = [entry for entry in current if not entry.get("json_input")]
    current.extend(normalized)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE sessions SET event_log=%s WHERE id=%s", (json.dumps(current), session["id"]))
        await conn.commit()
    canonical = DebriefAdapter().convert({**session, "event_log": current}, event_log=current)
    job = await JobStore(pool).enqueue(canonical)
    return {
        "session_code": session_code,
        "event_count": len(normalized),
        "job_id": job["job_id"],
        "status": job["status"],
        "message": "Structured JSON imported and debrief queued.",
    }


@api_app.post("/api/session/{session_code}/generate-synthetic-transcript", status_code=202)
async def generate_synthetic_transcript(session_code: str, user: dict = Depends(require_instructor)):
    """Append a clearly labelled demo transcript and queue a replacement debrief.

    This endpoint is for walkthroughs only.  It is intentionally separate from
    audio ingestion so generated dialogue cannot be mistaken for a recording.
    """
    session = await _debrief_session(session_code, user, write=True)
    if session.get("is_active"):
        raise HTTPException(status_code=409, detail="End the session before generating a synthetic transcript")
    from synthetic_transcript import generate_synthetic_segments
    generated = generate_synthetic_segments(session_code)
    current = session.get("event_log") or []
    if isinstance(current, str):
        current = json.loads(current)
    current = [entry for entry in current if not entry.get("synthetic_transcript")]
    current.extend(generated)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE sessions SET event_log=%s WHERE id=%s", (json.dumps(current), session["id"]))
        await conn.commit()
    canonical = DebriefAdapter().convert({**session, "event_log": current}, event_log=current)
    job = await JobStore(pool).enqueue(canonical)
    await sio.emit("synthetic_transcript_generated", {
        "session_code": session_code, "segment_count": len(generated), "debrief_job_id": job["job_id"],
        "warning": "Synthetic transcript — demonstration only",
    }, room=session_code)
    return {"session_code": session_code, "segment_count": len(generated), "job_id": job["job_id"],
            "status": job["status"], "warning": "Synthetic transcript — demonstration only"}


@api_app.post("/api/session/{session_code}/upload-synthetic-audio", status_code=202)
async def upload_synthetic_audio(
    session_code: str,
    audio: UploadFile = File(...),
    user: dict = Depends(require_instructor),
):
    """Store a generated demo audio file, append its synthetic transcript, and re-debrief.

    This deliberately does not transcribe the file.  The accompanying dialogue
    is deterministic synthetic data and the resulting report carries that
    warning, preventing it from being represented as observed performance.
    """
    session = await _debrief_session(session_code, user, write=True)
    if session.get("is_active"):
        raise HTTPException(status_code=409, detail="End the session before uploading synthetic audio")
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in DEBRIEF_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    content = await audio.read(MAX_DEBRIEF_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Audio upload is empty")
    if len(content) > MAX_DEBRIEF_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio upload exceeds the 200 MB limit")
    SYNTHETIC_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_slugify(session_code)}_synthetic_{uuid.uuid4().hex}{suffix}"
    path = SYNTHETIC_AUDIO_DIR / filename
    path.write_bytes(content)

    from synthetic_transcript import generate_synthetic_segments
    current = session.get("event_log") or []
    if isinstance(current, str):
        current = json.loads(current)
    current = [entry for entry in current if not entry.get("synthetic_transcript")]
    current.append({"synthetic_audio_upload": True, "audio_url": f"/api/synthetic-audio/{filename}"})
    current.extend(generate_synthetic_segments(session_code))
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE sessions SET event_log=%s WHERE id=%s", (json.dumps(current), session["id"]))
        await conn.commit()
    canonical = DebriefAdapter().convert({**session, "event_log": current}, event_log=current)
    job = await JobStore(pool).enqueue(canonical)
    return {"session_code": session_code, "audio_url": f"/api/synthetic-audio/{filename}",
            "segment_count": 8, "job_id": job["job_id"], "status": job["status"],
            "warning": "Synthetic audio and its deterministic transcript are demonstration-only"}


@api_app.get("/api/synthetic-audio/{filename}")
async def get_synthetic_audio(filename: str, user: dict = Depends(get_current_user)):
    path = SYNTHETIC_AUDIO_DIR / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Synthetic audio file not found")
    return FileResponse(path=str(path))


async def _initialize_live_audio_tables(pool):
    """Small durable manifest for browser-recorded chunks (one recording/session)."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""CREATE TABLE IF NOT EXISTS live_audio_recordings (
                session_code VARCHAR(100) PRIMARY KEY,
                audio_source VARCHAR(20) NOT NULL DEFAULT 'ceiling',
                language_mode VARCHAR(20), mime_type VARCHAR(100),
                status VARCHAR(30) NOT NULL DEFAULT 'recording', chunk_count INT NOT NULL DEFAULT 0,
                bytes_uploaded BIGINT NOT NULL DEFAULT 0, audio_job_id VARCHAR(64), error_message TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )""")
        await conn.commit()

    # One session can receive distinct microphone tracks from the instructor
    # and students.  The original table above is retained for old recordings;
    # new capture uses this recorder-scoped manifest to avoid overwriting
    # chunks when two people record at the same time.
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""CREATE TABLE IF NOT EXISTS live_audio_recorders (
                session_code VARCHAR(100) NOT NULL,
                recorder_id VARCHAR(80) NOT NULL,
                participant_role VARCHAR(20) NOT NULL,
                audio_source VARCHAR(20) NOT NULL DEFAULT 'ceiling',
                language_mode VARCHAR(20), mime_type VARCHAR(100),
                status VARCHAR(30) NOT NULL DEFAULT 'recording',
                chunk_count INT NOT NULL DEFAULT 0, bytes_uploaded BIGINT NOT NULL DEFAULT 0,
                audio_job_id VARCHAR(64), error_message TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (session_code, recorder_id)
            )""")
        await conn.commit()


async def _live_audio_session(session_code: str, user: dict):
    """Authorize an instructor or a student scoped to this live session."""
    return await _debrief_session(session_code, user, write=False)


def _recorder_id(user: dict, supplied: object = None) -> str:
    """Use a stable, safe per-participant recorder key within one session."""
    role = str(user.get("role", "participant")).lower()
    # Anonymous student portal tokens receive a placeholder numeric id, while
    # their token subject is unique. Prefer the username/subject so two
    # students in one session never share a recorder folder.
    identity = user.get("username") or user.get("id") or "participant"
    # Students cannot impersonate another recorder by choosing an arbitrary ID.
    raw = supplied if role in {"instructor", "operator", "admin"} and supplied else f"{role}_{identity}"
    return _slugify(str(raw), max_len=80)


async def _append_live_audio_event(session_code: str, event: str, **details):
    """Persist and broadcast an auditable recording-pipeline transition."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "event_type": "AUDIO_STATUS",
        "source": "live_audio",
        **details,
    }
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, event_log FROM sessions WHERE session_code=%s FOR UPDATE", (session_code,))
            session = await cur.fetchone()
            if not session:
                return entry
            event_log = session.get("event_log") or []
            if isinstance(event_log, str):
                event_log = json.loads(event_log)
            event_log.append(entry)
            await cur.execute("UPDATE sessions SET event_log=%s WHERE id=%s", (json.dumps(event_log), session["id"]))
        await conn.commit()
    await sio.emit("session_event", entry, room=session_code)
    await sio.emit("live_audio_status", {"session_code": session_code, **details}, room=session_code)
    return entry


@api_app.post("/api/session/{session_code}/live-audio/start")
async def start_live_audio_recording(
    session_code: str, body: dict, user: dict = Depends(require_authenticated_user),
):
    """Create a recoverable browser-recorder manifest while a simulation is live."""
    session = await _live_audio_session(session_code, user)
    if not session.get("is_active"):
        raise HTTPException(status_code=409, detail="Live recording can start only while the session is active")
    source = str(body.get("source", "ceiling")).lower().strip()
    language_mode = body.get("language_mode") or None
    mime_type = str(body.get("mime_type", "audio/webm"))[:100]
    recorder_id = _recorder_id(user, body.get("recorder_id"))
    if source not in {"ceiling", "lapel"}:
        raise HTTPException(status_code=422, detail="source must be 'ceiling' or 'lapel'")
    if language_mode not in {None, "english", "tamil", "tanglish"}:
        raise HTTPException(status_code=422, detail="Unsupported language mode")
    pool = await get_db_pool()
    await _initialize_live_audio_tables(pool)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM live_audio_recorders WHERE session_code=%s AND recorder_id=%s", (session_code, recorder_id))
            existing = await cur.fetchone()
            if existing and existing["status"] in {"recording", "finalizing", "queued", "completed"}:
                return {"session_code": session_code, "recorder_id": recorder_id, "status": existing["status"], "chunk_count": existing["chunk_count"]}
            await cur.execute("""INSERT INTO live_audio_recorders
                (session_code, recorder_id, participant_role, audio_source, language_mode, mime_type, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'recording')
                ON DUPLICATE KEY UPDATE participant_role=VALUES(participant_role), audio_source=VALUES(audio_source),
                language_mode=VALUES(language_mode), mime_type=VALUES(mime_type), status='recording', error_message=NULL""",
                (session_code, recorder_id, user.get("role", "participant"), source, language_mode, mime_type))
        await conn.commit()
    (LIVE_AUDIO_DIR / _slugify(session_code) / recorder_id).mkdir(parents=True, exist_ok=True)
    await _append_live_audio_event(
        session_code,
        f"Audio recording started ({user.get('role', 'participant')})",
        recorder_id=recorder_id,
        recorder_status="recording",
        participant_role=user.get("role", "participant"),
        chunk_count=0,
    )
    return {"session_code": session_code, "recorder_id": recorder_id, "status": "recording", "chunk_interval_seconds": 20}


@api_app.post("/api/session/{session_code}/live-audio/chunk", status_code=202)
async def upload_live_audio_chunk(
    session_code: str, sequence: int = Form(...), audio: UploadFile = File(...), recorder_id: str = Form(None),
    user: dict = Depends(require_authenticated_user),
):
    """Persist one MediaRecorder chunk without blocking vitals or simulator controls."""
    if sequence < 0 or sequence > 10000:
        raise HTTPException(status_code=422, detail="Invalid audio chunk sequence")
    await _live_audio_session(session_code, user)
    recorder_id = _recorder_id(user, recorder_id)
    suffix = Path(audio.filename or "chunk.webm").suffix.lower() or ".webm"
    if suffix not in DEBRIEF_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    content = await audio.read(MAX_DEBRIEF_AUDIO_BYTES + 1)
    if not content or len(content) > MAX_DEBRIEF_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="Audio chunk is empty or too large")
    pool = await get_db_pool()
    await _initialize_live_audio_tables(pool)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT status FROM live_audio_recorders WHERE session_code=%s AND recorder_id=%s", (session_code, recorder_id))
            recording = await cur.fetchone()
            if not recording or recording["status"] != "recording":
                raise HTTPException(status_code=409, detail="No active live recording for this session")
    folder = LIVE_AUDIO_DIR / _slugify(session_code) / recorder_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sequence:05d}{suffix}"
    path.write_bytes(content)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""UPDATE live_audio_recorders
                SET chunk_count=GREATEST(chunk_count, %s), bytes_uploaded=bytes_uploaded+%s
                WHERE session_code=%s AND recorder_id=%s""", (sequence + 1, len(content), session_code, recorder_id))
            await cur.execute("SELECT chunk_count, bytes_uploaded, status FROM live_audio_recorders WHERE session_code=%s AND recorder_id=%s", (session_code, recorder_id))
            saved = await cur.fetchone()
        await conn.commit()
    await sio.emit("live_audio_status", {
        "session_code": session_code, "recorder_id": recorder_id,
        "recorder_status": saved["status"], "chunk_count": saved["chunk_count"],
        "bytes_uploaded": saved["bytes_uploaded"],
    }, room=session_code)
    return {"sequence": sequence, "recorder_id": recorder_id, "status": "stored", **saved}


@api_app.post("/api/session/{session_code}/live-audio/stop")
async def stop_live_audio_recording(
    session_code: str, body: dict | None = None, user: dict = Depends(require_authenticated_user),
):
    """Mark a browser capture stopped while retaining its recoverable chunks."""
    await _live_audio_session(session_code, user)
    recorder_id = _recorder_id(user, (body or {}).get("recorder_id"))
    pool = await get_db_pool()
    await _initialize_live_audio_tables(pool)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""UPDATE live_audio_recorders SET status='stopped', updated_at=UTC_TIMESTAMP()
                WHERE session_code=%s AND recorder_id=%s AND status='recording'""", (session_code, recorder_id))
            await cur.execute("""SELECT chunk_count, bytes_uploaded, status FROM live_audio_recorders
                WHERE session_code=%s AND recorder_id=%s""", (session_code, recorder_id))
            recording = await cur.fetchone()
        await conn.commit()
    if not recording:
        raise HTTPException(status_code=404, detail="No live recording found for this participant")
    await _append_live_audio_event(
        session_code,
        "Audio recording stopped; saved chunks will be transcribed after session end",
        recorder_id=recorder_id,
        recorder_status=recording["status"],
        chunk_count=recording["chunk_count"],
        bytes_uploaded=recording["bytes_uploaded"],
    )
    return {"session_code": session_code, "recorder_id": recorder_id, **recording}


@api_app.get("/api/session/{session_code}/live-audio/status")
async def get_live_audio_recording_status(session_code: str, user: dict = Depends(require_authenticated_user)):
    """Return durable capture/transcription evidence for this simulation."""
    await _live_audio_session(session_code, user)
    pool = await get_db_pool()
    await _initialize_live_audio_tables(pool)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            params = [session_code]
            where = "r.session_code=%s"
            if user.get("role") == "student":
                where += " AND r.recorder_id=%s"
                params.append(_recorder_id(user))
            await cur.execute(f"""SELECT r.recorder_id, r.participant_role, r.audio_source,
                r.language_mode, r.status AS recorder_status, r.chunk_count, r.bytes_uploaded,
                r.audio_job_id, r.error_message AS recorder_error, r.created_at, r.updated_at,
                j.status AS job_status, j.segment_count, j.error_message AS job_error
                FROM live_audio_recorders r
                LEFT JOIN debrief_audio_jobs j ON j.job_id=r.audio_job_id
                WHERE {where} ORDER BY r.created_at""", tuple(params))
            rows = await cur.fetchall()
    return {"session_code": session_code, "recorders": rows}


@api_app.post("/api/session/{session_code}/live-audio/finalize", status_code=202)
async def finalize_live_audio_recording(session_code: str, recorder_id: str | None = None, user: dict = Depends(require_instructor)):
    """Join persisted WebM chunks after the simulation ends and enqueue transcription."""
    session = await _debrief_session(session_code, user, write=True)
    if session.get("is_active"):
        raise HTTPException(status_code=409, detail="End the session before finalizing live audio")
    pool = await get_db_pool()
    await _initialize_live_audio_tables(pool)
    # Ending a session finalizes every surviving participant track.
    if recorder_id is None:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT recorder_id, status, audio_job_id FROM live_audio_recorders WHERE session_code=%s", (session_code,))
                recorders = await cur.fetchall()
        results = []
        for item in recorders:
            if item["status"] in {"recording", "stopped"}:
                results.append(await finalize_live_audio_recording(session_code, item["recorder_id"], user))
            elif item.get("audio_job_id"):
                results.append({"recorder_id": item["recorder_id"], "status": item["status"], "audio_job_id": item["audio_job_id"]})
        if results:
            return {"session_code": session_code, "status": "queued", "recordings": results}
        raise HTTPException(status_code=404, detail="No live recording found for this session")
    recorder_id = _recorder_id(user, recorder_id)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM live_audio_recorders WHERE session_code=%s AND recorder_id=%s FOR UPDATE", (session_code, recorder_id))
            recording = await cur.fetchone()
            if not recording:
                raise HTTPException(status_code=404, detail="No live recording found for this session")
            if recording.get("audio_job_id"):
                return {"session_code": session_code, "status": recording["status"], "audio_job_id": recording["audio_job_id"]}
            if recording.get("status") not in {"recording", "stopped"}:
                raise HTTPException(status_code=409, detail="Recording is not ready to finalize")
            await cur.execute("UPDATE live_audio_recorders SET status='finalizing' WHERE session_code=%s AND recorder_id=%s", (session_code, recorder_id))
        await conn.commit()
    folder = LIVE_AUDIO_DIR / _slugify(session_code) / recorder_id
    chunks = sorted(path for path in folder.glob("*.*") if path.is_file())
    if not chunks:
        raise HTTPException(status_code=422, detail="No recoverable audio chunks were uploaded")
    # WebM MediaRecorder emits an initialization segment followed by media clusters;
    # preserving byte order creates a single recording for ffmpeg/Whisper processing.
    assembled = DEBRIEF_AUDIO_DIR / f"{_slugify(session_code)}_live_{uuid.uuid4().hex}.webm"
    DEBRIEF_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    with assembled.open("wb") as output:
        for chunk in chunks:
            output.write(chunk.read_bytes())
    # A participant may start recording after the simulation begins. Preserve
    # that clock relationship so their transcript aligns with vitals and
    # instructor actions rather than incorrectly starting at 00:00.
    audio_offset_ms = 0
    if session.get("started_at") and recording.get("created_at"):
        audio_offset_ms = max(0, int((recording["created_at"] - session["started_at"]).total_seconds() * 1000))
    job = await AudioDebriefJobStore(pool).enqueue(
        session_code, assembled, recording["audio_source"], recording.get("language_mode"), audio_offset_ms
    )
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""UPDATE live_audio_recorders SET status='queued', audio_job_id=%s,
                error_message=NULL WHERE session_code=%s AND recorder_id=%s""", (job["job_id"], session_code, recorder_id))
        await conn.commit()
    await _append_live_audio_event(
        session_code,
        "Audio saved; transcription and speaker diarization queued",
        recorder_id=recorder_id,
        recorder_status="queued",
        audio_job_id=job["job_id"],
        chunk_count=len(chunks),
    )
    return {"session_code": session_code, "recorder_id": recorder_id, "status": job["status"], "audio_job_id": job["job_id"], "chunk_count": len(chunks), "audio_offset_ms": audio_offset_ms}


@api_app.post("/session/{session_code}/checklist/{item_id}/note")
async def add_checklist_note(
    session_code: str,
    item_id: str,
    text: str = Form(None),
    audio: UploadFile = File(None),
    user: dict = Depends(require_instructor),
):
    """Attach a typed comment and/or a voice-note recording to one checklist item."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, checklist_state, event_log FROM sessions WHERE session_code = %s",
                (session_code,)
            )
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            checklist = json.loads(session["checklist_state"]) if session.get("checklist_state") else []
            target = None
            for item in checklist:
                if (
                    str(item.get("id")) == str(item_id)
                    or item.get("action") == item_id
                    or str(item.get("item_id")) == str(item_id)
                ):
                    target = item
                    break

            if not target:
                raise HTTPException(status_code=404, detail=f"Checklist item '{item_id}' not found")

            if text is not None:
                target["notes"] = text
            if audio is not None:
                audio_bytes = await audio.read()
                if audio_bytes:
                    target["voice_note_url"] = _save_voice_note(session_code, _slugify(item_id), audio, audio_bytes)
            target["note_updated_at"] = datetime.utcnow().isoformat()

            event_log = json.loads(session["event_log"]) if session.get("event_log") else []
            summary = text.strip()[:140] if text else "(voice note)"
            event_entry = {
                "timestamp": target["note_updated_at"],
                "event": f"Instructor note on '{target.get('action', item_id)}': {summary}",
                "event_type": "CHECKLIST_NOTE",
                "item_id": target.get("id", item_id),
            }
            event_log.append(event_entry)

            await cur.execute(
                "UPDATE sessions SET checklist_state = %s, event_log = %s WHERE id = %s",
                (json.dumps(checklist), json.dumps(event_log), session["id"])
            )

    await sio.emit("checklist_updated", {"checklist": checklist}, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)
    return {"item": target}


@api_app.get("/session/{session_code}/review")
async def get_session_review(session_code: str, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT instructor_review_text, instructor_review_audio_url, instructor_review_updated_at "
                "FROM sessions WHERE session_code = %s",
                (session_code,)
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")

    return {
        "text": row.get("instructor_review_text") or "",
        "audio_url": row.get("instructor_review_audio_url"),
        "updated_at": row["instructor_review_updated_at"].isoformat() if row.get("instructor_review_updated_at") else None,
    }


@api_app.post("/session/{session_code}/review")
async def save_session_review(
    session_code: str,
    text: str = Form(None),
    audio: UploadFile = File(None),
    user: dict = Depends(require_instructor),
):
    """Save the instructor's overall end-of-session review (text and/or a voice recording)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, event_log, instructor_review_audio_url FROM sessions WHERE session_code = %s",
                (session_code,)
            )
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            updates = {}
            if text is not None:
                updates["instructor_review_text"] = text
            audio_url = session.get("instructor_review_audio_url")
            if audio is not None:
                audio_bytes = await audio.read()
                if audio_bytes:
                    audio_url = _save_voice_note(session_code, "session_review", audio, audio_bytes)
                    updates["instructor_review_audio_url"] = audio_url

            now = datetime.utcnow()
            updates["instructor_review_updated_at"] = now

            set_clause = ", ".join(f"{k} = %s" for k in updates)
            await cur.execute(
                f"UPDATE sessions SET {set_clause} WHERE id = %s",
                (*updates.values(), session["id"])
            )

            event_log = json.loads(session["event_log"]) if session.get("event_log") else []
            event_entry = {
                "timestamp": now.isoformat(),
                "event": "Instructor added an overall session review",
                "event_type": "SESSION_REVIEW",
            }
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))

    payload = {
        "text": updates.get("instructor_review_text", text) or "",
        "audio_url": audio_url,
        "updated_at": now.isoformat(),
    }
    await sio.emit("session_review_updated", payload, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)
    return payload


@api_app.get("/session/{session_code}/history")
async def get_session_history(
    session_code: str,
    since: str = Query(None),
    limit: int = Query(300),
    user: dict = Depends(get_current_user),
):
    """Return numeric vital history for trend graphing."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT history FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

    history = json.loads(session["history"]) if session["history"] else []
    if since:
        history = [h for h in history if h.get("timestamp", "") > since]
    return {"history": history[-limit:]}


# ── Debrief Pipeline Integration ──────────────────────────────────
DEBRIEF_STATUS_CACHE: dict = {}

async def _debrief_session(session_code, user, write=False):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM sessions WHERE session_code=%s", (session_code,))
            session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    owns = user.get("role") in ("instructor", "operator") and session["created_by"] == user.get("id")
    scoped_student = not write and user.get("role") == "student" and user.get("session_code") == session_code
    if not (owns or scoped_student or user.get("role") == "admin"):
        raise HTTPException(status_code=403, detail="Session access denied")
    return session

async def _enqueue_debrief(session_code, user):
    session = await _debrief_session(session_code, user, write=True)
    if session.get("is_active"):
        raise HTTPException(status_code=409, detail="End the session before generating a report")
    try:
        # Pass the event_log JSON column explicitly so the engine receives
        # all simulator events recorded during the session.  Without this the
        # adapter sees an empty list and produces score = N/A every time.
        data = DebriefAdapter().convert(
            session,
            event_log=session.get("event_log"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = await JobStore(await get_db_pool()).enqueue(data)
    return {"session_code": session_code, **job, "status": "running" if job["status"] == "queued" else job["status"]}



@api_app.post("/session/{session_code}/end")
async def end_session(
    session_code: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_instructor)
):
    await _debrief_session(session_code, user, write=True)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            await cur.execute(
                "UPDATE sessions SET is_active = 0, ended_at = COALESCE(ended_at, %s) WHERE id = %s",
                (datetime.utcnow(), session["id"])
            )

    # Emit session_ended to all connected clients
    await emit_session_ended(session_code)

    # Browser navigation must never be the only path that finalizes a live
    # recording. If chunks were safely persisted during the run, enqueue their
    # transcription here; a missing recorder is normal and does not block the
    # clinical debrief.
    try:
        await finalize_live_audio_recording(session_code, user=user)
    except HTTPException as exc:
        if exc.status_code != 404:
            print(f"[LIVE AUDIO] Could not finalize {session_code}: {exc.detail}")

    job = await _enqueue_debrief(session_code, user)
    return {"message": "Session ended", "debrief_status": job["status"], "job_id": job["job_id"]}


# ── Debrief API Endpoints ──────────────────────────────────────────

@api_app.get("/api/demo/synthetic-vf")
async def get_synthetic_vf_demo(user: dict = Depends(require_instructor)):
    """Return the explicit JSON-only CPR debrief fixture for UI demonstration."""
    if not SYNTHETIC_TEST_REPORT_JSON.is_file():
        raise HTTPException(status_code=404, detail="Synthetic test fixture has not been generated yet.")
    try:
        report = json.loads(SYNTHETIC_TEST_REPORT_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Synthetic test fixture could not be loaded.") from exc
    return {
        "fixture_type": "synthetic_json_only",
        "notice": "Synthetic transcript and event annotations; microphone and diarization are bypassed.",
        "report": report,
        "pdf_available": SYNTHETIC_TEST_PDF.is_file(),
    }


@api_app.get("/api/demo/synthetic-vf/pdf")
async def download_synthetic_vf_demo_pdf(user: dict = Depends(require_instructor)):
    """Download the matching synthetic-fixture debrief PDF."""
    if not SYNTHETIC_TEST_PDF.is_file():
        raise HTTPException(status_code=404, detail="Synthetic test PDF has not been generated yet.")
    return FileResponse(
        SYNTHETIC_TEST_PDF,
        media_type="application/pdf",
        filename="SYNTH_VF_TEST_01_debrief.pdf",
        headers={"Cache-Control": "no-store"},
    )

@api_app.post("/api/debrief/generate/{session_code}")
async def generate_debrief_endpoint(
    session_code: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Queue an idempotent, versioned report; retain prior reports on failure."""
    return await _enqueue_debrief(session_code, user)


@api_app.get("/api/debrief/status/{session_code}")
async def get_debrief_status(
    session_code: str,
    user: dict = Depends(get_current_user),
):
    """Return durable status, including failure details and automatic attempts."""
    await _debrief_session(session_code, user)
    pool = await get_db_pool()
    job = await JobStore(pool).latest(session_code)
    if job:
        return {"session_code": session_code, "job_id": job["job_id"],
            "status": "running" if job["status"] == "queued" else job["status"],
            "error_message": job.get("error_message"), "attempts": job["attempts"]}
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT status FROM debrief_reports WHERE session_code = %s", (session_code,))
            row = await cur.fetchone()
            if row:
                db_status = str(row["status"]).lower()
                if db_status in ("completed", "failed"):
                    DEBRIEF_STATUS_CACHE[session_code] = db_status
                    return {"session_code": session_code, "status": db_status}

    if session_code in DEBRIEF_STATUS_CACHE:
        return {
            "session_code": session_code,
            "status": DEBRIEF_STATUS_CACHE[session_code]
        }

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if session:
                return {"session_code": session_code, "status": "pending"}

    return {"session_code": session_code, "status": "pending"}


@api_app.get("/api/debrief/list")
async def list_debrief_reports(
    limit: int = Query(20),
    user: dict = Depends(get_current_user),
):
    """Return a list of completed debrief reports for display on the Reports page."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT dr.session_code, dr.overall_score, dr.grade, dr.status,
                          dr.created_at, dr.updated_at,
                          s.started_at, s.ended_at
                   FROM debrief_reports dr
                   LEFT JOIN sessions s ON s.session_code = dr.session_code
                   WHERE dr.status = 'COMPLETED' AND (s.created_by=%s OR %s='admin')
                   ORDER BY dr.updated_at DESC
                   LIMIT %s""",
                (user["id"], user["role"], limit)
            )
            rows = await cur.fetchall()

    results = []
    for row in rows:
        results.append({
            "session_code": row["session_code"],
            "overall_score": row["overall_score"],
            "grade": row["grade"],
            "status": str(row["status"]).lower(),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "started_at": row["started_at"].isoformat() if row.get("started_at") else None,
            "ended_at": row["ended_at"].isoformat() if row.get("ended_at") else None,
        })
    return {"reports": results, "total": len(results)}


@api_app.get("/api/leaderboard")
async def get_leaderboard(limit: int = Query(20), user: dict = Depends(get_current_user)):
    """Return ranked team leaderboard from MySQL via canonical gamification service."""
    from debriefing.scenarios.gamification import canonical_gamification_service
    lb = canonical_gamification_service.get_leaderboard_sync(limit=limit)
    return {"leaderboard": lb, "total": len(lb)}


@api_app.get("/api/gamification/me")
@api_app.get("/api/gamification/team/{team_name}")
async def get_gamification_me(
    team_name: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Return comprehensive team gamification profile and badge status."""
    target_team = team_name or user.get("username") or "Resus Team"
    from debriefing.scenarios.gamification import canonical_gamification_service
    profile = canonical_gamification_service.get_team_profile_sync(target_team)
    return profile


@api_app.get("/api/gamification/badges")
async def get_gamification_badges(
    team_name: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Return full badge catalogue with earned status."""
    target_team = team_name or user.get("username") or "Resus Team"
    from debriefing.scenarios.gamification import canonical_gamification_service
    badges = canonical_gamification_service.get_badge_catalogue(team_name=target_team)
    return {"badges": badges}


@api_app.get("/api/gamification/session/{session_code}")
async def get_session_gamification(
    session_code: str,
    user: dict = Depends(get_current_user)
):
    """Return gamification results for a specific completed simulation session."""
    from debriefing.scenarios.gamification import canonical_gamification_service
    rec = canonical_gamification_service._get_session_record_sync(session_code)
    if not rec:
        # If debrief is completed, trigger processing
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM debrief_reports WHERE session_code = %s", (session_code,))
                report_row = await cur.fetchone()
                await cur.execute("SELECT * FROM sessions WHERE session_code = %s", (session_code,))
                sess_row = await cur.fetchone()

        if report_row and sess_row:
            team_name = sess_row.get("team_name") or sess_row.get("created_by") or user.get("username") or "Resus Team"
            score = float(report_row["overall_score"])
            grade = str(report_row["grade"])
            debrief_data = json.loads(report_row["debrief_data"]) if report_row.get("debrief_data") else {}
            findings = debrief_data.get("findings", [])

            rec = canonical_gamification_service.record_session_sync(
                session_code=session_code,
                team_name=team_name,
                scenario_id=str(sess_row.get("current_scenario_id", "")),
                scenario_name=sess_row.get("scenario_name", "ACLS Scenario"),
                level="beginner",
                score=score,
                prediction_accuracy=score,
                grade=grade,
                base_xp=200,
                total_deviations=len(findings),
                critical_misses=[],
                ai_debriefed=report_row["status"] == "COMPLETED",
                checklist_items=[],
                team_leader=team_name,
                is_team_leader=True
            )
        else:
            raise HTTPException(status_code=404, detail=f"Gamification record for session '{session_code}' not found.")

    return rec


def _scenario_display_name(spec: dict) -> str:
    if not spec:
        return "Simulation Session"
    patient = spec.get("patient") or {}
    if spec.get("title"):
        return spec["title"]
    if patient.get("presentation"):
        return patient["presentation"][:60]
    return "Simulation Session"


def _scenario_patient_label(spec: dict) -> str:
    patient = (spec or {}).get("patient") or {}
    if not patient:
        return "—"
    age = patient.get("age")
    sex = patient.get("sex")
    if age and sex:
        return f"{age}{str(sex)[0].upper()}"
    return patient.get("presentation", "—")[:40] if patient.get("presentation") else "—"


@api_app.get("/api/sessions/list")
async def list_sessions(limit: int = Query(50), user: dict = Depends(get_current_user)):
    """Real session history + summary stats for the instructor dashboard/sessions pages."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT s.session_code, s.started_at, s.ended_at, s.is_active,
                          s.current_scenario_json, s.team_name,
                          dr.overall_score, dr.grade, dr.status AS debrief_status
                   FROM sessions s
                   LEFT JOIN debrief_reports dr ON dr.session_code = s.session_code
                   WHERE s.created_by = %s
                   ORDER BY s.started_at DESC
                   LIMIT %s""",
                (user["id"], limit)
            )
            rows = await cur.fetchall()

            await cur.execute("SELECT COUNT(*) AS c FROM sessions WHERE created_by = %s", (user["id"],))
            total = (await cur.fetchone())["c"]

            await cur.execute(
                "SELECT COUNT(*) AS c FROM sessions WHERE created_by = %s AND DATE(started_at) = CURDATE()",
                (user["id"],)
            )
            today = (await cur.fetchone())["c"]

            await cur.execute(
                """SELECT COUNT(*) AS c FROM sessions s
                   JOIN debrief_reports dr ON dr.session_code = s.session_code
                   WHERE s.created_by = %s AND dr.status = 'COMPLETED'""",
                (user["id"],)
            )
            completed = (await cur.fetchone())["c"]

            await cur.execute(
                """SELECT COUNT(*) AS c FROM sessions s
                   WHERE s.created_by = %s AND s.is_active = 0
                   AND NOT EXISTS (
                       SELECT 1 FROM debrief_reports dr
                       WHERE dr.session_code = s.session_code AND dr.status = 'COMPLETED'
                   )""",
                (user["id"],)
            )
            pending = (await cur.fetchone())["c"]

    sessions = []
    for row in rows:
        spec = json.loads(row["current_scenario_json"]) if row.get("current_scenario_json") else {}
        started = row["started_at"]
        ended = row["ended_at"]
        if row["is_active"]:
            status = "Active"
        elif str(row.get("debrief_status") or "").upper() == "COMPLETED":
            status = "Completed"
        else:
            status = "Pending Debrief"

        if started and ended:
            secs = int((ended - started).total_seconds())
            duration = f"{secs // 60} Minutes"
        elif started and row["is_active"]:
            secs = int((datetime.utcnow() - started).total_seconds())
            duration = f"{secs // 60} Minutes"
        else:
            duration = "—"

        if row.get("overall_score") is not None:
            score = f"{round(row['overall_score'])}%"
        elif row["is_active"]:
            score = "In Progress"
        else:
            score = "Pending"

        sessions.append({
            "id": row["session_code"],
            "session_code": row["session_code"],
            "name": _scenario_display_name(spec),
            "patient": _scenario_patient_label(spec),
            "date": started.strftime("%d %b %Y") if started else "—",
            "duration": duration,
            "status": status,
            "score": score,
            "team_name": row.get("team_name"),
            "mode": spec.get("mode", "simulation"),
        })

    return {
        "sessions": sessions,
        "stats": {
            "total": total,
            "today": today,
            "completed": completed,
            "pending": pending,
        },
    }


@api_app.get("/api/scenarios/catalog")
async def get_scenarios_catalog(user: dict = Depends(get_current_user)):
    """Real named patient scenarios from the DB (used by dashboard 'library' quick-look)."""
    catalog = []
    for s in sm.SCENARIOS_CACHE:
        pd = s.get("patient_details") or {}
        catalog.append({
            "id": s["id"],
            "name": s.get("name", "Scenario"),
            "diagnosis": pd.get("diagnosis", "—"),
            "triage_level": pd.get("triageLevel", "—"),
            "duration": pd.get("duration", "—"),
        })
    return {"scenarios": catalog, "total": len(catalog)}


@api_app.get("/api/debrief/{session_code}")
async def get_debrief_report(
    session_code: str,
    user: dict = Depends(get_current_user),
):
    """Return full debrief report object."""
    await _debrief_session(session_code, user)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM debrief_reports WHERE session_code = %s", (session_code,))
            row = await cur.fetchone()
            if not row:
                status = DEBRIEF_STATUS_CACHE.get(session_code, "pending")
                if status in ("running", "pending"):
                    return {
                        "session_code": session_code,
                        "status": status,
                        "message": "Debrief report is currently being generated"
                    }
                raise HTTPException(status_code=404, detail=f"Debrief report for '{session_code}' not found")

    debrief_data = json.loads(row["debrief_data"]) if row.get("debrief_data") else {}
    return {
        "session_code": session_code,
        "overall_score": row["overall_score"],
        "grade": row["grade"],
        "status": row["status"],
        "pdf_path": row["pdf_path"],
        "error_message": row.get("error_message"),
        "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else str(row["updated_at"]),
        "debrief": debrief_data,
    }


@api_app.get("/api/reports/{session_code}")
async def get_report_pdf(
    session_code: str,
    user: dict = Depends(get_current_user),
):
    """Stream generated PDF report."""
    await _debrief_session(session_code, user)
    pdf_path = None
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT pdf_path FROM debrief_reports WHERE session_code = %s", (session_code,))
            row = await cur.fetchone()
            if row and row.get("pdf_path"):
                pdf_path = Path(row["pdf_path"])

    if not pdf_path or not pdf_path.exists():
        fallback = Path(__file__).parent / "debriefing" / "output" / "reports" / f"{session_code}_debrief.pdf"
        if fallback.exists():
            pdf_path = fallback

    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF report for session '{session_code}' not found or not generated yet")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{session_code}_debrief.pdf",
        # A debrief can be regenerated after transcription finishes while the
        # URL remains the same.  Never let a browser reuse an earlier PDF for
        # a session code: it could hide the newly appended transcript.
        headers={"Cache-Control": "no-store, max-age=0, must-revalidate"},
    )





import sys
import os
import uuid
from pathlib import Path

try:
    from debriefing.scenarios.generator import ScenarioGenerator
    from debriefing.scenarios.outcome_predictor import OutcomePredictor
    from debriefing.scenarios.voice_narrator import VoiceNarrator
    from debriefing.scenarios.instructor_listener import InstructorListener
    
    _scenario_gen = ScenarioGenerator()
    _outcome_pred = OutcomePredictor()
    _narrator = VoiceNarrator(output_dir=DEBRIEFING_PATH / "output" / "tts")
    _instructor = InstructorListener()
except Exception as e:
    print(f"[main.py] Warning: Scenario modules failed to load: {e}")
    _scenario_gen = _outcome_pred = _narrator = _instructor = None

_active_scenario_runs = {}

def map_rhythm_type_to_vitals(rhythm_type: str) -> dict:
    rt = (rhythm_type or "").upper()
    if "VF" in rt or "FIBRILLATION" in rt:
        return {
            "rhythm": "Ventricular Fibrillation",
            "HR": 0.0,
            "pulse_rate": 0.0,
            "SpO2": 0.0,
            "ABP_sys": 0.0,
            "ABP_dia": 0.0,
            "MAP": 0.0,
            "avRR": 0.0,
            "etCO2": 0.0,
            "emd_pea": False,
        }
    elif "PEA" in rt:
        return {
            "rhythm": "Sinus Rhythm",
            "HR": 60.0,
            "pulse_rate": 0.0,
            "SpO2": 0.0,
            "ABP_sys": 0.0,
            "ABP_dia": 0.0,
            "MAP": 0.0,
            "avRR": 0.0,
            "etCO2": 0.0,
            "emd_pea": True,
        }
    elif "ASYSTOLE" in rt:
        return {
            "rhythm": "Asystole",
            "HR": 0.0,
            "pulse_rate": 0.0,
            "SpO2": 0.0,
            "ABP_sys": 0.0,
            "ABP_dia": 0.0,
            "MAP": 0.0,
            "avRR": 0.0,
            "etCO2": 0.0,
            "emd_pea": False,
        }
    elif "BRADY" in rt:
        return {
            "rhythm": "Sinus Bradycardia",
            "HR": 40.0,
            "pulse_rate": 40.0,
            "SpO2": 92.0,
            "ABP_sys": 90.0,
            "ABP_dia": 60.0,
            "MAP": 70.0,
            "avRR": 10.0,
            "etCO2": 35.0,
            "emd_pea": False,
        }
    elif "TACHY" in rt or "SVT" in rt:
        return {
            "rhythm": "SVT",
            "HR": 150.0,
            "pulse_rate": 150.0,
            "SpO2": 95.0,
            "ABP_sys": 100.0,
            "ABP_dia": 70.0,
            "MAP": 80.0,
            "avRR": 20.0,
            "etCO2": 38.0,
            "emd_pea": False,
        }
    else:
        return {
            "rhythm": "Sinus Rhythm",
            "HR": 75.0,
            "pulse_rate": 75.0,
            "SpO2": 98.0,
            "ABP_sys": 120.0,
            "ABP_dia": 80.0,
            "MAP": 93.0,
            "avRR": 14.0,
            "etCO2": 35.0,
            "emd_pea": False,
        }

@api_app.get("/api/scenario/list")
async def api_scenario_list(user: dict = Depends(get_current_user)):
    if not _scenario_gen:
        raise HTTPException(status_code=503, detail="Scenario generator not available")
    return {
        "levels": _scenario_gen.list_levels(),
        "locations": _scenario_gen.list_locations(),
        "specialities": _scenario_gen.list_specialities(),
        "disciplines": {
            "doctor": "Physician / Registrar",
            "nurse": "Staff Nurse / Charge Nurse",
            "physiotherapist": "Physiotherapist",
            "allied": "Allied Health Professional",
        },
    }

@api_app.post("/api/scenario/generate")
async def api_scenario_generate(body: dict, user: dict = Depends(require_instructor)):
    if not _scenario_gen:
        raise HTTPException(status_code=503, detail="Scenario generator not available")
    level = body.get("level", "beginner")
    location = body.get("location", "ER")
    discipline = body.get("discipline", ["doctor"])
    speciality = body.get("speciality", "ER")
    
    spec = _scenario_gen.generate(
        level=level, location=location,
        discipline=discipline, speciality=speciality,
    )
    spec["generation_mode"] = "guided_generator"
    spec["generation_request"] = {
        "level": level, "location": location,
        "discipline": discipline, "speciality": speciality,
    }
    expected = None
    if _outcome_pred:
        expected = _outcome_pred.build_expected(spec)
        
    return {"spec": spec, "expected_outcome": expected}

def parse_scenario_spec_to_vitals(spec: dict) -> dict:
    rhythm_type = spec.get("rhythm_type") or spec.get("rhythm") or "Sinus Rhythm"
    vitals = map_rhythm_type_to_vitals(rhythm_type)
    
    raw_vitals = spec.get("initial_vitals") or spec.get("vitals") or spec.get("initial_readings") or {}
    if not isinstance(raw_vitals, dict):
        raw_vitals = {}

    def get_val(keys):
        for k in keys:
            if k in raw_vitals and raw_vitals[k] is not None:
                return raw_vitals[k]
            if k in spec and spec[k] is not None:
                return spec[k]
        return None

    # Rhythm
    rhythm_val = get_val(["rhythm", "rhythm_type", "ecgRhythm"])
    if rhythm_val:
        vitals["rhythm"] = str(rhythm_val)

    # Heart rate
    hr_val = get_val(["heart_rate", "heartRate", "HR", "hr"])
    if hr_val is not None:
        try:
            val = float(hr_val)
            vitals["HR"] = val
            vitals["pulse_rate"] = val
        except (ValueError, TypeError):
            pass

    # SpO2
    spo2_val = get_val(["spo2", "SpO2", "SPO2"])
    if spo2_val is not None:
        try:
            vitals["SpO2"] = float(spo2_val)
        except (ValueError, TypeError):
            pass

    # Blood Pressure
    bp_sys = get_val(["sys_bp", "systolic_bp", "ABP_sys", "sysBP", "systolic"])
    bp_dia = get_val(["dia_bp", "diastolic_bp", "ABP_dia", "diaBP", "diastolic"])
    
    bp_obj = get_val(["bloodPressure", "blood_pressure"])
    if isinstance(bp_obj, dict):
        bp_sys = bp_sys or bp_obj.get("systolic") or bp_obj.get("sys")
        bp_dia = bp_dia or bp_obj.get("diastolic") or bp_obj.get("dia")
        
    if bp_sys is not None:
        try:
            v = float(bp_sys)
            vitals["ABP_sys"] = v
            vitals["NBP_sys"] = v
        except (ValueError, TypeError):
            pass

    if bp_dia is not None:
        try:
            v = float(bp_dia)
            vitals["ABP_dia"] = v
            vitals["NBP_dia"] = v
        except (ValueError, TypeError):
            pass

    if "ABP_sys" in vitals and "ABP_dia" in vitals and vitals["ABP_sys"] > 0:
        map_val = round((vitals["ABP_sys"] + 2 * vitals["ABP_dia"]) / 3.0, 1)
        vitals["MAP"] = map_val
        vitals["NBP_mean"] = map_val

    # Respiratory Rate
    rr_val = get_val(["resp_rate", "respiratory_rate", "respiratoryRate", "avRR", "RR", "rr"])
    if rr_val is not None:
        try:
            vitals["avRR"] = float(rr_val)
        except (ValueError, TypeError):
            pass

    # EtCO2
    etco2_val = get_val(["etco2", "etCO2", "ETCO2"])
    if etco2_val is not None:
        try:
            vitals["etCO2"] = float(etco2_val)
        except (ValueError, TypeError):
            pass

    # Temperature
    temp_val = get_val(["temperature", "Tblood", "temp", "blood_temperature"])
    if isinstance(temp_val, dict):
        temp_val = temp_val.get("bloodTemperature") or temp_val.get("blood") or temp_val.get("value")
    if temp_val is not None:
        try:
            v = float(temp_val)
            vitals["Tblood"] = v
            vitals["Tperi"] = round(v - 0.5, 1)
        except (ValueError, TypeError):
            pass

    # Cardiac Output
    co_val = get_val(["cardiac_output", "cardiacOutput", "CO"])
    if co_val is not None:
        try:
            vitals["CO"] = float(co_val)
        except (ValueError, TypeError):
            pass

    # PAP
    pap_sys = get_val(["pap_sys", "PAP_sys"])
    pap_dia = get_val(["pap_dia", "PAP_dia"])
    pap_obj = get_val(["pulmonaryArteryPressure", "pap"])
    if isinstance(pap_obj, dict):
        pap_sys = pap_sys or pap_obj.get("systolic")
        pap_dia = pap_dia or pap_obj.get("diastolic")

    if pap_sys is not None:
        try:
            vitals["PAP_sys"] = float(pap_sys)
        except (ValueError, TypeError):
            pass
    if pap_dia is not None:
        try:
            vitals["PAP_dia"] = float(pap_dia)
        except (ValueError, TypeError):
            pass

    return vitals

@api_app.post("/api/scenario/start")
async def api_scenario_start(body: dict, user: dict = Depends(require_instructor)):
    spec = body.get("spec", {})
    session_code = body.get("session_code")
    
    run_id = str(uuid.uuid4())
    _active_scenario_runs[run_id] = {
        "spec": spec,
        "started_at": datetime.utcnow().isoformat(),
        "status": "active"
    }
    
    if session_code:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
                session = await cur.fetchone()
                if session:
                    # Update sessions table with the scenario spec JSON
                    await cur.execute(
                        "UPDATE sessions SET current_scenario_json = %s, current_scenario_id = NULL WHERE id = %s",
                        (json.dumps(spec), session["id"])
                    )
                    
                    # Parse vitals from spec
                    # A generated scenario's first condition is its actual
                    # launch physiology.  Fall back to the loose vitals parser
                    # only for manually authored legacy scenario specs.
                    vitals = spec.get("initial_state") or parse_scenario_spec_to_vitals(spec)
                    
                    await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
                    state_row = await cur.fetchone()
                    if state_row:
                        state = json.loads(state_row["state_data"])
                        for k, v in vitals.items():
                            state[k] = v
                        state["initial_readings_hidden"] = True
                        state["last_updated"] = datetime.utcnow().isoformat()
                        state["updated_by"] = user.get("username", "")
                        
                        from socket_manager import sio, compute_alarms, _sync_waveform_engine
                        state["alarms"] = compute_alarms(state)
                        
                        await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
                        await _sync_waveform_engine(state, session_code)
                        
                        # Emit updates to SIO room
                        await sio.emit("state_update", state, room=session_code)
                        await sio.emit("rhythm_change", {
                            k: state.get(k) for k in
                            ["rhythm", "extrasystole", "HR", "ecg_lead",
                             "artifact_electrical", "artifact_muscular", "emd_pea"]
                        }, room=session_code)
                        
                        # Broadcast scenario_selected
                        await sio.emit("scenario_selected", spec, room=session_code)
                        
    return {"run_id": run_id, "status": "active"}

@api_app.post("/api/scenario/launch")
async def api_scenario_launch(body: dict, user: dict = Depends(require_instructor)):
    spec = body.get("spec", {})
    team_name = body.get("team_name", "Resus Team")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # End any existing active session for this instructor
            await cur.execute(
                "UPDATE sessions SET is_active = 0, ended_at = %s WHERE created_by = %s AND is_active = 1",
                (datetime.utcnow(), user["id"])
            )
            
            # Generate fresh session code
            code = _generate_code()
            launch_state = spec.get("initial_state") or parse_scenario_spec_to_vitals(spec)
            initial_event = {
                "event_id": f"scenario_start_{uuid.uuid4().hex}",
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"Launched scenario: {spec.get('title', 'Clinical Scenario')}",
                "event_type": "rhythm_change",
                "source": "simman",
                "actor_role": "instructor",
                "payload": {
                    "rhythm": launch_state.get("rhythm"),
                    "heart_rate": launch_state.get("HR"),
                    "pulse_present": bool(launch_state.get("pulse_rate", 0) > 0),
                    "emd_pea": bool(launch_state.get("emd_pea", False)),
                },
            }
            event_log = json.dumps([initial_event])
            
            # Checklist initialization
            raw_checklist = spec.get("checklist", [])
            formatted_checklist = []
            for idx, item in enumerate(raw_checklist):
                action = item.get("action", f"Action {idx+1}")
                formatted_checklist.append({
                    "id": f"chk_{idx+1:02d}",
                    "action": action,
                    "critical": bool(item.get("critical", False)),
                    "window_sec": int(item.get("window_sec", 60)),
                    "status": "pending",
                    "completed_at": None,
                    "delay_seconds": 0
                })
                
            init_condition_id = "initial"
            if spec.get("conditions"):
                init_condition_id = spec["conditions"][0].get("id", "initial")

            await cur.execute(
                """INSERT INTO sessions 
                   (session_code, created_by, started_at, is_active, event_log, history, current_scenario_json, team_name, checklist_state, current_condition_id) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (code, user["id"], datetime.utcnow(), True, event_log, json.dumps([]), json.dumps(spec), team_name, json.dumps(formatted_checklist), init_condition_id)
            )
            session_id = cur.lastrowid

            # Insert DB checklist table rows
            for chk in formatted_checklist:
                await cur.execute(
                    """INSERT INTO session_checklist (session_id, item_id, action, critical, window_sec, status)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (session_id, chk["id"], chk["action"], chk["critical"], chk["window_sec"], chk["status"])
                )

            # Build initial state from spec.initial_state or spec vitals
            state = dict(DEFAULT_MONITOR_STATE)
            initial_state_data = launch_state
            for k, v in initial_state_data.items():
                state[k] = v
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = user["username"]
            state["started_at"] = datetime.utcnow().isoformat()
            
            from socket_manager import sio, compute_alarms, _sync_waveform_engine
            state["alarms"] = compute_alarms(state)
            
            await cur.execute(
                "INSERT INTO monitor_state (session_id, state_data) VALUES (%s, %s)",
                (session_id, json.dumps(state))
            )
            # The trace websocket is driven by the waveform engine, not the
            # stored dashboard state.  Synchronise it before notifying clients
            # so a newly launched VF session never briefly renders as NSR.
            await _sync_waveform_engine(state, code)
            
            # Emit Socket.IO events to room
            await sio.emit("state_update", state, room=code)
            await sio.emit("rhythm_change", {
                k: state.get(k) for k in
                ["rhythm", "extrasystole", "HR", "ecg_lead",
                 "artifact_electrical", "artifact_muscular", "emd_pea"]
            }, room=code)
            await sio.emit("scenario_selected", spec, room=code)
            await sio.emit("checklist_updated", {"checklist": formatted_checklist}, room=code)

    return {"session_code": code, "message": "New scenario simulation session launched successfully"}

@api_app.post("/api/scenario/speak")
async def api_scenario_speak(body: dict, user: dict = Depends(get_current_user)):
    if not _narrator:
         raise HTTPException(status_code=503, detail="Voice narrator not available")
    text = body.get("text", "")
    speak_type = body.get("type", "custom")
    spec = body.get("spec")
    
    # We default to browser TTS to bypass server-side setup dependencies
    if speak_type == "intro" and spec:
        text = spec.get("narration_intro", "")
    
    return {"mode": "browser", "text": text}

@api_app.post("/api/scenario/narrate")
async def api_scenario_narrate(body: dict, user: dict = Depends(get_current_user)):
    spec = body.get("spec", {})
    text = spec.get("narration_intro", "")
    if not text:
        pt = spec.get("patient", {})
        text = (
            f"Attention team. {spec.get('level','').title()}-level scenario "
            f"in the {spec.get('location_label', 'hospital')}. "
            f"Patient: {pt.get('age','?')}-year-old {pt.get('sex','patient')}. "
            f"Presentation: {pt.get('presentation','cardiac arrest')}. You may begin."
        )
    return {"mode": "browser", "text": text}

@api_app.post("/api/scenario/instructor")
async def api_scenario_instructor(body: dict, user: dict = Depends(get_current_user)):
    if not _instructor:
         raise HTTPException(status_code=503, detail="Instructor listener not available")
    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
        
    params = _instructor.parse_text(text)
    params.setdefault("level", "beginner")
    params.setdefault("location", "ER")
    params.setdefault("speciality", "ER")
    params.setdefault("discipline", ["doctor"])
    
    spec = {}
    if _scenario_gen:
        spec = _scenario_gen.generate(
            level=params["level"],
            location=params["location"],
            discipline=params["discipline"],
            speciality=params["speciality"],
            rhythm_hint=params.get("rhythm_hint"),
        )
        # Preserve the instructor's original wording and parsed choices as
        # part of the scenario configuration.  It is retained with the
        # session and printed in the final PDF for auditability.
        spec["generation_mode"] = "instructor_authored"
        spec["instructor_request"] = text.strip()
        spec["parsed_request"] = params
    return {"parsed_params": params, "spec": spec}


# ── WebSocket (SimMan ECG Engine) ─────────────────────────────────

def _state_snapshot(waveform_engine=engine) -> str:
    """Return current engine state as a JSON STATE_SNAPSHOT string."""
    return json.dumps({
        "type": "STATE_SNAPSHOT",
        "payload": waveform_engine.state.model_dump(mode="json"),
    })

@api_app.websocket("/ws/ecg")
async def ws_ecg(websocket: WebSocket, session_code: str | None = Query(default=None)):
    await websocket.accept()
    print(f"[WS] Client connected: {websocket.client}")
    waveform_engine = get_session_engine(session_code)
    await waveform_engine.start()

    async def send_fn(data: bytes) -> None:
        await websocket.send_bytes(data)

    waveform_engine.add_client(send_fn)
    await websocket.send_text(_state_snapshot(waveform_engine))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"[WS] Bad JSON from client: {e}")
                continue

            msg_type = msg.get("type")

            if msg_type == "SET_STATE":
                payload = msg.get("payload", {})
                try:
                    update = ECGStateUpdate.model_validate(payload)
                except Exception as e:
                    print(f"[WS] SET_STATE validation error: {e}")
                    await websocket.send_text(json.dumps({"type": "ERROR", "message": f"Validation error: {e}"}))
                    continue

                try:
                    await waveform_engine.apply_command(update)
                except Exception as e:
                    print(f"[WS] apply_command error: {e}")
                    traceback.print_exc()
                    continue

                await websocket.send_text(_state_snapshot(waveform_engine))
                
                await websocket.send_text(json.dumps({
                    "type": "ECG_INTELLIGENCE",
                    "payload": intelligence_payload(waveform_engine.state.rhythm),
                }))

            elif msg_type == "GET_STATE":
                await websocket.send_text(_state_snapshot())
            elif msg_type == "PING":
                await websocket.send_text(json.dumps({"type": "PONG"}))
            else:
                print(f"[WS] Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {websocket.client}")
    except Exception as e:
        print(f"[WS] Unexpected crash: {e}")
        traceback.print_exc()
    finally:
        waveform_engine.remove_client(send_fn)


# ── Mount Socket.IO onto ASGI ─────────────────────────────────────

app = socketio.ASGIApp(sio, other_asgi_app=api_app)
