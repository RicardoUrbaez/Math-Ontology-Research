from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .concept_lookup import lookup_symbols
from .gloss_record import GlossRecord, load_gloss_records
from .latex_parser import parse_latex_symbols
from .ssml_builder import build_ssml
from .surface_forms import generate_surface_forms
from .tts_backends import get_tts_backend


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GLOSS_PATH = ROOT / "data" / "gloss_dictionary" / "gloss_records_50.json"
OUTPUT_ROOT = ROOT / "outputs"


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return cleaned[:80] or "equation"


def _record_map(records: list[GlossRecord]) -> dict[str, GlossRecord]:
    return {record.concept_iri: record for record in records}


def _selected_gloss_text(
    resolved_symbols: list[dict[str, Any]],
    record_by_iri: dict[str, GlossRecord],
    surface_form: str,
) -> tuple[str, list[dict[str, Any]]]:
    seen: set[str] = set()
    used: list[dict[str, Any]] = []
    phrases: list[str] = []
    for symbol in resolved_symbols:
        candidates = symbol.get("candidates") or []
        if not candidates:
            continue
        top = candidates[0]
        iri = top.get("concept_iri")
        if not iri or iri in seen:
            continue
        seen.add(iri)
        record = record_by_iri.get(iri)
        if not record:
            continue
        forms = generate_surface_forms(record)
        form_text = forms.get(surface_form) or forms["pedagogical_form"]
        phrases.append(form_text)
        used.append(
            {
                "symbol": symbol,
                "selected_candidate": top,
                "gloss_record": record.to_dict(),
                "surface_forms": forms,
            }
        )
    if not phrases:
        return "No ontology-backed concept gloss was found for this expression.", used
    return " ".join(phrases), used


def process_latex_to_audio(
    latex: str,
    context: str | None = None,
    surface_form: str = "pedagogical",
    backend: str = "mock",
    output_root: str | Path = OUTPUT_ROOT,
    record_id: str | None = None,
) -> dict[str, Any]:
    records = load_gloss_records(DEFAULT_GLOSS_PATH)
    record_by_iri = _record_map(records)
    symbols = parse_latex_symbols(latex)
    lookup_context = f"{context or ''} {latex}".strip()
    resolved_symbols = lookup_symbols(symbols, records=records, context=lookup_context)
    gloss_text, used_glosses = _selected_gloss_text(resolved_symbols, record_by_iri, surface_form)
    speech_text = f"LaTeX expression: {latex}. {gloss_text}"
    ssml_payload = build_ssml(speech_text)

    digest = hashlib.sha1(f"{record_id or ''}|{latex}|{surface_form}".encode("utf-8")).hexdigest()[:10]
    stem = _safe_stem(record_id or f"latex_{digest}")
    output_base = Path(output_root)
    json_dir = output_base / "json_glosses"
    ssml_dir = output_base / "ssml"
    audio_dir = output_base / "audio"
    for directory in (json_dir, ssml_dir, audio_dir, output_base / "pipeline_tests"):
        directory.mkdir(parents=True, exist_ok=True)

    ssml_path = ssml_dir / f"{stem}.ssml"
    ssml_path.write_text(ssml_payload["ssml"], encoding="utf-8")

    synthesis = get_tts_backend(backend).synthesize(
        ssml_payload["plain_text"],
        ssml_payload["ssml"],
        audio_dir / stem,
    )

    json_payload = {
        "id": stem,
        "latex": latex,
        "context": context,
        "surface_form": surface_form,
        "requested_backend": backend,
        "symbols": resolved_symbols,
        "glosses": used_glosses,
        "speech_text": ssml_payload["plain_text"],
        "ssml_path": str(ssml_path),
        "audio_path": synthesis.get("audio_path"),
        "synthesis": synthesis,
    }
    json_path = json_dir / f"{stem}.json"
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "id": stem,
        "status": synthesis.get("status", "unknown"),
        "latex": latex,
        "concept_count": len(used_glosses),
        "symbol_count": len(resolved_symbols),
        "json_gloss_path": str(json_path),
        "ssml_path": str(ssml_path),
        "audio_path": synthesis.get("audio_path"),
        "backend": synthesis.get("backend"),
        "detail": synthesis.get("detail"),
    }
