"""Repeatable local audio test: transcribe, diarize, and inspect spoken events.

This diagnostic does not write a clinical score or modify a live session.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / "backend" / ".env")

from debriefing.analysis.event_extractor import EventExtractor
from debriefing.ingestion.audio_pipeline import AudioPipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", default="medium")
    parser.add_argument("--language", default="english")
    parser.add_argument("--session", default="AUDIO_TEST_01")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "audio_prototype_transcript.json")
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error(f"Audio file not found: {args.audio}")
    segments = AudioPipeline(whisper_model=args.model).process(
        str(args.audio), session_id=args.session, language_mode=args.language
    )
    events = EventExtractor().extract(segments)
    result = {
        "session_id": args.session,
        "audio_file": args.audio.name,
        "model": args.model,
        "language": args.language,
        "segments": segments,
        "speech_inferences": [event.to_dict() for event in events],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "segments": len(segments),
                      "speaker_labels": sorted({str(s.get("speaker_label")) for s in segments}),
                      "speech_inferences": len(events)}))


if __name__ == "__main__":
    main()
