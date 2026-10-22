# Community-1 setup on a new Windows laptop

This guide enables the optional `pyannote/speaker-diarization-community-1`
speaker-separation worker in Final IMSR. GitHub contains the integration code,
not the model weights, your Hugging Face token, recordings, or reports. Follow
[SETUP_NEW_COMPUTER.md](SETUP_NEW_COMPUTER.md) first to install and run the
database, backend, frontend, and FFmpeg. Keep `backend/.env` private.

Community-1 separates *voices*. Whisper transcribes *words*. A prebrief
introduction can help link a voice to a declared team role, but neither the
voice match nor the transcript independently verifies a person's identity or
that a clinical action happened.

## 1. Get access to the model

1. Sign in to your own Hugging Face account.
2. On the [Community-1 model page](https://huggingface.co/pyannote/speaker-diarization-community-1),
   accept its access conditions while signed in. Access belongs to that
   account, not to this GitHub repository.
3. Create a **read** token (or an appropriately scoped fine-grained token) in
   [Hugging Face token settings](https://huggingface.co/settings/tokens). Save
   it privately. Do not paste it into GitHub, chat, screenshots, or a commit.

If Hugging Face returns 401/403, check that the token belongs to the *same*
account that accepted the model conditions and that it has model read access.

## 2. Install Community-1 in its own Python environment

Open a **new PowerShell** window in the cloned repository's root (`cpr`, the
folder containing `backend` and `frontend`). Check the base prerequisites:

```powershell
py -3.12 --version
ffmpeg -version
```

The application uses pyannote 3.x in its main `.venv`; Community-1 needs
pyannote 4.x in a **separate** environment. Do not install 4.x over the main
environment. A short path avoids Windows path-length problems:

```powershell
$communityVenv = Join-Path $env:USERPROFILE 'cpr-c1'
py -3.12 -m venv $communityVenv
$communityPython = Join-Path $communityVenv 'Scripts\python.exe'
& $communityPython -m pip install --upgrade pip
& $communityPython -m pip install -r backend\requirements-community.txt
& $communityPython -c "import pyannote.audio; print(pyannote.audio.__version__)"
```

The last command should print `4.0.7`. Downloads and installation can take
time and need free disk space. The model itself downloads on first use.

## 3. Configure the private backend environment

Open `backend/.env` in a local editor (create it from `backend/.env.example`
only on a fresh installation). Add or update these keys, using the *actual*
absolute path printed by `$communityPython` for your laptop:

```dotenv
HF_TOKEN=your_private_read_token
DIARIZATION_BACKEND=pyannote
DIARIZATION_MODEL=community-1
DEBRIEF_COMMUNITY_PYTHON=C:/Users/YourName/cpr-c1/Scripts/python.exe
DEBRIEF_COMMUNITY_DEVICE=cpu
DEBRIEF_COMMUNITY_HF_HOME=C:/Users/YourName/cpr-community-cache
DEBRIEF_WHISPER_MODEL=medium
```

Use forward slashes in the Windows paths above and replace `YourName`.
The cache directory must be writable. Do not copy another laptop's `.env`
or assume its Python path works here. `medium` is the baseline transcription
model; try `large-v3` only after measuring memory, speed, and accuracy on your
own recordings. Do not set `DEBRIEF_EXPECTED_SPEAKERS=6` unless you *know* a
particular recording contains six distinct voices.

## 4. Restart and test a **new** recording

Stop the existing backend with Ctrl+C in its PowerShell window, then start it
again from `backend`:

```powershell
cd backend
& ..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Keep this window open. If the port is occupied, do not start a second copy;
follow [the port instructions](SETUP_NEW_COMPUTER.md#start-each-time).
Start the frontend separately as described in the main setup guide.

Create a **new** test session, record a short clear conversation, stop the
microphone, end the session, and wait for audio processing to finish. The
debrief page should show transcript segments and audio processing status.
`Acoustic speaker separation completed` means diarization ran; review names,
roles, and words against the recording before using the report. The backend
log should show that it selected the Community-1 subprocess. Existing reports
are **not automatically reprocessed** when you change models.

For a role-matching trial, record one member's name and role at a time during
the prebrief, then have the same people speak during the simulation. The
system may still leave ambiguous speakers unbound. A six-person roster read
by one voice is not six voice enrollments.

## If something goes wrong

| Symptom | Check |
| --- | --- |
| `DEBRIEF_COMMUNITY_PYTHON` error | Confirm the configured `python.exe` exists and is the pyannote 4 environment, not the main `.venv`. |
| Hugging Face 401/403 | Accept the model conditions with the token's account; check token read scope. Do not expose the token while troubleshooting. |
| Audio saved but no acoustic speaker labels | Check the backend audio-job error and model-download/network status. The transcript may still be retained with unverified speaker labels. |
| Processing is very slow or runs out of memory | Test a shorter recording, keep `DEBRIEF_WHISPER_MODEL=medium` (or trial `small`), run one job at a time, and measure RAM. CPU use on a 10–20 minute recording can be slow. |
| Old report still shows legacy labels | Make a new recording; changing `.env` does not retroactively reprocess old sessions. |

Community-1 is an **optional experiment**, not a proven accuracy upgrade for
your team's room microphones. Compare the same consented recording against a
human-corrected transcript and speaker map before making it the default. See
[AUDIO_MODEL_EXPERIMENT.md](AUDIO_MODEL_EXPERIMENT.md) for the comparison plan.
