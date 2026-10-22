# Comparing speech and speaker models

The current production baseline uses faster-whisper `medium` and pyannote
`speaker-diarization-3.1`. Both model choices are configured through environment
variables; no report or database schema change is required.

## Options

| Setting | Baseline | Trial |
|---|---|---|
| `DEBRIEF_WHISPER_MODEL` | `medium` | `large-v3` for Tamil/Tanglish; `large-v3-turbo` for English-only trials |
| `DIARIZATION_MODEL` | `legacy-3.1` | `community-1` |
| `DIARIZATION_BACKEND` | `pyannote` | `pyannote` |

The `large-v3-turbo` alias uses the faster-whisper CTranslate2 repository
`mobiuslabsgmbh/faster-whisper-large-v3-turbo`. Turbo is not trained for
translation. If Tamil/Tanglish translation is requested while Turbo is
selected, the pipeline uses Whisper medium for that task and records the
model actually used. Model files download into
`backend/uploads/model_cache/whisper` on first use. Leave `medium` as the
baseline until measured recordings show a benefit.

## Install Community-1 on Windows

Community-1 uses pyannote.audio 4.x, while the current 3.1 worker uses 3.x.
Install 4.x into a separate environment. On Windows, use a short path if the
project path is long; PyTorch wheel extraction can otherwise exceed the path
limit. This workstation uses `C:\Users\devad\Documents\Codex\c1`:

```powershell
python -m venv C:\path\to\c1
& C:\path\to\c1\Scripts\python.exe -m pip install --upgrade pip
& C:\path\to\c1\Scripts\python.exe -m pip install -r backend\requirements-community.txt
```

Install FFmpeg on PATH for audio preprocessing. The Community-1 worker reads
the resulting mono 16 kHz PCM WAV directly, avoiding TorchCodec's requirement
for FFmpeg shared DLLs on Windows. Sign in to Hugging Face and accept the access
conditions at <https://huggingface.co/pyannote/speaker-diarization-community-1>.
The existing `HF_TOKEN` in private `backend/.env` is passed to the isolated
worker through the process environment.

To try Community-1, add these lines to private `backend/.env` (use the actual
absolute path of the new environment):

```dotenv
DIARIZATION_MODEL=community-1
DEBRIEF_COMMUNITY_PYTHON=C:\path\to\c1\Scripts\python.exe
DEBRIEF_COMMUNITY_DEVICE=cpu
DEBRIEF_COMMUNITY_HF_HOME=C:\path\to\community-model-cache
DEBRIEF_WHISPER_MODEL=large-v3
# Only for a recording known to contain exactly six distinct voices:
DEBRIEF_EXPECTED_SPEAKERS=6
```

Restart the backend after editing `.env`. The report retains a transcript if
acoustic diarization fails; such labels are marked unverified. The model needs
an initial download and can be slow for a 10–20 minute session on CPU.
`DEBRIEF_COMMUNITY_HF_HOME` keeps the Community-1 cache separate from the
legacy worker's model cache and must be writable by the backend process.

## Compare on real sessions

Keep a copy of the source audio and a human-corrected transcript/role map.
Run the same recording once with the baseline and once with the trial settings.
Compare word errors in clinical terms, six-person speaker assignment, role
binding after introductions, omitted speech, and total processing time. Do
not infer clinical action from speech alone. Choose a new default only after
the trial improves the team's own noisy room recordings and meets the time
budget for debriefing.

This change does not retroactively reprocess old sessions. A newly submitted
recording is required to exercise the selected model.
