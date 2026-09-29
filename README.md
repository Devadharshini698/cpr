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

For a normal local run, start native MySQL (or optionally Docker MySQL), then run the FastAPI and
Socket.IO service from `backend/` using `main:app`, and Vite from `frontend/`.
Open `http://localhost:3000`.

## Research prototype updates

Scenario Studio includes consented team prebrief introductions before launch.
Introductions are stored locally and are not clinical scoring evidence or
validated voice identity enrolment. The monitor supports manual NIBP measurement,
including unobtainable readings in pulseless states. Preliminary reports may be
shown while audio analysis continues; incomplete audio findings are labelled.

Whisper and pyannote 3.1 remain the supported audio path. Community-1 was tested
in a separate environment but is not integrated: a local 8 GB laptop exhausted
the experiment's memory safety margin. No speed or accuracy improvement was
established. All clinical scenarios and waveform morphology require instructor
validation before research use; this is not a clinical decision-making system.

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
