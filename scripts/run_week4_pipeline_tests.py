from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mathontospeak.pipeline import process_latex_to_audio


SAMPLE_PATH = ROOT / "data" / "sample_latex_equations.json"
REPORT_PATH = ROOT / "reports" / "tts_pipeline_test_results.md"
OUTPUT_ROOT = ROOT / "outputs"


def run() -> list[dict]:
    samples = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    results = []
    for sample in samples:
        result = process_latex_to_audio(
            latex=sample["latex"],
            context=f"{sample['domain']}. {sample.get('notes', '')}",
            surface_form="pedagogical",
            backend="mock",
            output_root=OUTPUT_ROOT,
            record_id=sample["id"],
        )
        result["domain"] = sample["domain"]
        result["expected_primary_concepts"] = sample["expected_primary_concepts"]
        results.append(result)

    pipeline_dir = OUTPUT_ROOT / "pipeline_tests"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = pipeline_dir / "week4_pipeline_test_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Week 4 TTS Pipeline Test Results",
        "",
        "Status: mock backend tested locally.",
        "",
        "Scope: 20 arXiv-style test equations across algebra, calculus, linear algebra, and probability/statistics.",
        "",
        "| ID | Domain | Status | Concepts | JSON | SSML | Audio/mock transcript |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            "| {id} | {domain} | {status} | {concept_count} | {json_gloss_path} | {ssml_path} | {audio_path} |".format(
                **result
            )
        )
    lines.extend(
        [
            "",
            "Known limitations:",
            "",
            "- Azure is Azure-ready but not deployed or tested unless AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are configured.",
            "- gTTS is gTTS-ready but may require network access and the gTTS package at runtime.",
            "- The LaTeX parser is an MVP symbol recognizer, not a full mathematical semantics parser.",
            "- These are 20 arXiv-style test equations; no real arXiv papers were downloaded by this runner.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    completed = run()
    ok_count = sum(1 for item in completed if item["status"] in {"ok", "warning"})
    print(f"Processed {len(completed)} equations with mock backend; {ok_count} completed.")
    print(f"Report: {REPORT_PATH}")
