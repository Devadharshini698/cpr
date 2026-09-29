# Final IMSR: setup on another Windows computer

The integrated application is `backend/` plus `frontend/`. The nested
`cpr_debriefing_client/` is the legacy standalone application; do not start it
alongside the integrated backend.

## Prerequisites

Install Python 3.12, Node.js 22.12 or newer, Git, native MySQL 8 (or optionally
Docker Desktop for the bundled database), and an FFmpeg Windows binary build. Add FFmpeg's `bin` directory to
PATH and verify `ffmpeg -version` in a new PowerShell window.

## Install the source and dependencies

After the repository has been published:

```powershell
git clone https://github.com/Devadharshini698/cpr.git
cd cpr
py -3.12 -m venv .venv
cd backend
..\.venv\Scripts\python.exe -m pip install --upgrade pip
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m pip install -e ".[diarization,dev]"
Copy-Item .env.example .env
cd ..\frontend
npm ci
Copy-Item .env.example .env
cd ..
```

Only copy the environment examples on a fresh installation. Keep existing
configuration when updating an installation.

## Database and backend configuration

For native Windows MySQL, create a fresh local database and dedicated application
user using your database administration tool. Enter its host, port, database name
and credentials privately in `backend/.env`; do not reuse another laptop's
credentials. The application initializes its tables on startup. No Docker is
required with native MySQL. Never overwrite an existing database to try the app.

For a fresh local demonstration database, run from the project root:

```powershell
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps
```

The current development compose file creates database `imsr` with user `root`
and password `root` on port 3306. Set `backend/.env` accordingly:

```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
DB_NAME=imsr
MYSQL_SSL=false
```

These are local development defaults; use dedicated credentials and network
restrictions for deployment. Set `JWT_SECRET` to a new long random value. To
create demonstration users, set `ENABLE_DEMO_USERS=true` before starting the
backend. The instructor demonstration login is `instructor` / `instructor123`.
Disable demo seeding for deployment and use institution-managed accounts.

## Speech transcription and speaker diarization

Add `HF_TOKEN` privately to `backend/.env`. The Hugging Face account must accept
the access conditions for `pyannote/speaker-diarization-3.1` and
`pyannote/segmentation-3.0`. Never commit the token.

Whisper and diarization model files download on first use, requiring internet,
disk space and additional startup time. Test a short recording before a full
simulation. CPU processing can be substantially slower than this laptop; GPU
use additionally requires compatible CUDA, PyTorch and audio dependencies.
Do not assume equal latency across machines.

For a memory-constrained CPU laptop, set `DEBRIEF_WHISPER_MODEL=small` privately
instead of the example's `medium`. This is an accuracy/speed trade-off, especially
for Tamil/Tanglish; validate with consented, human-labelled recordings. Disk space
does not substitute for RAM. Test one recording at a time. Community-1 is not part
of this installation or a validated replacement for pyannote 3.1.

For optional Ollama narration, install Ollama on the new computer, run
`ollama pull qwen2.5:3b`, and set:

```dotenv
ENABLE_OLLAMA_DEBRIEF=true
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
```

Check `http://localhost:11434/api/tags`. With Ollama disabled, the engine can
generate its deterministic evidence-based report.

## Start each time

Start your native MySQL service (or Docker MySQL) first. In one terminal, from the project root:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal, from the project root:

```powershell
cd frontend
npm run dev
```

Open http://localhost:3000. Use `main:app` to include Socket.IO. Keep both
terminals open and use Ctrl+C to stop them. If port 8000 is occupied, identify
the existing backend before starting another instance.

If choosing port 8001 instead, use `--port 8001` and set
`VITE_BACKEND_URL=http://127.0.0.1:8001` in `frontend/.env`, then restart Vite.

## Verify before use

Run `..\.venv\Scripts\python.exe -m pytest tests -q` from `backend/` and
`npm run build` from `frontend/`. Launch a test session, record a short
conversation, stop recording, end the session and wait for processing. Confirm
the transcript appears in both the frontend and downloaded PDF, together with
the scenario configuration and actual simulator events.

## Existing sessions and recordings

A source checkout does not contain the original database, recordings, PDFs,
model caches or private `.env` files. A new local database starts empty.
Migrating existing sessions requires a separately authorized database export
and private transfer of `backend/uploads/` and report artifacts. Existing
database rows can contain absolute paths from the old computer; these must be
remapped to the new installation before old recordings/PDFs can be used.

Use a fresh local database on each test laptop. Do not connect to a cloud or
shared database without explicit authorization.

Fresh installation on the second computer still needs to be verified. The
dependency ranges are not a fully locked, platform-independent environment.
