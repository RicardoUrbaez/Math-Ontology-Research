"""Run Whisper ASR quality checks over generated study audio."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import imageio_ffmpeg
import whisper
from jiwer import wer


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_MANIFEST = ROOT / "study/audio/mathontospeak_semantic/week4_latex_audio_gtts_manifest.json"
NOTATION_MANIFEST = ROOT / "study/audio/notation_only/notation_only_manifest.json"
DEFAULT_CSV = ROOT / "reports/evaluation/week6_whisper_asr_audio_qc.csv"
DEFAULT_MD = ROOT / "reports/evaluation/week6_whisper_asr_audio_qc.md"


@dataclass
class AudioCase:
    audio_id: str
    condition: str
    audio_path: Path
    expected_text: str
    concept_keywords: list[str]


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def strip_ssml(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    try:
        root = ET.fromstring(raw)
        parts = [text.strip() for text in root.itertext() if text and text.strip()]
        return " ".join(parts)
    except ET.ParseError:
        return re.sub(r"<[^>]+>", " ", raw)


def load_semantic_cases() -> list[AudioCase]:
    rows = json.loads(SEMANTIC_MANIFEST.read_text(encoding="utf-8"))
    cases: list[AudioCase] = []
    for row in rows:
        audio_path = ROOT / row["audio_path"]
        ssml_path = ROOT / row["ssml_path"]
        concepts = [str(item) for item in row.get("concepts", []) if str(item).strip()]
        cases.append(
            AudioCase(
                audio_id=row["arxiv_id"],
                condition="mathontospeak_semantic",
                audio_path=audio_path,
                expected_text=strip_ssml(ssml_path),
                concept_keywords=concepts,
            )
        )
    return cases


def load_notation_cases() -> list[AudioCase]:
    rows = json.loads(NOTATION_MANIFEST.read_text(encoding="utf-8"))
    cases: list[AudioCase] = []
    for row in rows:
        expected = row.get("spoken_text") or Path(ROOT / row["transcript_path"]).read_text(encoding="utf-8")
        cases.append(
            AudioCase(
                audio_id=row["stimulus_id"],
                condition="notation_only",
                audio_path=ROOT / row["audio_path"],
                expected_text=expected,
                concept_keywords=[],
            )
        )
    return cases


def keyword_recall(keywords: Iterable[str], transcript: str) -> tuple[int, int, float]:
    normalized_transcript = normalize_text(transcript)
    expected = [normalize_text(keyword) for keyword in keywords if normalize_text(keyword)]
    if not expected:
        return 0, 0, 0.0
    found = sum(1 for keyword in expected if keyword in normalized_transcript)
    return found, len(expected), found / len(expected)


def transcribe_cases(model_name: str, limit: int | None, include_notation: bool) -> list[dict[str, str]]:
    os.environ["PATH"] = ensure_ffmpeg_path() + os.pathsep + os.environ.get("PATH", "")
    model = whisper.load_model(model_name)

    cases = load_semantic_cases()
    if include_notation:
        cases.extend(load_notation_cases())
    if limit is not None:
        cases = cases[:limit]

    results: list[dict[str, str]] = []
    for case in cases:
        transcript = ""
        status = "ok"
        note = ""
        try:
            result = model.transcribe(str(case.audio_path), fp16=False)
            transcript = str(result.get("text", "")).strip()
        except Exception as exc:  # pragma: no cover - external ASR/runtime path
            status = "error"
            note = str(exc)

        expected_norm = normalize_text(case.expected_text)
        transcript_norm = normalize_text(transcript)
        row_wer = wer(expected_norm, transcript_norm) if expected_norm and transcript_norm else 1.0
        found, total, recall = keyword_recall(case.concept_keywords, transcript)
        if status == "ok" and not transcript:
            status = "empty_transcript"
        if status == "ok" and total:
            note = f"{found}/{total} concept keywords recognized"

        results.append(
            {
                "audio_id": case.audio_id,
                "condition": case.condition,
                "audio_path": str(case.audio_path.relative_to(ROOT)),
                "transcript_produced": str(bool(transcript)).lower(),
                "word_error_rate": f"{row_wer:.3f}",
                "concept_keywords_expected": "; ".join(case.concept_keywords),
                "concept_keywords_found": str(found),
                "concept_keywords_total": str(total),
                "concept_keyword_recall": f"{recall:.3f}",
                "expected_text": case.expected_text,
                "whisper_transcript": transcript,
                "status": status,
                "notes": note,
            }
        )
    return results


def ensure_ffmpeg_path() -> str:
    existing = shutil.which("ffmpeg")
    if existing:
        return str(Path(existing).parent)

    source = Path(imageio_ffmpeg.get_ffmpeg_exe())
    scripts_dir = ROOT / ".venv/Scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    target = scripts_dir / "ffmpeg.exe"
    if not target.exists():
        shutil.copy2(source, target)
    return str(scripts_dir)


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "audio_id",
        "condition",
        "audio_path",
        "transcript_produced",
        "word_error_rate",
        "concept_keywords_expected",
        "concept_keywords_found",
        "concept_keywords_total",
        "concept_keyword_recall",
        "expected_text",
        "whisper_transcript",
        "status",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]], path: Path, csv_path: Path, model_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok_rows = [row for row in rows if row["status"] == "ok"]
    produced = sum(1 for row in rows if row["transcript_produced"] == "true")
    wers = [float(row["word_error_rate"]) for row in rows if row["transcript_produced"] == "true"]
    recalls = [
        float(row["concept_keyword_recall"])
        for row in rows
        if int(row["concept_keywords_total"]) > 0 and row["transcript_produced"] == "true"
    ]
    mean_wer = statistics.mean(wers) if wers else 1.0
    mean_recall = statistics.mean(recalls) if recalls else 0.0

    lines = [
        "# Week 6 Whisper ASR Audio QC",
        "",
        "This report evaluates whether generated MathOntoSpeak study audio can be transcribed back into text by a Whisper-style ASR model.",
        "",
        "## Configuration",
        "",
        f"- Whisper model: `{model_name}`",
        f"- Reviewed audio files: {len(rows)}",
        f"- Successful ASR rows: {len(ok_rows)}",
        f"- Transcripts produced: {produced}/{len(rows)}",
        f"- Mean word error rate: {mean_wer:.3f}",
        f"- Mean semantic concept keyword recall: {mean_recall:.3f}",
        f"- CSV output: `{csv_path.relative_to(ROOT)}`",
        "",
        "## Interpretation",
        "",
        "Whisper is used here as an ASR intelligibility check, not as the MathOntoSpeak TTS engine. The project first generates semantic math audio, then ASR is used to test whether the audio can be recovered as text and whether important mathematical concept words remain recognizable.",
        "",
        "## Row Preview",
        "",
        "| Audio ID | Condition | Transcript | WER | Concept Recall | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows[:10]:
        transcript = row["whisper_transcript"].replace("|", "\\|")
        if len(transcript) > 80:
            transcript = transcript[:77] + "..."
        lines.append(
            f"| {row['audio_id']} | {row['condition']} | {transcript} | {row['word_error_rate']} | {row['concept_keyword_recall']} | {row['status']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Whisper ASR QC on generated study audio.")
    parser.add_argument("--model", default="tiny.en", help="Whisper model name. tiny.en is fast for local CPU checks.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of audio files for a quick smoke run.")
    parser.add_argument("--include-notation", action="store_true", help="Also transcribe notation-only study audio.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    rows = transcribe_cases(args.model, args.limit, args.include_notation)
    write_csv(rows, args.csv)
    write_markdown(rows, args.md, args.csv, args.model)
    print(f"Wrote {len(rows)} ASR rows to {args.csv}")
    print(f"Wrote Markdown summary to {args.md}")


if __name__ == "__main__":
    main()
