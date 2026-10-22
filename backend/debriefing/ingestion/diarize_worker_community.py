"""Isolated pyannote.audio 4 worker for Community-1 speaker diarization.

The legacy pyannote 3.1 pipeline runs in the application's Python environment.
This worker can run in a separate Python environment selected with
DEBRIEF_COMMUNITY_PYTHON, so its pyannote 4 dependencies do not replace the
legacy pipeline. HF_TOKEN is inherited through the environment, never argv.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import wave


def _load_preprocessed_wav(path: str):
    """Load the mono 16 kHz PCM produced by Whisper without TorchCodec DLLs."""
    import numpy as np
    import torch

    with wave.open(path, "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getframerate() != 16000:
            raise ValueError("Community-1 requires a mono 16 kHz 16-bit PCM WAV")
        samples = source.readframes(source.getnframes())
    waveform = torch.from_numpy(np.frombuffer(samples, dtype="<i2").astype("float32") / 32768.0)
    return {"waveform": waveform.unsqueeze(0), "sample_rate": 16000}


def _turns_from_output(output) -> list[dict]:
    """Use exclusive turns to align each Whisper segment to one speaker."""
    diarization = getattr(output, "exclusive_speaker_diarization", None)
    if diarization is None:
        diarization = output.speaker_diarization
    if hasattr(diarization, "itertracks"):
        entries = ((turn, speaker) for turn, _, speaker in diarization.itertracks(yield_label=True))
    else:
        entries = iter(diarization)
    turns = [
        {"speaker": str(speaker), "start_ms": round(turn.start * 1000), "end_ms": round(turn.end * 1000)}
        for turn, speaker in entries
    ]
    return sorted(turns, key=lambda turn: (turn["start_ms"], turn["end_ms"]))


def _enrollment_embedding(pipeline, audio_path: str):
    """Embed a single-speaker introduction with Community-1's own encoder."""
    import numpy as np
    import torch

    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg is required to decode prebrief introductions')
    decoded = subprocess.run(
        [ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', audio_path,
         '-ac', '1', '-ar', '16000', '-t', '30', '-f', 's16le', 'pipe:1'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90, check=True,
    ).stdout
    samples = np.frombuffer(decoded, dtype='<i2').astype('float32') / 32768.0
    if len(samples) < 3 * 16000 or float(np.sqrt(np.mean(samples * samples))) < 0.005:
        raise ValueError('Introduction is too short or silent for a voice match')
    waveform = torch.from_numpy(samples.copy()).reshape(1, 1, -1)
    with torch.inference_mode():
        embedding = pipeline._embedding(waveform)[0]
    return np.asarray(embedding, dtype='float32')


def _match_enrollments(output, clips: list[dict], pipeline) -> dict[str, dict]:
    """One-to-one, mutual-best voice matching; ambiguous voices stay unbound.

    Thresholds are conservative pilot defaults, not calibrated probabilities.
    The score is a cosine similarity, not a clinical or identity confidence.
    """
    import numpy as np

    centroids = getattr(output, 'speaker_embeddings', None)
    if centroids is None or not clips:
        return {}
    labels = output.speaker_diarization.labels()
    if len(labels) != len(centroids):
        return {}
    enrollment = []
    valid_clips = []
    for clip in clips:
        try:
            embedding = _enrollment_embedding(pipeline, clip['path'])
            if np.all(np.isfinite(embedding)) and np.linalg.norm(embedding) > 0:
                enrollment.append(embedding)
                valid_clips.append(clip)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError) as exc:
            print(f"Skipping unusable prebrief clip: {type(exc).__name__}", file=sys.stderr)
    if not enrollment:
        return {}
    a, b = np.asarray(centroids, dtype='float32'), np.asarray(enrollment, dtype='float32')
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[1]:
        return {}
    valid_speakers = np.all(np.isfinite(a), axis=1) & (np.linalg.norm(a, axis=1) > 1e-8)
    if not np.any(valid_speakers):
        return {}
    a /= np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-8)
    b /= np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-8)
    scores = a @ b.T
    result = {}
    for speaker_index, label in enumerate(labels):
        if not valid_speakers[speaker_index]:
            continue
        clip_index = int(np.argmax(scores[speaker_index]))
        score = float(scores[speaker_index, clip_index])
        other_clips = [float(value) for index, value in enumerate(scores[speaker_index]) if index != clip_index]
        other_speakers = [float(scores[index, clip_index]) for index in range(len(labels))
                          if index != speaker_index and valid_speakers[index]]
        if (score < 0.72 or (other_clips and score - max(other_clips) < 0.08)
                or (other_speakers and score - max(other_speakers) < 0.08)):
            continue
        clip = valid_clips[clip_index]
        result[str(label)] = {'name': clip['name'], 'role': clip['role'], 'score': round(score, 3)}
    return result


def main() -> int:
    if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
        print("Usage: diarize_worker_community.py <wav_path> [num_speakers]", file=sys.stderr)
        return 1

    token = os.getenv("HF_TOKEN")
    if not token:
        print("HF_TOKEN is required for Community-1", file=sys.stderr)
        return 1

    # The API may set a different cache for its legacy pyannote environment.
    # Select this worker's cache before importing pyannote/huggingface_hub.
    community_cache = os.getenv("DEBRIEF_COMMUNITY_HF_HOME", "").strip()
    if community_cache:
        os.environ["HF_HOME"] = community_cache
        os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(community_cache, "hub")
        os.environ.setdefault("MPLCONFIGDIR", os.path.join(community_cache, "matplotlib"))

    from pyannote.audio import Pipeline
    import torch

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=token)
    device = os.getenv("DEBRIEF_COMMUNITY_DEVICE", "cpu").lower()
    if device not in {"cpu", "cuda"}:
        print("DEBRIEF_COMMUNITY_DEVICE must be cpu or cuda", file=sys.stderr)
        return 1
    if device == "cuda" and not torch.cuda.is_available():
        print("CUDA requested but unavailable", file=sys.stderr)
        return 1
    if device == "cuda":
        pipeline.to(torch.device("cuda"))

    positional = [arg for arg in sys.argv[2:] if arg != '--enrollment-manifest']
    clips = []
    if '--enrollment-manifest' in sys.argv:
        index = sys.argv.index('--enrollment-manifest')
        if index + 1 >= len(sys.argv):
            raise ValueError('Missing enrollment manifest path')
        with open(sys.argv[index + 1], encoding='utf-8') as source:
            clips = json.load(source)
        positional = sys.argv[2:index]
    kwargs = {"num_speakers": int(positional[0])} if positional else {"min_speakers": 1, "max_speakers": 6}
    output = pipeline(_load_preprocessed_wav(sys.argv[1]), **kwargs)
    turns = _turns_from_output(output)
    if clips:
        print(json.dumps({'turns': turns, 'enrollment_matches': _match_enrollments(output, clips, pipeline)}))
    else:
        print(json.dumps(turns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
