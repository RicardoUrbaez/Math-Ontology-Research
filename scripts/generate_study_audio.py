from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def synthesize_gtts(text: str, output_path: Path) -> dict[str, Any]:
    try:
        from gtts import gTTS

        output_path.parent.mkdir(parents=True, exist_ok=True)
        gTTS(text=text, lang="en").save(str(output_path))
        return {"status": "ok", "audio_path": str(output_path), "detail": "gTTS MP3 written"}
    except Exception as exc:
        fallback = output_path.with_suffix(".txt")
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(text, encoding="utf-8")
        return {
            "status": "warning",
            "audio_path": str(fallback),
            "detail": f"gTTS failed; wrote transcript fallback: {exc}",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate notation-only study audio.")
    parser.add_argument("--stimuli", type=Path, default=Path("study/stimuli/study_stimuli.csv"))
    parser.add_argument("--out", type=Path, default=Path("study/audio/notation_only"))
    args = parser.parse_args()

    rows = list(csv.DictReader(args.stimuli.open(newline="", encoding="utf-8")))
    audio_dir = args.out / "mp3"
    transcript_dir = args.out / "transcripts"
    manifest: list[dict[str, Any]] = []

    for row in rows:
        stimulus_id = row["stimulus_id"]
        text = row["notation_reading"]
        output_path = audio_dir / f"{stimulus_id}_notation_only.mp3"
        result = synthesize_gtts(text, output_path)
        transcript_path = transcript_dir / f"{stimulus_id}_notation_only.txt"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(text, encoding="utf-8")
        manifest.append(
            {
                "stimulus_id": stimulus_id,
                "condition": "notation_only",
                "domain": row["domain"],
                "difficulty": row["difficulty"],
                "latex": row["latex"],
                "spoken_text": text,
                "audio_path": result["audio_path"],
                "transcript_path": str(transcript_path),
                "status": result["status"],
                "detail": result["detail"],
            }
        )

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "notation_only_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest)} notation-only audio artifacts to {args.out}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()

