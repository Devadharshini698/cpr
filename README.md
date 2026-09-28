# Final IMSR

Final IMSR is a cardiac-resuscitation simulation and debriefing application. It
combines a live patient monitor, instructor-controlled scenario states,
structured simulator events, microphone recording, speech transcription,
speaker diarization, and evidence-based debrief reports with PDF export.

The integrated application is in `backend/` and `frontend/`. The nested
`cpr_debriefing_client/` directory is retained as a legacy standalone reference
and is not started with the integrated application.

## Run locally

See [SETUP_NEW_COMPUTER.md](SETUP_NEW_COMPUTER.md) for prerequisites, private
configuration, database setup, microphone/diarization requirements, and the
exact Windows start commands.

For a normal local run, start MySQL with Docker, then run the FastAPI and
Socket.IO service from `backend/` using `main:app`, and Vite from `frontend/`.
Open `http://localhost:3000`.

## Privacy and repository contents

This repository intentionally excludes `.env` files, database data, recordings,
generated reports, model caches, and dependency folders. Copy `.env.example`
files locally and enter credentials such as `HF_TOKEN` privately. Do not commit
those credentials or real simulation recordings.

## Validation

From `backend/`, run:

```powershell
..\.venv\Scripts\python.exe -m pytest tests -q
```

From `frontend/`, run:

```powershell
npm run build
```
