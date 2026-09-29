# Final IMSR — complete handoff for a second laptop

The active system is the top-level `backend/` plus `frontend/`; the nested
`cpr_debriefing_client/` is legacy and must not be started with it.

## Transfer and prerequisites

Clone this repository, or copy this complete `publish-final-imsr` folder if
GitHub is not reachable. This clean source copy intentionally excludes private
`.env` files, uploaded audio, database data, reports, model caches, virtual
environments, and `node_modules`.

Install Git, Python 3.12 x64, Node.js 22 LTS, native MySQL 8 or optional Docker
Desktop with WSL 2, and FFmpeg on PATH. For audio experiments, 25 GB free disk
and 16 GB RAM are recommended, not measured minimum requirements. Verify:

```powershell
git --version
py -3.12 --version
node --version
# Only if using Docker:
docker version
ffmpeg -version
```

## Install

```powershell
git clone https://github.com/Devadharshini698/cpr.git
cd cpr
py -3.12 -m venv .venv
cd backend
& ..\.venv\Scripts\python.exe -m pip install --upgrade pip
& ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
& ..\.venv\Scripts\python.exe -m pip install -e ".[diarization,dev]"
Copy-Item .env.example .env
cd ..\frontend
npm ci
Copy-Item .env.example .env
cd ..
# Skip this command when using native MySQL:
docker compose -f docker-compose.dev.yml up -d
```

In `backend/.env`, use local Docker values `MYSQL_HOST=127.0.0.1`,
`MYSQL_PORT=3306`, `MYSQL_USER=root`, `MYSQL_PASSWORD=root`, `DB_NAME=imsr`,
and set a new long `JWT_SECRET`. For live diarization add a private
`HF_TOKEN`, after accepting Hugging Face access conditions for
`pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`.

## Run

With your chosen local MySQL service running, start in two terminals:

```powershell
cd path\to\cpr\backend
& ..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
cd path\to\cpr\frontend
npm run dev
```

Open `http://localhost:3000`. `http://127.0.0.1:8000/docs` confirms backend
availability. For the complete acceptance test, data migration rules, Ollama
option and troubleshooting, read `SETUP_NEW_COMPUTER.md`.

For native MySQL, use a fresh local database and dedicated application user;
enter its credentials privately instead of the Docker example values above.
On an 8 GB CPU laptop, consider `DEBRIEF_WHISPER_MODEL=small` and validate audio
accuracy. Community-1 is not integrated. If backend port 8001 is needed, update
both the uvicorn command and `VITE_BACKEND_URL` in the private frontend env.

Do not expose secrets, automatically connect to a cloud database, or treat
low-confidence speech as proof of clinical actions.
