"""
ingestion/diarize_worker.py — Standalone pyannote GPU Worker
=============================================================
Runs in a SEPARATE PROCESS from the main AudioPipeline so that
pyannote's PyTorch CUDA runtime and CTranslate2's bundled CUDA runtime
do not conflict (Windows DLL namespace isolation).

Called by diarization._mode_b_pyannote() via subprocess.Popen().

Usage (internal — not called directly):
    python diarize_worker.py <wav_path> [num_speakers]  # HF_TOKEN inherited privately

Output:
    JSON array of speaker turns written to stdout, one JSON line:
    [{"speaker": "SPEAKER_00", "start_ms": 0, "end_ms": 1230}, ...]

Exit codes:
    0 — success, JSON on stdout
    1 — error, message on stderr
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: diarize_worker.py <wav_path> [num_speakers]", file=sys.stderr)
        sys.exit(1)

    wav_path    = sys.argv[1]
    hf_token    = os.environ.get("HF_TOKEN", "")
    num_speakers = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if not os.path.exists(wav_path):
        print(f"[diarize_worker] File not found: {wav_path}", file=sys.stderr)
        sys.exit(1)

    # pyannote 3.1 references the NumPy 1.x spelling while this project uses
    # NumPy 2.x.  Apply the compatibility alias before importing pyannote.
    import numpy as np
    if not hasattr(np, "NaN"):
        np.NaN = np.nan
    if not hasattr(np, "NAN"):
        np.NAN = np.nan

    # pyannote 3.1 supplies the now-renamed ``use_auth_token`` parameter to
    # huggingface_hub.  Translate it locally so the worker can load the gated
    # model with current Hub clients.
    import huggingface_hub as huggingface_hub
    original_download = huggingface_hub.hf_hub_download
    def compatible_download(*args, use_auth_token=None, **kwargs):
        if use_auth_token is not None:
            kwargs.setdefault("token", use_auth_token)
        return original_download(*args, **kwargs)
    huggingface_hub.hf_hub_download = compatible_download

    # ── Device selection ───────────────────────────────────────────────────────
    # This runs in its own process → no CTranslate2 DLLs loaded → safe to use GPU
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ── Load pyannote ──────────────────────────────────────────────────────────
    from pyannote.audio import Pipeline
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )
    pipeline.to(torch.device(device))

    # ── Run diarization ────────────────────────────────────────────────────────
    kwargs: dict = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    else:
        kwargs["min_speakers"] = 1
        kwargs["max_speakers"] = 6

    diarization = pipeline(wav_path, **kwargs)

    # ── Emit JSON turns to stdout ──────────────────────────────────────────────
    turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append({
            "speaker":  speaker,
            "start_ms": int(turn.start * 1000),
            "end_ms":   int(turn.end   * 1000),
        })

    print(json.dumps(turns))   # single JSON line on stdout
    sys.exit(0)


if __name__ == "__main__":
    main()
