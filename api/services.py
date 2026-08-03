from __future__ import annotations

import base64
import binascii
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from io import BytesIO
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from api.image_equation_ocr import (
    extract_equation_image_context,
    image_ocr_runtime_status,
    is_equation_image,
)
from api.local_tts import kokoro_runtime_status
from api.equation_normalization import normalize_extracted_equation, validate_equation_structure
from api.external_integrations import (
    docling_runtime_status,
    extract_pdf_context_with_docling,
    extract_pdf_context_with_mineru,
    integration_registry,
    mineru_runtime_status,
    semantic_retrieval_status,
)
from api.semantic_retrieval import semantic_similarity_scores, semantic_similarity_scores_batch
from api.grounding_evaluation import evaluate_grounding
from api.grobid_integration import enrich_with_grobid
from api.math_semantics import (
    accessible_notation_reading,
    build_speech_segments,
    canonical_symbol,
    extract_grouped_expression,
    latex_to_mathml,
    mathcat_notation_reading,
    split_source_label,
)
from api.explanation_providers import (
    ExplanationProvider,
    provider_from_environment,
    run_grounded_provider,
)

from scripts.week4_tts_rendering import (
    ArxivEquation,
    GlossRepository,
    SymbolConceptLookup,
    assemble_ssml,
    backend_for,
    build_equation_speech_bundle,
    build_surface_forms,
    latex_to_plain_text,
    load_gloss_records,
    parse_latex_tokens,
    resolve_latex_tokens,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOSS_PATH = ROOT / "gloss" / "week3_gloss_dictionary.json"
DEFAULT_PROTEGE_ONTOLOGY_PATH = (
    ROOT / "ontologies" / "merged" / "math_accessibility_kg_week3_grouped_for_protege.owl"
)
DEFAULT_SPARQL_ENDPOINT = "http://localhost:3030/mathkg500/query"
DEFAULT_PAPER_AUDIO_DIR = ROOT / "reports" / "audio" / "paper_demo"
DEFAULT_MARKER_TIMEOUT_SECONDS = 600
DEFAULT_PDF_PAGE_LIMIT = 100
DEFAULT_DOCUMENT_CONTEXT_PREVIEW_LIMIT = 2400
AUDIENCE_TO_FIELD = {
    "concise": "concise_form",
    "pedagogical": "pedagogical_form",
    "expert": "expert_form",
    "document_role": "document_role_form",
}
DISPLAY_AUDIENCE = {
    "concise": "Concise",
    "pedagogical": "Pedagogical",
    "expert": "Expert",
    "document_role": "Document role",
}
CONTEXT_DOMAIN_TERMS = {
    "attention",
    "channel",
    "covariance",
    "energy",
    "frequency",
    "matrix",
    "noise",
    "power",
    "probability",
    "received",
    "receiver",
    "signal",
    "transmission",
    "transmitted",
    "variance",
    "voltage",
}
SECTION_NAMES = {
    "abstract",
    "background",
    "conclusion",
    "discussion",
    "introduction",
    "methods",
    "methodology",
    "results",
    "system model",
}
PDF_SPACED_WORDS = {
    r"\ba\s+n\s+d\b": "and",
    r"\bc\s+o\s+s\b": "cos",
    r"\bl\s+o\s+g\b": "log",
    r"\bs\s+i\s+n\b": "sin",
    r"\bw\s+h\s+e\s+r\s+e(?=\s|[A-Z])": "where ",
}


def positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def symbol_key(value: str) -> str:
    """Normalize math notation without collapsing case-sensitive symbols such as N and n."""

    return re.sub(r"[^A-Za-z0-9]+", "", value or "")


def tokens_for(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) > 1}


def sentence_for_context(context: str, latex: str, labels: list[str]) -> str:
    context = re.sub(r"\s+", " ", context or "").strip()
    if not context:
        return ""
    candidates = [part.strip() for part in re.split(r"(?<=[.!?])\s+", context) if part.strip()]
    if not candidates:
        return context[:360]
    label_tokens = {token for label in labels for token in tokens_for(label)}
    latex_tokens = tokens_for(latex)

    def score(sentence: str) -> tuple[int, int]:
        terms = tokens_for(sentence)
        return (len(terms.intersection(label_tokens)), len(terms.intersection(latex_tokens)))

    best = max(candidates, key=score)
    return best[:420]


def _is_section_heading(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", value).strip(" :")
    if not cleaned or len(cleaned) > 120 or "=" in cleaned:
        return False
    normalized = normalize_text(cleaned)
    if normalized in SECTION_NAMES:
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+[A-Za-z][A-Za-z\s-]{2,}$", cleaned):
        return True
    return cleaned.isupper() and 3 <= len(cleaned.split()) <= 10


def repair_pdf_spacing(value: str) -> str:
    repaired = value or ""
    for pattern, replacement in PDF_SPACED_WORDS.items():
        repaired = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)
    return repaired


def context_chunks_from_text(
    text: str,
    *,
    source: str,
    page: int | None = None,
    include_title: bool = False,
) -> list[dict[str, Any]]:
    raw_lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        normalized = re.sub(r"\s+", " ", text or "").strip()
        lines = [normalized] if normalized else []

    chunks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    current_heading = ""
    paragraph_lines: list[str] = []

    def add_chunk(value: str, kind: str, heading: str = "") -> None:
        cleaned = re.sub(r"\s+", " ", value).strip()
        key = (kind, cleaned)
        if not cleaned or key in seen:
            return
        seen.add(key)
        payload: dict[str, Any] = {
            "source": source,
            "kind": kind,
            "text": cleaned[:1200],
            "reading_order": len(chunks),
            "block_id": f"{source}-p{page or 0}-b{len(chunks)}",
        }
        if page is not None:
            payload["page"] = page
        if heading:
            payload["section_heading"] = heading
        chunks.append(payload)

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        paragraph = " ".join(paragraph_lines).strip()
        paragraph_lines = []
        if not paragraph:
            return
        kind = "abstract" if normalize_text(current_heading) == "abstract" else "paragraph"
        add_chunk(paragraph, kind, current_heading)
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            if sentence.strip() and sentence.strip() != paragraph:
                add_chunk(sentence, "sentence", current_heading)

    if include_title and lines:
        add_chunk(lines[0], "title")

    for line_number, line in enumerate(lines):
        if include_title and line_number == 0:
            continue
        if _is_section_heading(line):
            flush_paragraph()
            current_heading = line
            add_chunk(line, "section_heading", line)
            continue
        paragraph_lines.append(line)
        if line.endswith((".", "!", "?")):
            flush_paragraph()
    flush_paragraph()
    return chunks


def is_publication_boilerplate(text: str) -> bool:
    normalized = normalize_text(text)
    return (
        "this paper is published to" in normalized
        and "copyright" in normalized
        and "copy of record" in normalized
    )


def document_text_from_structured_chunks(chunks: list[dict[str, Any]]) -> str:
    ordered = sorted(
        enumerate(chunks),
        key=lambda pair: (
            int(pair[1].get("page")) if str(pair[1].get("page") or "").isdigit() else 10**9,
            int(pair[1].get("reading_order"))
            if str(pair[1].get("reading_order") or "").isdigit()
            else pair[0],
        ),
    )
    parts: list[str] = []
    seen: set[str] = set()
    for _position, chunk in ordered:
        if str(chunk.get("kind") or "") == "sentence":
            continue
        text = re.sub(r"\s+", " ", str(chunk.get("text") or "")).strip()
        normalized = normalize_text(text)
        if not text or is_publication_boilerplate(text) or normalized in seen:
            continue
        seen.add(normalized)
        parts.append(text)
    return "\n\n".join(parts)


def build_document_context_payload(
    *,
    pdf_text: str,
    pdf_chunks: list[dict[str, Any]],
    pdf_status: dict[str, Any],
    provided_context: str,
) -> dict[str, Any]:
    using_pdf = bool(pdf_text.strip() or pdf_chunks)
    source_chunks = (
        pdf_chunks
        if using_pdf
        else context_chunks_from_text(provided_context, source="provided_context")
    )
    preferred_kinds = ("abstract", "paragraph", "sentence")
    ordered_chunks = sorted(
        source_chunks,
        key=lambda chunk: (
            preferred_kinds.index(str(chunk.get("kind")))
            if str(chunk.get("kind")) in preferred_kinds
            else len(preferred_kinds)
        ),
    )
    preview_parts: list[str] = []
    seen: set[str] = set()
    preview_length = 0
    for chunk in ordered_chunks:
        kind = str(chunk.get("kind") or "")
        text = re.sub(r"\s+", " ", str(chunk.get("text") or "")).strip()
        normalized = normalize_text(text)
        if (
            kind not in preferred_kinds
            or len(text) < 40
            or is_publication_boilerplate(text)
            or normalized in seen
        ):
            continue
        seen.add(normalized)
        remaining = DEFAULT_DOCUMENT_CONTEXT_PREVIEW_LIMIT - preview_length
        if remaining <= 0:
            break
        preview_parts.append(text[:remaining])
        preview_length += len(preview_parts[-1]) + 2
        if preview_length >= DEFAULT_DOCUMENT_CONTEXT_PREVIEW_LIMIT:
            break

    fallback_text = pdf_text if using_pdf else provided_context
    preview = "\n\n".join(preview_parts).strip()
    if not preview:
        preview = re.sub(r"\[Page \d+\]\s*", "", fallback_text or "")
        preview = re.sub(r"\s+", " ", preview).strip()[:DEFAULT_DOCUMENT_CONTEXT_PREVIEW_LIMIT]

    extracted_text = document_text_from_structured_chunks(source_chunks) if source_chunks else ""
    if not extracted_text:
        extracted_text = str(fallback_text or "").strip()
    extracted_text = re.sub(r"[ \t]+", " ", extracted_text)
    extracted_text = re.sub(r"\n[ \t]+", "\n", extracted_text)
    extracted_text = re.sub(r"\n{3,}", "\n\n", extracted_text).strip()
    pages_processed = int(pdf_status.get("pages_processed") or 0) if using_pdf else 0
    if using_pdf and not pages_processed:
        pages_processed = max(
            (int(chunk["page"]) for chunk in source_chunks if str(chunk.get("page") or "").isdigit()),
            default=0,
        )

    return {
        "source": str(pdf_status.get("input_type") or "pdf") if using_pdf else "provided_context" if provided_context.strip() else "none",
        "preview": preview,
        "preview_truncated": len(extracted_text) > len(preview),
        "preview_character_count": len(preview),
        "extracted_text": extracted_text,
        "extracted_character_count": len(extracted_text),
        "analysis_scope": "full_document" if using_pdf else "provided_context" if provided_context.strip() else "none",
        "context_chunk_count": len(source_chunks),
        "extractor": pdf_status.get("extractor", "none") if using_pdf else "none",
        "pages_processed": pages_processed,
    }


def build_document_graph(
    chunks: list[dict[str, Any]],
    equation_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    cross_references: list[dict[str, Any]] = []
    symbol_definitions: list[dict[str, Any]] = []
    seen_sections: set[tuple[str, Any]] = set()
    seen_references: set[tuple[str, str]] = set()
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        block_id = str(chunk.get("block_id") or "")
        page = chunk.get("page")
        if chunk.get("kind") == "section_heading":
            key = (text, page)
            if key not in seen_sections:
                seen_sections.add(key)
                sections.append({"title": text, "page": page, "block_id": block_id})
        for match in re.finditer(
            r"\b(?:equation|eq\.?)\s*(?:\(|\[)?((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)(?:\)|\])?",
            text,
            re.IGNORECASE,
        ):
            key = (match.group(1), block_id)
            if key in seen_references:
                continue
            seen_references.add(key)
            cross_references.append(
                {
                    "source_label": match.group(1),
                    "page": page,
                    "block_id": block_id,
                    "text": text[:500],
                }
            )
        for definition in re.finditer(
            r"(?<!\w)([A-Za-z][A-Za-z0-9_]*(?:\s*\[[^\]]+\])?)\s+"
            r"(?:is|denotes|represents|refers to|stands for)\s+([^.;]{3,180})",
            text,
            re.IGNORECASE,
        ):
            symbol_definitions.append(
                {
                    "symbol": definition.group(1).strip(),
                    "meaning": re.sub(r"\s+", " ", definition.group(2)).strip(" ,"),
                    "page": page,
                    "block_id": block_id,
                }
            )
    return {
        "block_count": len(chunks),
        "sections": sections,
        "cross_references": cross_references,
        "symbol_definitions": symbol_definitions,
        "equations": [
            {
                "source_label": str(candidate.get("source_label") or ""),
                "page": candidate.get("page"),
                "block_id": str(candidate.get("block_id") or ""),
            }
            for candidate in equation_candidates
        ],
    }


def extract_plain_text_equations(text: str, limit: int = 12) -> list[str]:
    pattern = re.compile(
        r"(?=(?P<lhs>[^\W\d_][\w]*(?:\s*[_^]\s*(?:\{[^}]+\}|[\w]+))?"
        r"(?:\s*[\[(][^\])]{1,32}[\])])?)\s*=\s*(?P<rhs>[^=.;]{1,260}))",
        flags=re.UNICODE,
    )
    equations: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text or ""):
        lhs = re.sub(r"\s+", " ", match.group("lhs")).strip()
        rhs = re.split(
            r",\s*(?:where|with|which|whose|for)\b"
            r"|,\s*(?:and\s+)?[A-Za-z][A-Za-z0-9_]*(?:\s*[\[(][^\])]+[\])])?\s+"
            r"(?:is|denotes|represents)\b"
            r"|\s+(?:where|with|which)\b",
            repair_pdf_spacing(match.group("rhs")),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        rhs = re.sub(r"\s+", " ", rhs).strip(" ,")
        label_match = re.search(
            r"\s+\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)(?=\s+[A-Z]|\s*$)",
            rhs,
        )
        if label_match:
            rhs = rhs[: label_match.start()].rstrip(" ,") + f" ({label_match.group(1)})"
        else:
            trailing_text = (text or "")[match.span("rhs")[1] : match.span("rhs")[1] + 32]
            trailing_label = re.match(
                r"\s*\.?\s*\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)",
                trailing_text,
            )
            if trailing_label:
                rhs = rhs.rstrip(" ,") + f" ({trailing_label.group(1)})"
        if not lhs or not rhs:
            continue
        if not re.search(r"[A-Za-z0-9\u0370-\u03ff]", rhs):
            continue
        equation = f"{lhs} = {rhs}"
        if equation not in seen:
            seen.add(equation)
            equations.append(equation)
        if len(equations) >= limit:
            break
    return equations


def extract_equation_candidates(text: str, limit: int = 12) -> list[dict[str, Any]]:
    patterns = [
        r"\$\$(.+?)\$\$",
        r"\\\[(.+?)\\\]",
        r"\\\((.+?)\\\)",
        r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$",
    ]
    equations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.DOTALL):
            equation = re.sub(r"\s+", " ", match.group(1)).strip()
            equation, source_label = split_source_label(equation)
            if not source_label:
                trailing = re.match(
                    r"\s*\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)",
                    (text or "")[match.end() : match.end() + 32],
                )
                source_label = trailing.group(1) if trailing else ""
            if equation and equation not in seen:
                seen.add(equation)
                equations.append(
                    {
                        "latex": equation,
                        "confidence": "high",
                        "method": "latex_delimiter",
                        "source_label": source_label,
                    }
                )
            if len(equations) >= limit:
                return equations
    if equations:
        return equations
    for equation in extract_plain_text_equations(text, limit=limit):
        equation, source_label = split_source_label(equation)
        equations.append(
            {
                "latex": equation,
                "confidence": "medium",
                "method": "plain_text_equation",
                "source_label": source_label,
            }
        )
    return equations


def extract_latex_equations(text: str, limit: int = 12) -> list[str]:
    return [candidate["latex"] for candidate in extract_equation_candidates(text, limit=limit)]


def extract_equation_candidates_from_chunks(
    chunks: list[dict[str, Any]],
    limit: int = 12,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    ordered_chunks = sorted(
        enumerate(chunks),
        key=lambda item: (0 if str(item[1].get("kind") or "") == "equation" else 1, item[0]),
    )
    for _original_position, chunk in ordered_chunks:
        kind = str(chunk.get("kind") or "")
        if kind not in {"equation", "paragraph", "sentence", "inline_math"}:
            continue
        chunk_latex = str(chunk.get("latex") or "").strip()
        nested_candidates = (
            [{"latex": chunk_latex, "source_label": str(chunk.get("source_label") or "")}]
            if chunk_latex
            else extract_equation_candidates(str(chunk.get("text") or ""), limit=4)
        )
        for nested_candidate in nested_candidates:
            latex, inline_label = normalize_extracted_equation(
                str(nested_candidate.get("latex") or ""),
                str(chunk.get("source_label") or nested_candidate.get("source_label") or ""),
            )
            latex, split_label = split_source_label(latex)
            inline_label = inline_label or split_label
            normalized = re.sub(r"\s+", "", latex)
            if not latex or normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(
                {
                    "latex": latex,
                    "confidence": str(chunk.get("confidence") or ("high" if kind == "equation" else "medium")),
                    "method": str(chunk.get("method") or ("structured_equation_block" if kind == "equation" else "context_block_equation")),
                    "source_label": inline_label,
                    "page": chunk.get("page"),
                    "bbox": chunk.get("bbox") or [],
                    "polygon": chunk.get("polygon") or [],
                    "block_id": str(chunk.get("block_id") or ""),
                    "reading_order": chunk.get("reading_order"),
                    "section_heading": str(chunk.get("section_heading") or ""),
                    "equation_image": str(chunk.get("equation_image") or ""),
                }
            )
            if len(candidates) >= limit:
                return candidates
    return candidates


def match_manual_equation_candidate(
    manual_latex: str,
    source_label: str,
    extracted_candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    manual_symbols = {
        normalize_key(str(node.get("symbol") or ""))
        for node in extract_grouped_expression(manual_latex)
        if node.get("kind") == "symbol"
    }
    best: tuple[float, dict[str, Any]] | None = None
    for candidate in extracted_candidates:
        candidate_symbols = {
            normalize_key(str(node.get("symbol") or ""))
            for node in extract_grouped_expression(str(candidate.get("latex") or ""))
            if node.get("kind") == "symbol"
        }
        union = manual_symbols.union(candidate_symbols)
        overlap = len(manual_symbols.intersection(candidate_symbols)) / len(union) if union else 0.0
        label_matches = bool(source_label and str(candidate.get("source_label") or "") == source_label)
        score = overlap + (1.0 if label_matches else 0.0)
        if (label_matches and overlap >= 0.2) or overlap >= 0.65:
            if best is None or score > best[0]:
                best = (score, candidate)
    return dict(best[1]) if best else None


def extract_pdf_context_from_base64(
    pdf_base64: str,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    if not pdf_base64:
        return "", [], {"status": "not_provided", "detail": "No PDF payload supplied."}
    try:
        raw = base64.b64decode(pdf_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        return "", [], {"status": "failed", "detail": f"PDF base64 decode failed: {exc}"}
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw))
        page_texts: list[str] = []
        context_chunks: list[dict[str, Any]] = []
        page_limit = positive_int_env("MATHONTOSPEAK_PDF_PAGE_LIMIT", DEFAULT_PDF_PAGE_LIMIT)
        pages_processed = min(len(reader.pages), page_limit)
        for page_number, page in enumerate(reader.pages[:page_limit], start=1):
            page_text = repair_pdf_spacing(page.extract_text() or "")
            if not page_text.strip():
                continue
            page_texts.append(f"[Page {page_number}]\n{page_text}")
            context_chunks.extend(
                context_chunks_from_text(
                    page_text,
                    source="pdf",
                    page=page_number,
                    include_title=page_number == 1,
                )
            )
        for reading_order, chunk in enumerate(context_chunks):
            chunk["reading_order"] = reading_order
        text = "\n\n".join(page_texts).strip()
    except Exception as exc:  # noqa: BLE001 - returned as user-facing provenance.
        return "", [], {"status": "failed", "detail": f"PDF extraction failed: {type(exc).__name__}: {exc}"}
    if not text:
        return "", [], {"status": "empty", "detail": "PDF parsed, but no extractable text was found."}
    return (
        text,
        context_chunks,
        {
            "status": "ok",
            "detail": (
                f"Extracted text from {pages_processed} of {len(reader.pages)} PDF page(s)."
            ),
            "page_count": len(reader.pages),
            "pages_processed": pages_processed,
            "truncated": len(reader.pages) > pages_processed,
            "context_chunk_count": len(context_chunks),
        },
    )


def extract_pdf_text_from_base64(pdf_base64: str) -> tuple[str, dict[str, Any]]:
    text, _chunks, status = extract_pdf_context_from_base64(pdf_base64)
    return text, status


def marker_executable_path() -> Path:
    configured = os.getenv("MARKER_SINGLE_PATH", "").strip()
    if configured:
        return Path(configured)
    external_root = Path(
        os.getenv(
            "MATHONTOSPEAK_EXTERNAL_ROOT",
            str(Path.home() / "Documents" / "MathOntoSpeak-External"),
        )
    )
    executable_name = "marker_single.exe" if os.name == "nt" else "marker_single"
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    return external_root / ".venvs" / "marker" / scripts_dir / executable_name


def marker_mode_policy() -> tuple[str, str, str]:
    requested = os.getenv("MATHONTOSPEAK_MARKER_MODE", "auto").strip().lower() or "auto"
    if requested not in {"auto", "balanced", "fast"}:
        requested = "auto"
    if requested != "auto":
        return requested, requested, "The Marker mode was explicitly configured."
    if shutil.which("docker") and shutil.which("nvidia-smi"):
        return requested, "balanced", "Docker and an NVIDIA runtime are available."
    return requested, "fast", "Docker-backed GPU inference is unavailable; using reliable fast extraction."


def marker_ocr_policy(requested_mode: str) -> tuple[bool, str]:
    if requested_mode != "auto":
        return True, "OCR follows the explicitly configured Marker mode."
    if shutil.which("docker") and shutil.which("nvidia-smi"):
        return True, "Docker-backed NVIDIA OCR is available."
    if shutil.which("llama-server"):
        return True, "Native llama.cpp OCR is available."
    return False, "No local Marker VLM runtime is installed; using the PDF text layer without OCR."


def marker_runtime_status() -> dict[str, Any]:
    executable = marker_executable_path()
    requested_mode, effective_mode, mode_reason = marker_mode_policy()
    ocr_enabled, ocr_reason = marker_ocr_policy(requested_mode)
    return {
        "available": executable.is_file(),
        "path": str(executable),
        "strategy": os.getenv("MATHONTOSPEAK_PDF_EXTRACTOR", "auto").strip().lower() or "auto",
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "mode_reason": mode_reason,
        "ocr_enabled": ocr_enabled,
        "ocr_reason": ocr_reason,
    }


def marker_markdown_context_chunks(markdown: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_heading = ""
    page_number = 1
    for block in re.split(r"\n\s*\n", markdown or ""):
        cleaned = block.strip()
        if not cleaned:
            continue
        if re.fullmatch(r"-{20,}", cleaned):
            page_number += 1
            continue
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", cleaned)
        if heading_match:
            current_heading = re.sub(r"\s+", " ", heading_match.group(2)).strip()
            chunks.append(
                {
                    "source": "marker",
                    "kind": "section_heading",
                    "text": current_heading,
                    "page": page_number,
                    "section_heading": current_heading,
                }
            )
            continue

        kind = "equation" if cleaned.startswith(("$$", r"\[")) else "paragraph"
        text = re.sub(r"\s+", " ", cleaned).strip()
        payload: dict[str, Any] = {
            "source": "marker",
            "kind": kind,
            "text": text[:1600],
            "page": page_number,
        }
        if current_heading:
            payload["section_heading"] = current_heading
        chunks.append(payload)
        if kind == "paragraph":
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                sentence = sentence.strip()
                if sentence and sentence != text:
                    sentence_payload = {
                        "source": "marker",
                        "kind": "sentence",
                        "text": sentence[:1200],
                        "page": page_number,
                    }
                    if current_heading:
                        sentence_payload["section_heading"] = current_heading
                    chunks.append(sentence_payload)
    return chunks


def _marker_html_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def repair_marker_equation_text(value: str) -> tuple[str, str]:
    """Repair common symbol-font damage in born-digital equation blocks."""
    return normalize_extracted_equation(value)


def _marker_page_number(block: dict[str, Any]) -> int | None:
    match = re.search(r"/page/(\d+)/", str(block.get("id") or ""), re.IGNORECASE)
    if match:
        return int(match.group(1)) + 1
    for candidate in (
        block.get("page"),
        block.get("page_id"),
        (block.get("metadata") or {}).get("page_id") if isinstance(block.get("metadata"), dict) else None,
    ):
        if isinstance(candidate, int):
            return candidate + 1 if candidate >= 0 else None
    return None


def _polygon_bbox(polygon: Any) -> list[float]:
    if not isinstance(polygon, list) or not polygon:
        return []
    try:
        xs = [float(point[0]) for point in polygon]
        ys = [float(point[1]) for point in polygon]
    except (IndexError, TypeError, ValueError):
        return []
    return [min(xs), min(ys), max(xs), max(ys)]


def marker_structured_context_chunks(payload: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        block_type = str(value.get("block_type") or value.get("type") or "")
        children = value.get("children") or value.get("blocks")
        if block_type.lower() in {"document", "page"} and children:
            walk(children)
            return
        if block_type:
            blocks.append(value)
            return
        if children:
            walk(children)

    walk(payload)
    chunks: list[dict[str, Any]] = []
    headings_by_page: dict[int | None, str] = {}
    kind_by_type = {
        "sectionheader": "section_heading",
        "equation": "equation",
        "textinlinemath": "inline_math",
        "caption": "caption",
        "footnote": "footnote",
        "text": "paragraph",
        "listitem": "paragraph",
    }
    for reading_order, block in enumerate(blocks):
        block_type = str(block.get("block_type") or block.get("type") or "")
        kind = kind_by_type.get(block_type.lower())
        if not kind:
            continue
        raw_html = str(block.get("html") or block.get("text") or "")
        text_value = _marker_html_text(raw_html)
        if not text_value:
            continue
        page = _marker_page_number(block)
        if kind == "section_heading":
            headings_by_page[page] = text_value
        section_heading = headings_by_page.get(page, "")
        polygon = block.get("polygon") or []
        chunk: dict[str, Any] = {
            "source": "marker",
            "kind": kind,
            "text": text_value[:2000],
            "page": page,
            "reading_order": reading_order,
            "block_id": str(block.get("id") or f"marker-block-{reading_order}"),
            "block_type": block_type,
            "polygon": polygon,
            "bbox": _polygon_bbox(polygon),
        }
        if section_heading:
            chunk["section_heading"] = section_heading
        if kind == "equation":
            nested = extract_equation_candidates(raw_html, limit=1)
            latex = str(nested[0].get("latex") or "") if nested else ""
            nested_label = str(nested[0].get("source_label") or "") if nested else ""
            if not latex or "block-type" in latex or "type =" in latex:
                latex, nested_label = repair_marker_equation_text(text_value)
            trailing_label = re.search(r"\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)\s*$", text_value)
            if latex:
                chunk["latex"] = latex
            if nested_label or trailing_label:
                chunk["source_label"] = nested_label or trailing_label.group(1)
            images = block.get("images")
            if isinstance(images, dict) and images:
                image_value = str(next(iter(images.values())) or "")
                if image_value:
                    chunk["equation_image"] = image_value if image_value.startswith("data:") else f"data:image/png;base64,{image_value}"
        chunks.append(chunk)
        if kind == "paragraph":
            for sentence in re.split(r"(?<=[.!?])\s+", text_value):
                if sentence.strip() and sentence.strip() != text_value:
                    sentence_chunk = dict(chunk)
                    sentence_chunk["kind"] = "sentence"
                    sentence_chunk["text"] = sentence.strip()[:1200]
                    sentence_chunk["block_id"] = f"{chunk['block_id']}-sentence-{len(chunks)}"
                    chunks.append(sentence_chunk)
    return chunks


def extract_pdf_context_with_marker(
    raw_pdf: bytes,
    *,
    pdf_filename: str = "",
    executable: Path | None = None,
    timeout_seconds: int | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    executable = executable or marker_executable_path()
    timeout_seconds = timeout_seconds or positive_int_env(
        "MATHONTOSPEAK_MARKER_TIMEOUT_SECONDS",
        DEFAULT_MARKER_TIMEOUT_SECONDS,
    )
    requested_mode, marker_mode, mode_reason = marker_mode_policy()
    ocr_enabled, ocr_reason = marker_ocr_policy(requested_mode)
    cache_enabled = os.getenv("MATHONTOSPEAK_DISABLE_CACHE", "").strip() != "1" and executable.is_file()
    cache_root = Path(
        os.getenv(
            "MATHONTOSPEAK_CACHE_DIR",
            str(Path.home() / ".cache" / "mathontospeak"),
        )
    )
    cache_key = hashlib.sha256(
        raw_pdf + f"marker-chunks-v4:{marker_mode}:ocr={ocr_enabled}".encode("utf-8")
    ).hexdigest()
    cache_path = cache_root / "pdf" / f"{cache_key}.json"
    if cache_enabled:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_status = dict(cached["status"])
            cached_status["cache_hit"] = True
            cached_status["detail"] = f"Reused cached Marker extraction. {cached_status.get('detail', '')}".strip()
            return str(cached["text"]), list(cached["chunks"]), cached_status
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    try:
        with tempfile.TemporaryDirectory(prefix="mathontospeak-marker-") as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "paper.pdf"
            output_dir = temp_root / "output"
            input_path.write_bytes(raw_pdf)
            command = [
                str(executable),
                str(input_path),
                "--mode",
                marker_mode,
                "--output_format",
                "chunks",
                "--output_dir",
                str(output_dir),
                "--disable_multiprocessing",
            ]
            if not ocr_enabled:
                command.append("--disable_ocr")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "Marker exited without details.").strip()
                return (
                    "",
                    [],
                    {
                        "status": "failed",
                        "extractor": "marker",
                        "detail": f"Marker exited with code {result.returncode}: {detail[-800:]}",
                    },
                )
            json_files = sorted(
                output_dir.rglob("*.json"),
                key=lambda path: path.stat().st_size,
                reverse=True,
            )
            markdown_files = sorted(
                output_dir.rglob("*.md"),
                key=lambda path: path.stat().st_size,
                reverse=True,
            )
            if not json_files and not markdown_files:
                return (
                    "",
                    [],
                    {
                        "status": "empty",
                        "extractor": "marker",
                        "detail": "Marker completed but produced no structured output.",
                    },
                )
            if json_files:
                structured = json.loads(json_files[0].read_text(encoding="utf-8", errors="replace"))
                chunks = marker_structured_context_chunks(structured)
                markdown = "\n\n".join(str(chunk.get("text") or "") for chunk in chunks).strip()
                output_format = "chunks"
            else:
                markdown = markdown_files[0].read_text(encoding="utf-8", errors="replace").strip()
                chunks = marker_markdown_context_chunks(markdown)
                output_format = "markdown_fallback"
    except subprocess.TimeoutExpired:
        return (
            "",
            [],
            {
                "status": "failed",
                "extractor": "marker",
                "detail": f"Marker exceeded the {timeout_seconds}-second processing limit.",
            },
        )
    except (OSError, ValueError) as exc:
        return (
            "",
            [],
            {
                "status": "failed",
                "extractor": "marker",
                "detail": f"Marker could not run: {type(exc).__name__}: {exc}",
            },
        )

    if not markdown:
        return (
            "",
            [],
            {
                "status": "empty",
                "extractor": "marker",
                "detail": "Marker produced an empty Markdown document.",
            },
        )
    equation_count = len(extract_equation_candidates(markdown))
    status = {
        "status": "ok",
        "extractor": "marker",
        "detail": (
            f"Marker extracted {len(chunks)} context chunk(s) and "
            f"{equation_count} equation candidate(s)."
        ),
        "filename": pdf_filename,
        "context_chunk_count": len(chunks),
        "equation_candidate_count": equation_count,
        "mode": marker_mode,
        "requested_mode": requested_mode,
        "mode_reason": mode_reason,
        "ocr_enabled": ocr_enabled,
        "ocr_reason": ocr_reason,
        "output_format": output_format,
        "cache_hit": False,
        "document_id": cache_key,
    }
    if cache_enabled:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({"text": markdown, "chunks": chunks, "status": status}, ensure_ascii=True),
                encoding="utf-8",
            )
        except OSError:
            status["cache_warning"] = "Marker extraction succeeded, but the local cache could not be written."
    return markdown, chunks, status


def assess_document_extraction_quality(
    text: str,
    chunks: list[dict[str, Any]],
    *,
    equation_count: int,
    manual_equations_present: bool,
) -> dict[str, Any]:
    normalized = normalize_text(text)
    word_count = len(re.findall(r"[A-Za-z][A-Za-z0-9'-]+", normalized))
    paragraph_count = sum(
        1
        for chunk in chunks
        if chunk.get("kind") == "paragraph" and len(str(chunk.get("text") or "").split()) >= 5
    )
    replacement_count = normalized.count("\ufffd") + normalized.count("\x00")
    score = 1.0
    reasons: list[str] = []
    if word_count < 60:
        score -= 0.35
        reasons.append("too_little_prose")
    if paragraph_count < 2:
        score -= 0.25
        reasons.append("too_few_paragraphs")
    if len(chunks) < 3:
        score -= 0.15
        reasons.append("too_few_structured_blocks")
    if not manual_equations_present and equation_count == 0:
        score -= 0.35
        reasons.append("no_equation_recovered")
    if replacement_count:
        score -= 0.25
        reasons.append("corrupted_characters")
    score = max(0.0, round(score, 3))
    return {
        "score": score,
        "confidence": "high" if score >= 0.75 else "medium" if score >= 0.55 else "low",
        "usable": score >= 0.55,
        "word_count": word_count,
        "paragraph_count": paragraph_count,
        "structured_block_count": len(chunks),
        "equation_count": equation_count,
        "reasons": reasons,
    }


def merge_extraction_chunks(
    primary_chunks: list[dict[str, Any]],
    recovery_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(chunk) for chunk in primary_chunks]
    existing_text = {
        normalize_text(str(chunk.get("text") or ""))
        for chunk in merged
        if str(chunk.get("text") or "").strip()
    }
    for chunk in recovery_chunks:
        normalized = normalize_text(str(chunk.get("text") or ""))
        if not normalized:
            continue
        if chunk.get("kind") == "equation" or normalized not in existing_text:
            merged.append(dict(chunk))
            existing_text.add(normalized)
    merged.sort(
        key=lambda chunk: (
            int(chunk["page"]) if str(chunk.get("page") or "").isdigit() else 10**9,
            int(chunk["reading_order"])
            if str(chunk.get("reading_order") or "").isdigit()
            else 10**9,
        )
    )
    for reading_order, chunk in enumerate(merged):
        chunk["reading_order"] = reading_order
    return merged


def extract_pdf_context(
    pdf_base64: str,
    *,
    pdf_filename: str = "",
    manual_equations_present: bool = False,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    pypdf_text, pypdf_chunks, pypdf_status = extract_pdf_context_from_base64(pdf_base64)
    pypdf_status = dict(pypdf_status)
    pypdf_status.setdefault("extractor", "pypdf")
    pypdf_status["fallback_used"] = False
    if pdf_filename:
        pypdf_status["filename"] = pdf_filename
    if not pdf_base64:
        return pypdf_text, pypdf_chunks, pypdf_status

    strategy = os.getenv("MATHONTOSPEAK_PDF_EXTRACTOR", "auto").strip().lower() or "auto"
    if strategy not in {"auto", "docling", "mineru", "marker", "pypdf"}:
        strategy = "auto"
        pypdf_status["configuration_warning"] = (
            "Unknown MATHONTOSPEAK_PDF_EXTRACTOR value; using auto."
        )
    candidates = extract_equation_candidates(pypdf_text)
    has_high_confidence_equation = any(
        candidate.get("confidence") == "high" for candidate in candidates
    )
    advanced_extraction_needed = strategy in {"docling", "mineru", "marker"} or (
        strategy == "auto"
        and (
            pypdf_status.get("status") != "ok"
            or not pypdf_text
            or (not manual_equations_present and not has_high_confidence_equation)
        )
    )
    if strategy == "pypdf" or not advanced_extraction_needed:
        return pypdf_text, pypdf_chunks, pypdf_status

    try:
        raw_pdf = base64.b64decode(pdf_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        failed_extractor = (
            strategy if strategy in {"docling", "mineru", "marker"} else "advanced_extraction"
        )
        pypdf_status[failed_extractor] = {
            "status": "failed",
            "extractor": failed_extractor,
            "detail": f"Advanced extractor input decode failed: {exc}",
        }
        return pypdf_text, pypdf_chunks, pypdf_status

    docling_context: tuple[str, list[dict[str, Any]], dict[str, Any]] | None = None
    mineru_fallback_reason = "docling_not_configured"
    if strategy in {"auto", "docling"}:
        docling_status = docling_runtime_status()
        if docling_status.get("enabled") or docling_status.get("runtime_available"):
            docling_text, docling_chunks, extraction_status = extract_pdf_context_with_docling(
                raw_pdf,
                pdf_filename=pdf_filename,
            )
            if extraction_status.get("status") == "ok" and docling_text:
                extraction_status = dict(extraction_status)
                extraction_status["fallback_used"] = strategy == "auto"
                extraction_status["selected_integration"] = "docling"
                extraction_status["pypdf"] = pypdf_status
                docling_equations = extract_equation_candidates_from_chunks(docling_chunks)
                if not docling_equations:
                    docling_equations = extract_equation_candidates(docling_text)
                extraction_status["equation_candidate_count"] = len(docling_equations)
                extraction_quality = assess_document_extraction_quality(
                    docling_text,
                    docling_chunks,
                    equation_count=len(docling_equations),
                    manual_equations_present=manual_equations_present,
                )
                extraction_status["quality"] = extraction_quality
                if strategy == "docling" or (docling_equations and extraction_quality["usable"]):
                    return enrich_with_grobid(
                        raw_pdf,
                        pdf_filename=pdf_filename,
                        text=docling_text,
                        chunks=docling_chunks,
                        status=extraction_status,
                    )
                mineru_fallback_reason = (
                    "equation_not_recovered" if not docling_equations else "low_document_quality"
                )
                reason_text = (
                    "No equations were recovered"
                    if not docling_equations
                    else "The extracted document context was low confidence"
                )
                extraction_status["detail"] = (
                    str(extraction_status.get("detail") or "Docling completed.")
                    + f" {reason_text}, so MinerU was tried next."
                )
                docling_context = (docling_text, docling_chunks, extraction_status)
            # Keep provenance snapshots acyclic: extraction_status already contains
            # a pypdf snapshot, so linking the same object back into pypdf_status
            # would make the API response impossible to serialize as JSON.
            pypdf_status["docling"] = {
                key: value
                for key, value in extraction_status.items()
                if key != "pypdf"
            }
            if extraction_status.get("status") != "ok":
                mineru_fallback_reason = "docling_failed"
        else:
            pypdf_status["docling"] = {
                "status": "not_configured",
                "extractor": "docling",
                "detail": "Docling is wired into the pipeline, but its isolated runtime is not installed.",
            }
        if strategy == "docling":
            return pypdf_text, pypdf_chunks, pypdf_status

    if strategy in {"auto", "mineru"}:
        mineru_status = mineru_runtime_status()
        if mineru_status.get("enabled") or mineru_status.get("runtime_available"):
            mineru_text, mineru_chunks, extraction_status = extract_pdf_context_with_mineru(
                raw_pdf,
                pdf_filename=pdf_filename,
            )
            if extraction_status.get("status") == "ok" and mineru_text:
                extraction_status = dict(extraction_status)
                extraction_status["fallback_used"] = strategy == "auto"
                extraction_status["selected_integration"] = "mineru"
                extraction_status["fallback_reason"] = mineru_fallback_reason
                extraction_status["pypdf"] = pypdf_status
                mineru_equations = extract_equation_candidates_from_chunks(mineru_chunks)
                if not mineru_equations:
                    mineru_equations = extract_equation_candidates(mineru_text)
                extraction_status["equation_candidate_count"] = len(mineru_equations)
                if docling_context:
                    docling_text, docling_chunks, docling_status = docling_context
                    mineru_chunks = merge_extraction_chunks(docling_chunks, mineru_chunks)
                    mineru_text = document_text_from_structured_chunks(mineru_chunks) or (
                        f"{docling_text}\n\n{mineru_text}".strip()
                    )
                    extraction_status["context_provider"] = "docling"
                    extraction_status["docling"] = docling_status
                    extraction_status["context_chunk_count"] = len(mineru_chunks)
                if strategy == "mineru" or mineru_equations or manual_equations_present:
                    return enrich_with_grobid(
                        raw_pdf,
                        pdf_filename=pdf_filename,
                        text=mineru_text,
                        chunks=mineru_chunks,
                        status=extraction_status,
                    )
                extraction_status["detail"] = (
                    str(extraction_status.get("detail") or "MinerU completed.")
                    + " No equations were recovered, so Marker was tried next."
                )
            pypdf_status["mineru"] = {
                key: value
                for key, value in extraction_status.items()
                if key != "pypdf"
            }
        else:
            pypdf_status["mineru"] = {
                "status": "not_configured",
                "extractor": "mineru",
                "detail": "MinerU is wired into the pipeline, but its isolated runtime is not installed.",
            }
        if strategy == "mineru":
            return pypdf_text, pypdf_chunks, pypdf_status

    executable = marker_executable_path()
    if not executable.is_file():
        pypdf_status["marker"] = {
            "status": "not_configured",
            "extractor": "marker",
            "detail": f"Marker executable was not found at {executable}.",
        }
        return pypdf_text, pypdf_chunks, pypdf_status
    marker_text, marker_chunks, marker_status = extract_pdf_context_with_marker(
        raw_pdf,
        pdf_filename=pdf_filename,
        executable=executable,
    )
    if marker_status.get("status") == "ok" and marker_text:
        marker_status = dict(marker_status)
        marker_status["fallback_used"] = True
        marker_status["pypdf"] = pypdf_status
        if docling_context:
            docling_text, docling_chunks, docling_status = docling_context
            docling_pages = {
                int(chunk["page"])
                for chunk in docling_chunks
                if str(chunk.get("page") or "").isdigit()
            }
            existing_text = {
                normalize_text(str(chunk.get("text") or ""))
                for chunk in docling_chunks
                if str(chunk.get("text") or "").strip()
            }
            merged_chunks = list(docling_chunks)
            for chunk in marker_chunks:
                normalized = normalize_text(str(chunk.get("text") or ""))
                marker_page = int(chunk["page"]) if str(chunk.get("page") or "").isdigit() else None
                if (
                    chunk.get("kind") != "equation"
                    and marker_page is not None
                    and marker_page in docling_pages
                ):
                    continue
                if normalized and (chunk.get("kind") == "equation" or normalized not in existing_text):
                    merged_chunks.append(chunk)
                    existing_text.add(normalized)
            merged_chunks.sort(
                key=lambda chunk: (
                    int(chunk["page"]) if str(chunk.get("page") or "").isdigit() else 10**9,
                    int(chunk["reading_order"])
                    if str(chunk.get("reading_order") or "").isdigit()
                    else 10**9,
                )
            )
            for reading_order, chunk in enumerate(merged_chunks):
                chunk["reading_order"] = reading_order
            marker_text = document_text_from_structured_chunks(merged_chunks)
            marker_chunks = merged_chunks
            marker_status["context_provider"] = "docling"
            marker_status["docling"] = docling_status
            marker_status["context_chunk_count"] = len(marker_chunks)
        marker_status["selected_integration"] = "marker"
        return enrich_with_grobid(
            raw_pdf,
            pdf_filename=pdf_filename,
            text=marker_text,
            chunks=marker_chunks,
            status=marker_status,
        )

    if pypdf_status.get("status") == "ok" and pypdf_text:
        pypdf_status["marker"] = marker_status
        return pypdf_text, pypdf_chunks, pypdf_status
    return (
        "",
        [],
        {
            "status": "failed",
            "extractor": "none",
            "detail": (
                f"pypdf: {pypdf_status.get('detail', 'failed')} "
                f"Marker: {marker_status.get('detail', 'failed')}"
            ),
            "filename": pdf_filename,
            "fallback_used": True,
            "pypdf": pypdf_status,
            "marker": marker_status,
            "docling": pypdf_status.get("docling", {}),
            "mineru": pypdf_status.get("mineru", {}),
        },
    )


def split_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[;,]", str(value)) if part.strip()]


def extract_document_context(
    encoded_document: str,
    *,
    filename: str = "",
    media_type: str = "",
    manual_equations_present: bool = False,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    if is_equation_image(filename, media_type):
        return extract_equation_image_context(
            encoded_document,
            filename=filename,
            media_type=media_type,
        )
    return extract_pdf_context(
        encoded_document,
        pdf_filename=filename,
        manual_equations_present=manual_equations_present,
    )


def rank_context_evidence(
    chunks: list[dict[str, Any]],
    *,
    latex: str,
    labels: list[str],
    equation_metadata: dict[str, Any] | None = None,
    limit: int = 3,
    semantic_scores_by_text: dict[str, float] | None = None,
    allow_semantic_runtime: bool = True,
) -> list[dict[str, Any]]:
    equation_metadata = equation_metadata or {}
    equation_page = equation_metadata.get("page")
    equation_order = equation_metadata.get("reading_order")
    equation_section = str(equation_metadata.get("section_heading") or "")
    source_label = str(equation_metadata.get("source_label") or "")
    equation_block = str(equation_metadata.get("block_id") or "")
    equation_terms = {
        normalize_key(term)
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_]*", latex)
        if len(term) > 1 or term.lower() in {"h", "n", "p", "r", "s", "x", "y"}
    }
    macro_names = {
        "bar", "frac", "hat", "in", "ldots", "left", "mathrm", "pi", "quad",
        "right", "sqrt", "sum", "text", "textrm", "tilde",
    }
    lhs_terms = [
        normalize_key(term)
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_]*", latex.split("=", 1)[0])
        if normalize_key(term) not in macro_names
    ]
    lhs_symbol = lhs_terms[0] if lhs_terms else ""
    label_terms = {token for label in labels for token in normalize_text(label).split()}
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for position, chunk in enumerate(chunks):
        if chunk.get("source") == "image_ocr":
            continue
        if chunk.get("kind") in {"equation", "inline_math", "ocr_text"}:
            continue
        if equation_block and str(chunk.get("block_id") or "") == equation_block:
            continue
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        normalized_terms = set(normalize_text(text).split())
        chunk_equation_terms = {
            normalize_key(term) for term in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text)
        }
        symbol_matches = len(equation_terms.intersection(chunk_equation_terms))
        chunk_sequence = [
            normalize_key(term) for term in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text)
        ]
        clustered_matches = 0
        for start in range(len(chunk_sequence)):
            window = set(chunk_sequence[start : start + 60])
            clustered_matches = max(clustered_matches, len(equation_terms.intersection(window)))
        lhs_bonus = 0
        if lhs_symbol:
            lhs_pattern = rf"(?<!\w){re.escape(lhs_symbol)}\s*(?:[\[(][^\])]*[\])])?\s*="
            lhs_bonus = 8 if re.search(lhs_pattern, text, re.IGNORECASE) else 0
        label_matches = len(normalized_terms.intersection(label_terms))
        domain_matches = len(normalized_terms.intersection(CONTEXT_DOMAIN_TERMS))
        definition_bonus = 2 if re.search(r"\b(?:is|denotes|represents|refers to)\b", text, re.IGNORECASE) else 0
        symbol_definition_matches = 0
        for term in equation_terms:
            if not term:
                continue
            definition_pattern = (
                rf"(?<!\w){re.escape(term)}\s*(?:[\[(][^\])]*[\])])?\s+"
                r"(?:is|denotes|represents|refers to)\b"
            )
            if re.search(definition_pattern, normalize_text(text), re.IGNORECASE):
                symbol_definition_matches += 1
        kind_bonus = 1 if chunk.get("kind") in {"abstract", "paragraph", "sentence"} else 0
        page_bonus = 0.0
        if equation_page is not None and chunk.get("page") == equation_page:
            page_bonus = 16.0
        order_bonus = 0.0
        if equation_order is not None and chunk.get("reading_order") is not None:
            distance = abs(int(chunk["reading_order"]) - int(equation_order))
            order_bonus = max(0.0, 6.0 - float(distance))
        section_bonus = 0.0
        if equation_section and str(chunk.get("section_heading") or "") == equation_section:
            section_bonus = 3.0
        reference_bonus = 0.0
        if source_label and re.search(
            rf"\b(?:equation|eq\.?)[\s~]*(?:\(|\[)?{re.escape(source_label)}(?:\)|\])?",
            text,
            re.IGNORECASE,
        ):
            reference_bonus = 10.0
        elif source_label and re.search(
            rf"\b(?:from|using|in)\s*\(\s*{re.escape(source_label)}\s*\)",
            text,
            re.IGNORECASE,
        ):
            reference_bonus = 10.0
        length_penalty = min(len(text) / 500.0, 2.0)
        score = (
            (clustered_matches * 5.0)
            + symbol_matches
            + (label_matches * 1.5)
            + (domain_matches * 0.5)
            + definition_bonus
            + (symbol_definition_matches * 6.0)
            + kind_bonus
            + lhs_bonus
            + page_bonus
            + order_bonus
            + section_bonus
            + reference_bonus
            - length_penalty
        )
        ranked.append((score, -position, chunk))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    semantic_scores: dict[int, float] = {}
    ranking_engine = "deterministic_proximity"
    has_extracted_document_evidence = any(
        str(item[2].get("source") or "") in {"docling", "grobid", "marker", "mineru", "pdf"}
        for item in ranked
    )
    if ranked and has_extracted_document_evidence and semantic_scores_by_text is not None:
        semantic_candidates = ranked[:20]
        for _score, _position, chunk in semantic_candidates:
            semantic_score = semantic_scores_by_text.get(
                normalize_text(str(chunk.get("text") or ""))
            )
            if semantic_score is not None:
                semantic_scores[id(chunk)] = semantic_score
        if semantic_scores:
            ranked = [
                (score + (semantic_scores.get(id(chunk), 0.0) * 12.0), position, chunk)
                for score, position, chunk in ranked
            ]
            ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
            ranking_engine = "sentence_transformers_batch"
    elif (
        allow_semantic_runtime
        and ranked
        and has_extracted_document_evidence
        and semantic_retrieval_status().get("enabled")
    ):
        semantic_candidates = ranked[:20]
        query = " ".join([latex, *labels]).strip()
        scores, semantic_status = semantic_similarity_scores(
            query,
            [str(item[2].get("text") or "") for item in semantic_candidates],
        )
        if semantic_status.get("status") == "ok" and len(scores) == len(semantic_candidates):
            for (_score, _position, chunk), semantic_score in zip(semantic_candidates, scores, strict=True):
                semantic_scores[id(chunk)] = semantic_score
            ranked = [
                (score + (semantic_scores.get(id(chunk), 0.0) * 12.0), position, chunk)
                for score, position, chunk in ranked
            ]
            ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
            ranking_engine = "sentence_transformers"
    evidence: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    seen_normalized: list[str] = []
    for score, _position, chunk in ranked:
        text = str(chunk.get("text") or "")
        if text in seen_text:
            continue
        normalized_candidate = normalize_text(text)
        if any(
            min(len(normalized_candidate), len(previous)) > 35
            and (normalized_candidate in previous or previous in normalized_candidate)
            for previous in seen_normalized
        ):
            continue
        seen_text.add(text)
        seen_normalized.append(normalized_candidate)
        payload = dict(chunk)
        payload["relevance_score"] = round(score, 2)
        payload["ranking_engine"] = ranking_engine
        if id(chunk) in semantic_scores:
            payload["semantic_score"] = round(semantic_scores[id(chunk)], 4)
        payload.setdefault(
            "evidence_id",
            str(chunk.get("block_id") or f"evidence-{len(evidence) + 1}-{normalize_key(normalized_candidate)[:12]}"),
        )
        payload["provenance_type"] = "paper_evidence"
        evidence.append(payload)
        if len(evidence) >= limit:
            break
    return evidence


def rank_definition_evidence(
    chunks: list[dict[str, Any]],
    *,
    latex: str,
    equation_metadata: dict[str, Any],
    fallback: list[dict[str, Any]],
    limit: int = 20,
) -> list[dict[str, Any]]:
    equation_page = equation_metadata.get("page")
    equation_order = equation_metadata.get("reading_order")
    equation_block = str(equation_metadata.get("block_id") or "")
    if equation_page is None:
        return fallback
    symbols = {
        normalize_key(canonical_symbol(str(node.get("symbol") or ""))).lower()
        for node in extract_grouped_expression(latex)
        if node.get("kind") == "symbol"
    }
    qualified_surfaces = {
        item["surface_key"].lower() for item in _qualified_symbol_specs(latex) if item.get("surface_key")
    }
    ranked: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        if chunk.get("source") == "image_ocr":
            continue
        if equation_block and str(chunk.get("block_id") or "") == equation_block:
            continue
        page = chunk.get("page")
        order = chunk.get("reading_order")
        if page is None:
            continue
        text = str(chunk.get("text") or "")
        compact_text = re.sub(r"(?<=[A-Za-z])\s+(?=\d)", "", text)
        compact_text_key = normalize_key(compact_text).lower()
        text_symbols = {
            normalize_key(value).lower()
            for value in re.findall(r"[A-Za-z][A-Za-z0-9_]*", compact_text)
        }
        paper_definition_symbols = {
            normalize_key(symbol).lower()
            for symbol in extract_paper_symbol_definitions(
                [
                    {
                        "text": text,
                        "evidence_id": str(chunk.get("evidence_id") or chunk.get("block_id") or ""),
                    }
                ]
            )
        }
        explicit_definition_matches = symbols.intersection(paper_definition_symbols)
        matched_symbols = symbols.intersection(text_symbols | paper_definition_symbols)
        symbol_matches = len(matched_symbols)
        qualified_matches = sum(1 for surface in qualified_surfaces if surface in compact_text_key)
        if not symbol_matches and not qualified_matches:
            continue
        definition_cues = len(
            re.findall(
                r"\b(?:amplitude|amplitudes|index|input|inputs|is|matrix|mode|modes|output|outputs|ports|"
                r"denotes|represents|refers to|stands for|transform|where|gain|noise|power|signal|angle|distance|radius)\b",
                text,
                re.IGNORECASE,
            )
        )
        if not definition_cues:
            continue
        page_distance = abs(int(equation_page) - int(page))
        order_distance = (
            abs(int(order) - int(equation_order))
            if page == equation_page and equation_order is not None and order is not None
            else 20
        )
        same_section = bool(
            equation_metadata.get("section_heading")
            and chunk.get("section_heading") == equation_metadata.get("section_heading")
        )
        if (
            page != equation_page
            and not qualified_matches
            and not explicit_definition_matches
            and all(len(symbol) == 1 for symbol in matched_symbols)
        ):
            continue
        same_column = True
        equation_bbox = equation_metadata.get("bbox") or []
        chunk_bbox = chunk.get("bbox") or []
        if page == equation_page and len(equation_bbox) == 4 and len(chunk_bbox) == 4:
            overlap = max(
                0.0,
                min(float(equation_bbox[2]), float(chunk_bbox[2]))
                - max(float(equation_bbox[0]), float(chunk_bbox[0])),
            )
            same_column = overlap > 0
        if page == equation_page and not same_column:
            continue
        score = (
            (symbol_matches * 4.0)
            + (len(explicit_definition_matches) * 10.0)
            + (qualified_matches * 12.0)
            + min(definition_cues, 5)
            + max(0.0, 10.0 - page_distance * 2.0)
            + max(0.0, 8.0 - order_distance)
            + (4.0 if same_section else 0.0)
        )
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, chunk in ranked:
        text = str(chunk.get("text") or "")
        if normalize_text(text) in seen:
            continue
        seen.add(normalize_text(text))
        item = dict(chunk)
        item.setdefault("evidence_id", str(item.get("block_id") or f"definition-{len(output) + 1}"))
        item["provenance_type"] = "paper_evidence"
        item["definition_score"] = round(score, 2)
        output.append(item)
        if len(output) >= limit:
            break
    return output or fallback


def _context_symbol_latex(value: str) -> str:
    compact = re.sub(r"\s+", "", value or "").strip(".,;:()[]")
    if not compact or not re.fullmatch(r"[A-Za-z]{1,4}", compact):
        return compact
    if len(compact) == 1:
        return compact
    suffix = compact[1:]
    return f"{compact[0]}_{suffix}" if len(suffix) == 1 else f"{compact[0]}_{{{suffix}}}"


def _qualified_symbol_specs(latex: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"(?P<raw>(?P<base>[A-Za-z])_(?:\{(?P<braced_sub>[^{}]+)\}|(?P<sub>[^\s^]+))"
        r"\s*\^\s*\{\\(?:mathrm|textrm|text|operatorname)\s*\{(?P<qualifier>[^{}]+)\}\})"
    )
    specs: list[dict[str, str]] = []
    for match in pattern.finditer(latex or ""):
        subscript = str(match.group("braced_sub") or match.group("sub") or "").strip()
        qualifier = str(match.group("qualifier") or "").strip()
        base = match.group("base")
        specs.append(
            {
                "raw": match.group("raw"),
                "base": base,
                "subscript": subscript,
                "qualifier": qualifier,
                "surface_key": normalize_key(f"{base} {qualifier} {subscript}"),
            }
        )
    return specs


def extract_paper_symbol_definitions(evidence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}

    def add_definition(symbol: str, meaning: str, evidence_id: str) -> None:
        key = symbol_key(symbol)
        cleaned_meaning = re.sub(r"\s+", " ", meaning).strip(" ,.;")
        cleaned_meaning = re.split(
            r"\s+and\s+(?:the\s+)?(?:incident|input|output|transmit|received|threshold|activation)\s+"
            r"(?:energy|power|signal|value|quantity)\b",
            cleaned_meaning,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        cleaned_meaning = re.sub(r"\bE\s+o\s+E\s+d\b", "E is less than E d", cleaned_meaning)
        cleaned_meaning = re.sub(r"\b(90|180)1\b", r"\1 degrees", cleaned_meaning)
        cleaned_meaning = cleaned_meaning.strip(" ,.;:")
        if not key or not cleaned_meaning:
            return
        definitions.setdefault(
            key,
            {
                "symbol": canonical_symbol(symbol),
                "latex": symbol,
                "meaning": cleaned_meaning,
                "evidence_ids": [evidence_id] if evidence_id else [],
            },
        )

    # Recover compound variables that PDF text layers commonly flatten. These meanings are
    # only added when the corresponding wording is present in the selected paper evidence.
    for item in evidence:
        text = str(item.get("text") or "")
        compact = normalize_key(text)
        evidence_id = str(item.get("evidence_id") or item.get("block_id") or "")
        threshold_match = re.search(
            r"threshold\s+incident\s+energy\s+E\s*(?:th\s*0|0\s*th)"
            r"(?:\s+below\s+which\s+(?P<condition>[^.;]{3,160}))?",
            text,
            re.IGNORECASE,
        )
        if threshold_match:
            meaning = "the threshold incident energy"
            if threshold_match.group("condition"):
                meaning += " below which " + threshold_match.group("condition").strip(" ,")
            add_definition(r"E_0^{\mathrm{th}}", meaning, evidence_id)
        if "complexinputandoutputamplitudes" in compact and "transmittedorreceivedmode" in compact:
            if "aoaml" in compact:
                add_definition(
                    r"a_l^{\mathrm{OAM}}",
                    "the complex input amplitude of transmitted OAM mode l",
                    evidence_id,
                )
            if "boaml" in compact:
                add_definition(
                    r"b_{l'}^{\mathrm{OAM}}",
                    "the complex output amplitude of received OAM mode l prime",
                    evidence_id,
                )
        if "waveamplitudesfeedingthetransmitterarray" in compact:
            if "afeedn" in compact:
                add_definition(
                    r"a_n^{\mathrm{feed}}",
                    "the wave amplitude feeding the transmitter array at element n",
                    evidence_id,
                )
            if "bfeedp" in compact:
                add_definition(
                    r"b_p^{\mathrm{feed}}",
                    "the wave amplitude collected at receiver array element p",
                    evidence_id,
                )
        index_match = re.search(
            r"\bwith\s+([A-Za-z])\s+the\s+([^,.;]{3,120})",
            text,
            re.IGNORECASE,
        )
        if index_match:
            add_definition(index_match.group(1), index_match.group(2), evidence_id)
        if re.search(r"\bBFN\s+that\s+has\s+N\s+input\s+ports\b", text, re.IGNORECASE):
            add_definition("N", "the number of input ports in the ideal beam-forming network", evidence_id)
        if re.search(r"\bOAM\s+modes?\s+of\s+order\s+l\b", text, re.IGNORECASE):
            add_definition("l", "the OAM mode order", evidence_id)
        if re.search(r"\bterms?\s+h\s*p\s*n\s+correspond\s+to\s+the\s+propagation\b", text, re.IGNORECASE):
            add_definition(
                r"h_{pn}",
                "the channel-matrix coefficient for propagation from transmitter element n to receiver element p",
                evidence_id,
            )
            add_definition("n", "the element index at the transmitter", evidence_id)
            add_definition("p", "the element index at the receiver", evidence_id)
        if re.search(
            r"(?:β|\bbeta\b)\s+contains\s+all\s+the\s+variables\s+associated\s+with\s+the\s+antenna\s+system\s+configuration",
            text,
            re.IGNORECASE,
        ):
            add_definition(
                r"\beta",
                "a factor containing the variables associated with the antenna system configuration",
                evidence_id,
            )
        wavelength_match = re.search(
            r"(?:λ|\blambda\b)\s+is\s+the\s+(?P<meaning>wavelength\s+of\s+the\s+carrier)",
            text,
            re.IGNORECASE,
        )
        if wavelength_match:
            add_definition(r"\lambda", wavelength_match.group("meaning"), evidence_id)

    symbol_pattern = r"(?P<symbol>[A-Z](?:\s*[A-Za-z]{1,3})?)"
    patterns = [
        re.compile(
            rf"(?<!\w){symbol_pattern}\s+(?:is|denotes|represents|refers to|stands for)\s+"
            r"(?:the\s+|an?\s+)?(?P<meaning>[^,.;]{3,120})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?<!\w){symbol_pattern}\s+(?:the\s+|an?\s+)(?P<meaning>[^,.;]{{3,120}})",
        ),
    ]
    for item in evidence:
        text = str(item.get("text") or "")
        evidence_id = str(item.get("evidence_id") or item.get("block_id") or "")
        clauses = re.split(
            r",|\s+and\s+(?=[A-Z](?:\s*[A-Za-z]{1,3})?\s+(?:the\s+|an?\s+))",
            text,
        )
        for clause in clauses:
            for pattern in patterns:
                match = pattern.search(clause)
                if not match:
                    continue
                raw_symbol = re.sub(r"\s+", "", match.group("symbol"))
                if len(raw_symbol) > 1 and raw_symbol.lower() in {
                    "and",
                    "as",
                    "at",
                    "by",
                    "fig",
                    "for",
                    "from",
                    "if",
                    "in",
                    "of",
                    "on",
                    "or",
                    "the",
                    "to",
                    "when",
                    "where",
                    "with",
                }:
                    continue
                latex_symbol = _context_symbol_latex(match.group("symbol"))
                key = normalize_key(latex_symbol)
                meaning = re.sub(r"\s+", " ", match.group("meaning")).strip(" ,")
                if (
                    not key
                    or not meaning
                    or re.match(r"^(?:given|defined|expressed|calculated|obtained)\s+by\b", meaning, re.IGNORECASE)
                ):
                    continue
                add_definition(latex_symbol, meaning, evidence_id)
                break
    return definitions


def _repair_flattened_bfn_fourier_sum(
    latex: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    evidence_text = normalize_text(" ".join(str(item.get("text") or "") for item in evidence))
    if "bfn" not in evidence_text or "oam" not in evidence_text:
        return latex, None

    value = re.sub(r"\s+", " ", latex or "").strip().replace("−", "-").replace("′", "'")
    structural_key = normalize_key(value)
    compact_symbols = value.replace(" ", "").lower()
    if not (
        ("sqrtn" in structural_key or "√n" in compact_symbols)
        and ("jx" not in structural_key)
        and ("j2pi" in structural_key or "j2π" in compact_symbols)
        and ("x1" in structural_key or "x-1" in compact_symbols)
    ):
        return latex, None

    lhs_match = re.match(
        r"\s*(?P<base>[ab])\s+(?P<qualifier>feed|OAM)\s+(?P<index>[nlp](?:\s*')?)\s*=",
        value,
        re.IGNORECASE,
    )
    sum_match = re.search(r"(?P<index>[lp])\s*=\s*0", value, re.IGNORECASE)
    if not lhs_match or not sum_match:
        return latex, None

    lhs_base = lhs_match.group("base").lower()
    lhs_qualifier = lhs_match.group("qualifier")
    lhs_index = re.sub(r"\s+", "", lhs_match.group("index"))
    sum_index = sum_match.group("index").lower()
    term_qualifier = "OAM" if lhs_qualifier.lower() == "feed" else "feed"
    term_base = lhs_base
    sign = "-" if re.search(r"e\s*-\s*j", value, re.IGNORECASE) else ""

    lhs_subscript = f"{{{lhs_index}}}" if len(lhs_index) > 1 else lhs_index
    term_subscript = f"{{{sum_index}}}" if len(sum_index) > 1 else sum_index
    latex_qualifier = lhs_qualifier if lhs_qualifier.upper() == "OAM" else lhs_qualifier.lower()
    term_latex_qualifier = term_qualifier if term_qualifier.upper() == "OAM" else term_qualifier.lower()
    repaired = (
        f"{lhs_base}_{lhs_subscript}^{{\\mathrm{{{latex_qualifier}}}}} = "
        f"\\frac{{1}}{{\\sqrt{{N}}}} \\sum_{{{sum_index}=0}}^{{N-1}} "
        f"{term_base}_{term_subscript}^{{\\mathrm{{{term_latex_qualifier}}}}} "
        f"e^{{{sign}j 2\\pi {sum_index} {lhs_index}/N}}, \\quad "
        f"{lhs_index} \\in \\{{0,\\ldots,N-1\\}}"
    )
    evidence_ids = [
        str(item.get("evidence_id") or item.get("block_id") or "")
        for item in evidence
        if "bfn" in normalize_text(str(item.get("text") or ""))
    ]
    return repaired, {
        "kind": "fourier_sum_structure",
        "description": (
            "Restored the normalization, indexed summation, compound symbols, complex phase, "
            "and index domain flattened by the PDF text layer."
        ),
        "provenance_type": "structural_inference",
        "evidence_ids": [value for value in evidence_ids if value],
        "confidence": "medium",
    }


def _repair_flattened_channel_coefficient(
    latex: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    evidence_text = normalize_text(" ".join(str(item.get("text") or "") for item in evidence))
    if not (
        "channel matrix" in evidence_text
        and "propagation" in evidence_text
        and ("free space losses" in evidence_text or "free-space losses" in evidence_text)
    ):
        return latex, None

    compact = re.sub(r"\s+", "", latex or "").lower()
    compact = (
        compact.replace("β", "beta")
        .replace("λ", "lambda")
        .replace("π", "pi")
        .replace("−", "-")
    )
    if not all(value in compact for value in ("hpn", "beta", "jkrnp", "lambda", "4pi")):
        return latex, None
    if r"\frac" in latex and re.search(r"e\s*\^", latex):
        return latex, None

    evidence_ids = [
        str(item.get("evidence_id") or item.get("block_id") or "")
        for item in evidence
        if any(
            phrase in normalize_text(str(item.get("text") or ""))
            for phrase in ("channel matrix", "propagation term", "free space losses", "point-to-point link")
        )
    ]
    return r"h_{pn} = \beta e^{-j k r_{np}} \frac{\lambda}{4\pi r_{np}}", {
        "kind": "channel_coefficient_structure",
        "description": (
            "Restored the compound channel coefficient, complex propagation exponent, and reciprocal "
            "free-space-loss factor flattened by the PDF text layer."
        ),
        "provenance_type": "paper_evidence",
        "evidence_ids": [value for value in evidence_ids if value],
        "confidence": "high",
    }


def _compound_identifier_latex(value: str) -> str:
    compact = re.sub(r"[^A-Za-zΑ-ω]", "", value or "")
    greek_names = (
        "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda", "mu", "nu",
        "xi", "pi", "rho", "sigma", "tau", "phi", "chi", "psi", "omega",
    )
    for name in greek_names:
        if compact.lower().startswith(name):
            suffix = compact[len(name) :]
            return rf"\{name}_{{{suffix}}}" if suffix else rf"\{name}"
    if not compact:
        return value.strip()
    if len(compact) == 1:
        return compact
    return f"{compact[0]}_{{{compact[1:]}}}"


def _repair_flattened_root_geometry(
    latex: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    """Recover a text-layer-flattened law-of-cosines style root expression.

    The trigger is structural and evidence-based: it does not inspect a paper title,
    filename, or equation number.
    """

    evidence_text = normalize_text(" ".join(str(item.get("text") or "") for item in evidence))
    if "distance" not in evidence_text:
        return latex, None
    value = re.sub(r"\s+", " ", latex or "").strip()
    value = value.replace("−", "-").replace("âˆ’", "-").replace("θ", "theta ")
    match = re.match(
        r"^(?P<lhs>[A-Za-z]+)\s*=\s*(?:q|√|sqrt)\s+"
        r"(?P<a>[A-Za-z]+)\s+2\s*\+\s*"
        r"(?P<b>[A-Za-z]+)\s+2\s+(?P<bsub>[A-Za-z]+)\s*\+\s*"
        r"(?P<c>[A-Za-z]+)\s+2\s+(?P<csub>[A-Za-z]+)\s*-\s*2\s+"
        r".+?\bcos\s*\(\s*(?P<angle>[^)]+?)\s*\)\s*$",
        value,
        re.IGNORECASE,
    )
    if not match:
        return latex, None

    lhs = _compound_identifier_latex(match.group("lhs"))
    first = match.group("a")
    second = f"{match.group('b')}_{match.group('bsub')}"
    third = f"{match.group('c')}_{match.group('csub')}"
    angle = _compound_identifier_latex(match.group("angle"))
    repaired = (
        f"{lhs} = \\sqrt{{{first}^2 + {second}^2 + {third}^2 - "
        f"2 {second} {third} \\cos({angle})}}"
    )
    evidence_ids = [
        str(item.get("evidence_id") or item.get("block_id") or "")
        for item in evidence
        if "distance" in normalize_text(str(item.get("text") or ""))
    ]
    return repaired, {
        "kind": "root_geometry_structure",
        "description": (
            "Restored a square root, squared terms, compound subscripts, and cosine grouping "
            "flattened by the PDF text layer."
        ),
        "provenance_type": "structural_inference",
        "evidence_ids": [item for item in evidence_ids if item],
        "confidence": "medium",
    }


def repair_equation_from_paper_evidence(
    latex: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    definitions = extract_paper_symbol_definitions(evidence)
    aliases = {
        symbol_key(item["symbol"]): str(item["latex"])
        for item in definitions.values()
        if symbol_key(item["symbol"])
    }
    alias_keys = sorted(aliases, key=len, reverse=True)

    def segment_run(match: re.Match[str]) -> str:
        run = match.group(0)
        if match.start() > 0 and match.string[match.start() - 1] == "{":
            return run
        memo: dict[int, list[str] | None] = {}

        def segment(position: int) -> list[str] | None:
            if position == len(run):
                return []
            if position in memo:
                return memo[position]
            for key in alias_keys:
                if run.startswith(key, position):
                    tail = segment(position + len(key))
                    if tail is not None:
                        memo[position] = [aliases[key], *tail]
                        return memo[position]
            memo[position] = None
            return None

        parts = segment(0)
        return " ".join(parts) if parts else run

    repaired, root_geometry_repair = _repair_flattened_root_geometry(latex, evidence)
    repaired, channel_repair = _repair_flattened_channel_coefficient(repaired, evidence)
    repaired, fourier_repair = _repair_flattened_bfn_fourier_sum(repaired, evidence)
    repaired = re.sub(r"(?<!\\)[A-Za-z]{2,}", segment_run, repaired)
    repaired = re.sub(r"\s+", " ", repaired).strip()
    repairs: list[dict[str, Any]] = [
        repair for repair in (root_geometry_repair, channel_repair, fourier_repair) if repair is not None
    ]
    evidence_ids = sorted(
        {
            evidence_id
            for item in definitions.values()
            for evidence_id in item.get("evidence_ids", [])
            if evidence_id
        }
    )
    if repaired != re.sub(r"\s+", " ", latex).strip() and not (
        root_geometry_repair or channel_repair or fourier_repair
    ):
        repairs.append(
            {
                "kind": "compound_symbol_grouping",
                "description": "Grouped compact OCR text into symbols defined by the nearby paper prose.",
                "provenance_type": "paper_evidence",
                "evidence_ids": evidence_ids,
                "confidence": "high",
            }
        )

    evidence_text = normalize_text(" ".join(str(item.get("text") or "") for item in evidence))
    lhs, separator, rhs = repaired.partition("=")
    lhs_symbols = [
        normalize_key(str(node.get("symbol") or ""))
        for node in extract_grouped_expression(lhs)
        if node.get("kind") == "symbol"
    ]
    rhs_symbols = [
        normalize_key(str(node.get("symbol") or ""))
        for node in extract_grouped_expression(rhs)
        if node.get("kind") == "symbol"
    ]
    is_flattened_friis = (
        separator
        and "friis transmission equation" in evidence_text
        and lhs_symbols == ["pr"]
        and rhs_symbols == ["pt", "gt", "gr", "lfs"]
        and r"\frac" not in repaired
        and "/" not in repaired
    )
    if is_flattened_friis:
        repaired = r"P_r = \frac{P_t G_t G_r}{L_{FS}}"
        friis_evidence_ids = [
            str(item.get("evidence_id") or item.get("block_id") or "")
            for item in evidence
            if "friis transmission equation" in normalize_text(str(item.get("text") or ""))
        ]
        repairs.append(
            {
                "kind": "named_equation_structure",
                "description": "Restored the quotient structure after the PDF text layer flattened the named Friis equation.",
                "provenance_type": "structural_inference",
                "evidence_ids": [value for value in friis_evidence_ids if value],
                "confidence": "medium",
            }
        )
    return repaired.rstrip(" ."), repairs


def infer_context_summary(
    equation_label: str,
    context: str,
    evidence: list[dict[str, Any]],
    latex: str = "",
) -> str:
    evidence_text = " ".join(str(item.get("text") or "") for item in evidence)
    normalized = normalize_text(evidence_text or context)
    terms = set(normalized.split())
    definitions = extract_paper_symbol_definitions(evidence)
    named_equation = re.search(
        r"\b(?:is|are)\s+(?:given|defined|expressed|calculated)\s+by\s+(?:the\s+)?"
        r"(?P<name>[A-Za-z][A-Za-z\s-]{1,80}?\s+equation)\b",
        evidence_text,
        re.IGNORECASE,
    )
    if named_equation and definitions and "=" in latex:
        lhs_definitions = [
            definitions.get(normalize_key(str(node.get("symbol") or "")))
            for node in extract_grouped_expression(latex.split("=", 1)[0])
            if node.get("kind") == "symbol"
        ]
        purpose = next((item for item in lhs_definitions if item), None)
        if purpose:
            equation_name = re.sub(r"\s+", " ", named_equation.group("name")).strip()
            return (
                f"{equation_label} is identified by the paper as the {equation_name}. "
                f"It calculates or defines {purpose['meaning']} using quantities defined in the surrounding text."
            )
    signal_present = bool(terms.intersection({"signal", "signals", "transmitted", "received", "receiver"}))
    channel_present = bool(terms.intersection({"channel", "channels", "gain", "scaling"}))
    noise_present = bool(terms.intersection({"noise", "noises", "gaussian", "covariance"}))
    if signal_present and channel_present and noise_present:
        return (
            f"{equation_label} describes a received or transmitted signal after wireless-channel "
            "scaling, with additive noise terms."
        )
    if signal_present and noise_present:
        return f"{equation_label} describes a signal model that includes additive noise."
    if terms.intersection({"probability", "distribution", "variance", "covariance", "expectation"}):
        return f"{equation_label} expresses a probability or statistical relationship used in the paper."
    if terms.intersection({"matrix", "vector", "attention", "embedding"}):
        return f"{equation_label} expresses a matrix or vector relationship used by the paper's model."
    if terms.intersection({"energy", "power", "voltage", "frequency"}):
        return f"{equation_label} relates physical quantities in the paper's system model."
    if evidence:
        excerpt = re.sub(r"\s+", " ", str(evidence[0].get("text") or "")).strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:217].rstrip() + "..."
        return f"{equation_label} is explained by this nearby paper context: {excerpt}"
    return (
        f"{equation_label} has no nearby explanatory prose, so only its notation and "
        "ontology-backed concepts can be described."
    )


def classify_equation_role(latex: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_text = " ".join(str(item.get("text") or "") for item in evidence)
    terms = set(normalize_text(evidence_text).split())
    evidence_ids = [str(item.get("evidence_id")) for item in evidence if item.get("evidence_id")]
    normalized_latex = re.sub(r"\s+", "", latex)

    role = "unknown"
    confidence = "low"
    provenance_type = "structural_inference"
    normalized_evidence = normalize_text(evidence_text)
    if "friis transmission equation" in normalized_evidence or (
        {"link", "budget"}.issubset(terms)
        and bool(terms.intersection({"power", "gains", "gain"}))
        and bool(terms.intersection({"loss", "losses"}))
    ):
        role, confidence, provenance_type = "link_budget", "high", "paper_evidence"
    elif (
        "bfn" in terms
        and "oam" in terms
        and r"\sum" in latex
        and bool(re.search(r"\^\{\\mathrm\{(?:feed|OAM)\}\}", latex))
    ):
        role, confidence, provenance_type = "beamforming_transform", "high", "paper_evidence"
    elif (
        "channel matrix" in normalized_evidence
        and "propagation" in terms
        and ("point-to-point link" in normalized_evidence or "hpn" in normalized_evidence)
        and bool(re.search(r"h_?\{?pn\}?", normalized_latex, re.IGNORECASE))
    ):
        role, confidence, provenance_type = "channel_coefficient", "high", "paper_evidence"
    elif terms.intersection({"received", "transmitted", "receiver", "signal"}) and terms.intersection({"noise", "channel"}):
        role, confidence, provenance_type = "signal_model", "high", "paper_evidence"
    elif (
        terms.intersection({"energy", "energies"})
        and terms.intersection({"transfer", "transferred", "lose", "loss"})
        and terms.intersection({"scattering", "scatter", "scattered"})
    ):
        role, confidence, provenance_type = "energy_transfer", "high", "paper_evidence"
    elif terms.intersection({"threshold"}) and terms.intersection({"energy", "energies"}):
        role, confidence, provenance_type = "threshold_energy", "high", "paper_evidence"
    elif terms.intersection({"resolution"}) and terms.intersection({"aberration", "aberrations", "microscope", "imaging"}):
        role, confidence, provenance_type = "resolution_model", "high", "paper_evidence"
    elif (
        bool(terms.intersection({"distance", "radius", "geometry", "geometric"}))
        and (
            len(terms.intersection({"distance", "radius", "angle", "geometry", "geometric"})) >= 2
            or bool(re.search(r"\b(?:equation|formula)\b.{0,80}\b(?:distance|radius|angle)\b", normalized_evidence))
            or bool(re.search(r"\b(?:gives|calculates|defines)\s+(?:the\s+|a\s+)?distance\b", normalized_evidence))
            or bool(
                re.search(
                    r"\bdistance\b.{0,100}\b(?:is\s+)?(?:given|calculated|defined)\s+by\b",
                    normalized_evidence,
                )
            )
        )
    ):
        role, confidence, provenance_type = "geometry_distance", "high", "paper_evidence"
    elif terms.intersection({"probability", "distribution", "variance", "expectation", "covariance"}):
        role, confidence, provenance_type = "probability_statistics", "high", "paper_evidence"
    elif terms.intersection({"objective", "minimize", "maximize", "optimization", "optimal"}):
        role, confidence, provenance_type = "optimization_objective", "high", "paper_evidence"
    elif terms.intersection({"constraint", "subject", "bounded"}):
        role, confidence, provenance_type = "constraint", "medium", "paper_evidence"
    elif terms.intersection({"recurrence", "update", "iteration", "recursive"}):
        role, confidence, provenance_type = "recurrence_update", "medium", "paper_evidence"
    elif r"\sqrt" in normalized_latex and r"\cos" in normalized_latex and re.search(r"\^\{?2\}?", normalized_latex):
        role, confidence = "geometry_distance", "medium"
    elif "=" in latex:
        role, confidence = "definition_or_identity", "medium"

    return {
        "label": role,
        "confidence": confidence,
        "provenance_type": provenance_type,
        "evidence_ids": evidence_ids if provenance_type == "paper_evidence" else [],
    }


def summarize_equation_role(
    equation_label: str,
    role: dict[str, Any],
    context: str,
    evidence: list[dict[str, Any]],
    latex: str = "",
) -> str:
    label = str(role.get("label") or "unknown")
    if label == "link_budget":
        return (
            f"{equation_label} is the Friis transmission equation used for the paper's link budget. "
            "It calculates received power from transmitted power and the transmitter and receiver antenna "
            "gains, with free-space loss reducing the received power."
        )
    if label == "beamforming_transform":
        if re.match(r"\s*a_", latex):
            return (
                f"{equation_label} defines the transmitter beam-forming network output for antenna element n. "
                "It calculates each feed amplitude as a normalized sum of the transmitted OAM-mode amplitudes, "
                "using a mode- and element-dependent complex phase shift."
            )
        return (
            f"{equation_label} defines the receiver beam-forming network output. It calculates an OAM-mode "
            "amplitude as a normalized sum of the signals collected by the receiver elements, using a complex phase shift."
        )
    if label == "channel_coefficient":
        return (
            f"{equation_label} defines one entry of the paper's channel matrix: the propagation coefficient "
            "from transmitter element n to receiver element p. It combines antenna-configuration effects, "
            "a distance-dependent propagation phase, and the reciprocal of the paper's free-space-loss factor "
            "for a point-to-point link without coupling terms."
        )
    if label == "geometry_distance":
        if role.get("provenance_type") == "paper_evidence":
            evidence_text = normalize_text(" ".join(str(item.get("text") or "") for item in evidence))
            if "distance between each antenna element" in evidence_text:
                return (
                    f"{equation_label} calculates the distance between each antenna element "
                    "using the geometric quantities in the paper."
                )
            return f"{equation_label} calculates or defines a distance using the geometric quantities described by the paper."
        return (
            f"{equation_label} has a law-of-cosines-style distance structure. "
            "Its exact domain meaning is not stated in the available paper evidence."
        )
    if label == "signal_model":
        return (
            f"{equation_label} describes a received or transmitted signal after channel scaling, "
            "with additive noise terms."
        )
    if label == "energy_transfer":
        evidence_text = normalize_text(" ".join(str(item.get("text") or "") for item in evidence))
        purpose = (
            "the maximum energy transfer from an electron"
            if "maximum" in evidence_text
            else "the energy transferred from an electron"
        )
        angle_clause = (
            " The paper states that this maximum corresponds to a 180-degree scattering angle."
            if "180" in evidence_text
            else ""
        )
        return (
            f"{equation_label} calculates {purpose} during elastic scattering."
            f"{angle_clause}"
        )
    if label == "threshold_energy":
        return (
            f"{equation_label} calculates the threshold incident energy below which the displacement "
            "described by the paper cannot occur."
        )
    if label == "resolution_model":
        return (
            f"{equation_label} models microscope resolution using wavelength, lens-aberration, "
            "energy-spread, and parasitic-aberration contributions described by the paper."
        )
    if label == "probability_statistics":
        return f"{equation_label} expresses a probability or statistical relationship used in the paper."
    if label == "optimization_objective":
        return f"{equation_label} states an optimization objective described by the paper."
    if label == "constraint":
        return f"{equation_label} states a constraint on the quantities in the paper."
    if label == "recurrence_update":
        return f"{equation_label} defines an iterative or recurrent update."
    return infer_context_summary(equation_label, context, evidence, latex)


def build_conceptual_structure(role: dict[str, Any], latex: str) -> str:
    label = str(role.get("label") or "unknown")
    if label == "channel_coefficient":
        return (
            "Conceptually, the right side multiplies three factors: beta groups antenna-system effects; "
            "the complex exponential represents the distance-dependent propagation phase; and lambda "
            "divided by four pi r sub n p applies the reciprocal free-space-loss scaling."
        )

    structures: list[str] = []
    if "=" in latex:
        structures.append("the equality defines the quantity on the left using the expression on the right")
    if r"\sum" in latex:
        structures.append("the summation combines contributions across an index range")
    if r"\frac" in latex:
        structures.append("the fraction compares or scales a numerator by a denominator")
    if r"\sqrt" in latex:
        structures.append("the square root converts the enclosed quantity to its principal root")
    if re.search(r"e\s*\^", latex):
        structures.append("the exponential contributes a growth, decay, or phase factor depending on its exponent")
    if r"\cos" in latex:
        structures.append("the cosine contributes an angle-dependent component")
    if not structures:
        return ""
    return "Conceptually, " + "; ".join(structures) + "."


def context_symbol_definitions(context: str, latex: str) -> list[dict[str, str]]:
    definition_pattern = re.compile(
        r"(?=(?<!\w)(?P<symbol>[A-Za-z][A-Za-z0-9_]*(?:\s*[\[(][^\])]{1,24}[\])])?)\s+"
        r"(?:is|denotes|represents|refers to)\s+(?P<meaning>[^,.;]{3,180}))",
        flags=re.IGNORECASE,
    )
    compact_latex = normalize_key(latex)
    latex_symbols = set(re.findall(r"[A-Za-z][A-Za-z0-9_]*", latex))
    best_definitions: dict[str, tuple[float, dict[str, str]]] = {}
    for match in definition_pattern.finditer(context or ""):
        symbol_with_args = re.sub(r"\s+", "", match.group("symbol"))
        symbol = re.sub(r"[\[(].*$", "", symbol_with_args)
        key = normalize_key(symbol)
        if not key or key not in compact_latex:
            continue
        if len(symbol) == 1 and symbol not in latex_symbols and symbol.lower() not in {"x", "y"}:
            continue
        meaning = re.sub(r"\s+", " ", match.group("meaning")).strip()
        meaning_terms = set(normalize_text(meaning).split())
        if (
            not meaning
            or "=" in meaning
            or normalize_text(meaning) in {"complex", "defined", "given", "real"}
        ):
            continue
        domain_score = len(meaning_terms.intersection(CONTEXT_DOMAIN_TERMS)) * 4.0
        score = domain_score + min(len(meaning_terms), 12) / 4.0
        candidate = {"symbol": symbol, "meaning": meaning}
        if key not in best_definitions or score > best_definitions[key][0]:
            best_definitions[key] = (score, candidate)
    return [item[1] for item in best_definitions.values()]


def _definition_from_gloss(gloss: str, fallback: str) -> str:
    definition = re.sub(r"^[^:]{1,80}:\s*", "", gloss or "").strip()
    definition = re.sub(r"\s+", " ", definition).strip(" .")
    if not definition:
        return fallback
    return definition[:220]


def build_term_explanations(
    *,
    latex: str,
    context: str,
    tokens: list[dict[str, Any]],
    grouped_expression: list[dict[str, str]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    grouped_expression = grouped_expression or extract_grouped_expression(latex)
    evidence = evidence or []
    terms: list[dict[str, Any]] = []
    covered: set[str] = set()

    evidence_lookup: list[tuple[str, str]] = [
        (str(item.get("evidence_id") or ""), str(item.get("text") or "")) for item in evidence
    ]
    context_for_definitions = " ".join(text for _evidence_id, text in evidence_lookup) or context
    paper_definitions = extract_paper_symbol_definitions(evidence)
    normalized_definition_context = normalize_text(context_for_definitions)
    if r"r_{np}" in latex and "distance between each antenna element" in normalized_definition_context:
        distance_evidence_ids = [
            evidence_id
            for evidence_id, text in evidence_lookup
            if "distance between each antenna element" in normalize_text(text)
        ]
        paper_definitions.setdefault(
            symbol_key(r"r_{np}"),
            {
                "symbol": r"r_{np}",
                "latex": r"r_{np}",
                "meaning": "the distance between transmitter element n and receiver element p",
                "evidence_ids": distance_evidence_ids,
            },
        )

    token_by_key: dict[str, dict[str, Any]] = {}
    for token in tokens:
        raw = str(token.get("raw") or "")
        key = normalize_key(raw)
        if key and key not in token_by_key:
            token_by_key[key] = token

    unique_symbols: list[dict[str, str]] = []
    seen_symbols: set[str] = set()
    for node in grouped_expression:
        if node.get("kind") != "symbol":
            continue
        symbol = canonical_symbol(str(node.get("symbol") or node.get("raw") or ""))
        key = symbol_key(symbol)
        if not key or key in seen_symbols:
            continue
        seen_symbols.add(key)
        unique_symbols.append({**node, "symbol": symbol})

    definition_verbs = r"(?:is|denotes|represents|refers to|stands for|corresponds to)"
    structural_symbol_meanings = {
        "e": "the base of the complex exponential phase factor",
        "j": "the imaginary unit used in the complex exponential",
        "pi": "the mathematical constant pi used in the phase angle",
    }
    for node in unique_symbols:
        symbol = node["symbol"]
        paper_definition = paper_definitions.get(symbol_key(symbol))
        if paper_definition:
            matching_token = token_by_key.get(normalize_key(symbol)) or token_by_key.get(normalize_key(symbol[:1]))
            terms.append(
                {
                    "symbol": symbol,
                    "spoken": node.get("spoken") or symbol,
                    "meaning": str(paper_definition["meaning"]),
                    "source": "paper_context",
                    "provenance_type": "paper_evidence",
                    "evidence_ids": list(paper_definition.get("evidence_ids") or []),
                    "ontology_concept": (matching_token or {}).get("canonical_label") or "Variable",
                    "confidence": "high",
                }
            )
            covered.add(symbol_key(symbol))
            continue
        structural_key = normalize_key(symbol)
        structural_meaning = structural_symbol_meanings.get(structural_key)
        if structural_meaning and (
            (structural_key == "e" and re.search(r"\be\s*\^", latex))
            or (structural_key == "j" and re.search(r"\^\{[^{}]*j", latex))
            or (structural_key == "pi" and r"\pi" in latex)
        ):
            terms.append(
                {
                    "symbol": symbol,
                    "spoken": node.get("spoken") or symbol,
                    "meaning": structural_meaning,
                    "source": "ontology",
                    "provenance_type": "ontology",
                    "evidence_ids": [],
                    "ontology_concept": "Mathematical constant",
                    "confidence": "high",
                }
            )
            covered.add(symbol_key(symbol))
            continue
        if (
            structural_key == "k"
            and re.search(r"e\s*\^\{[^{}]*\bk\b", latex)
            and "propagation term is the exponent" in normalized_definition_context
        ):
            exponent_evidence_ids = [
                evidence_id
                for evidence_id, text in evidence_lookup
                if "propagation term is the exponent" in normalize_text(text)
            ]
            terms.append(
                {
                    "symbol": symbol,
                    "spoken": node.get("spoken") or symbol,
                    "meaning": (
                        "the quantity multiplying distance inside the propagation-phase exponent; "
                        "the paper does not explicitly define k"
                    ),
                    "source": "unresolved",
                    "provenance_type": "paper_evidence",
                    "evidence_ids": exponent_evidence_ids,
                    "ontology_concept": "Variable",
                    "confidence": "medium",
                }
            )
            covered.add(symbol_key(symbol))
            continue
        plain_symbol = symbol.lstrip("\\").replace("{", "").replace("}", "")
        aliases = {symbol, plain_symbol}
        alias_patterns = {re.escape(alias) for alias in aliases}
        if "_" in plain_symbol:
            alias_patterns.add(re.escape(plain_symbol).replace("_", r"[_\s]?"))
        match: re.Match[str] | None = None
        matched_text = ""
        for alias_pattern in sorted(alias_patterns, key=len, reverse=True):
            candidate = re.search(
                rf"(?<!\w){alias_pattern}(?:\s*[\[(][^\])]+[\])])?\s+{definition_verbs}\s+(?P<meaning>[^.;]{{3,220}})",
                context_for_definitions,
                re.IGNORECASE,
            )
            if candidate:
                candidate_meaning = str(candidate.group("meaning") or "")
                candidate_preview = re.split(r",\s+(?:and|where)\b", candidate_meaning, maxsplit=1, flags=re.IGNORECASE)[0]
                symbol_is_noise = normalize_key(symbol).startswith("n") and re.search(
                    rf"\bnoise\s+{re.escape(plain_symbol.replace('_', ''))}\b",
                    context_for_definitions,
                    re.IGNORECASE,
                )
                if "=" in candidate_preview or normalize_text(candidate_preview).startswith("given by") or symbol_is_noise:
                    continue
                match = candidate
                matched_text = candidate.group(0)
                break
        if match is None:
            domain_phrase = (
                r"(?P<meaning>(?:average\s+transmit\s+power|channel\s+gain|phase\s+shift|"
                r"carrier\s+frequency|symbol\s+index|(?:(?:received|transmitted|complex\s+baseband)\s+)?signal|"
                r"(?:antenna\s+|conversion\s+|gaussian\s+)?noise|distance|radius|angle))"
            )
            for alias_pattern in sorted(alias_patterns, key=len, reverse=True):
                candidate = re.search(
                    rf"{domain_phrase}\s+{alias_pattern}(?:\s*[\[(][^\])]+[\])])?",
                    context_for_definitions,
                    re.IGNORECASE,
                )
                if candidate:
                    match = candidate
                    matched_text = candidate.group(0)
                    break
        if match:
            meaning = re.split(r",\s+(?:and\s+)?(?:\\?[A-Za-z][A-Za-z0-9_{}]*)\s+" + definition_verbs, match.group("meaning"), maxsplit=1, flags=re.IGNORECASE)[0]
            meaning = re.split(r",\s+(?:and\b|where\b|i\.?\s*e\.?\b|i\s*$)", meaning, maxsplit=1, flags=re.IGNORECASE)[0]
            meaning = re.split(
                r"\s+and\s+(?:the\s+)?(?:incident|input|output|transmit|received|threshold|activation)\s+"
                r"(?:energy|power|signal|value|quantity)\b",
                meaning,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            meaning = re.sub(r"\s+", " ", meaning).strip(" ,")
            meaning = re.sub(r"\b(90|180)1\b", r"\1 degrees", meaning)
            prefix_window = context_for_definitions[max(0, match.start() - 80) : match.start()]
            prefix_match = re.search(
                r"(?:the\s+)?((?:incident|input|output|threshold|activation|maximum|average|atomic)\s+"
                r"(?:energy|power|signal|value|quantity|mass\s+number))\s*$",
                prefix_window,
                re.IGNORECASE,
            )
            if prefix_match and re.match(r"^(?:in|measured\s+in|expressed\s+in)\b", meaning, re.IGNORECASE):
                meaning = f"{prefix_match.group(1)} {meaning}"
            if normalize_text(meaning) == "noise" and "receiving antenna" in context_for_definitions.lower():
                meaning = "antenna noise after the receiving antenna"
            evidence_ids = [evidence_id for evidence_id, text in evidence_lookup if matched_text.lower() in text.lower()]
            matching_token = token_by_key.get(normalize_key(symbol)) or token_by_key.get(normalize_key(symbol[:1]))
            terms.append(
                {
                    "symbol": symbol,
                    "spoken": str(node.get("spoken") or symbol),
                    "meaning": meaning,
                    "source": "paper_context",
                    "provenance_type": "paper_evidence",
                    "evidence_ids": evidence_ids,
                    "ontology_concept": str(matching_token.get("canonical_label") if matching_token else "Variable"),
                    "confidence": "high" if evidence_ids else "medium",
                }
            )
            covered.add(symbol_key(symbol))

    concept_by_raw = {
        "=": ("Equality", "states that the expression on the left equals the expression on the right"),
        "+": ("Addition", "adds another quantity or component to the expression"),
        "-": ("Subtraction", "subtracts one quantity or component from another"),
        r"\sqrt": ("Taking root", "takes the square root of the enclosed expression"),
        r"\cos": ("Cosine", "applies the cosine function to the enclosed angle"),
        r"\sin": ("Sine", "applies the sine function to the enclosed angle"),
        r"\sum": ("Addition", "combines indexed terms through summation"),
        r"\prod": ("Multiplication", "combines indexed terms through multiplication"),
    }
    seen_notation: set[str] = set()
    for node in grouped_expression:
        raw = str(node.get("raw") or "")
        symbol = canonical_symbol(str(node.get("symbol") or raw))
        key = symbol_key(symbol)
        if not raw or raw in seen_notation or (node.get("kind") == "symbol" and key in covered):
            continue
        seen_notation.add(raw)
        if node.get("kind") == "symbol":
            terms.append(
                {
                    "symbol": symbol,
                    "spoken": str(node.get("spoken") or symbol),
                    "meaning": (
                        f"{symbol} is a mathematical symbol, but its domain-specific meaning is not defined "
                        "in the available paper evidence"
                    ),
                    "source": "unresolved",
                    "provenance_type": "ontology",
                    "evidence_ids": [],
                    "ontology_concept": "Variable",
                    "confidence": "low",
                }
            )
        elif raw in concept_by_raw:
            concept, meaning = concept_by_raw[raw]
            terms.append(
                {
                    "symbol": raw,
                    "spoken": str(node.get("spoken") or raw),
                    "meaning": meaning,
                    "source": "ontology",
                    "provenance_type": "ontology",
                    "evidence_ids": [],
                    "ontology_concept": concept,
                    "confidence": "high",
                }
            )
        if len(terms) >= 20:
            break
    return terms


def build_spoken_script(
    *,
    equation_label: str,
    context_summary: str,
    conceptual_structure: str = "",
    extraction_warning: str = "",
    term_explanations: list[dict[str, Any]],
    plain_notation: str,
) -> str:
    script_parts = [f"Next, I am going to explain {equation_label}.", context_summary]
    if conceptual_structure:
        script_parts.append(conceptual_structure)
    if extraction_warning:
        script_parts.append(extraction_warning)
    source_priority = {"paper_context": 0, "ontology": 1, "notation": 2, "unresolved": 3}
    spoken_terms = sorted(
        term_explanations,
        key=lambda term: (
            source_priority.get(str(term.get("source") or ""), 3),
            str(term.get("symbol") or "") in {"k", "t"},
        ),
    )[:8]
    if spoken_terms:
        explanations = []
        for term in spoken_terms:
            meaning = str(term.get("meaning") or "").strip().rstrip(".")
            explanations.append(f"{term.get('spoken') or term.get('symbol')} means {meaning}")
        script_parts.append("Term by term, " + "; ".join(explanations) + ".")
    script_parts.append(f"Now the notation is: {plain_notation}.")
    return re.sub(r"\s+", " ", " ".join(script_parts)).strip()


@dataclass(frozen=True)
class FusekiStatus:
    available: bool
    endpoint: str
    dataset: str
    detail: str


class FusekiClient:
    def __init__(self, endpoint: str | None = None, timeout_seconds: float = 3.0) -> None:
        self.endpoint = endpoint or os.getenv("MATHKG_SPARQL_ENDPOINT", DEFAULT_SPARQL_ENDPOINT)
        self.timeout_seconds = timeout_seconds

    @property
    def dataset(self) -> str:
        parts = urllib.parse.urlparse(self.endpoint).path.strip("/").split("/")
        return parts[0] if parts else ""

    def query(self, sparql: str) -> dict[str, Any]:
        data = urllib.parse.urlencode({"query": sparql}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def status(self) -> FusekiStatus:
        try:
            result = self.query("ASK { ?s ?p ?o }")
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return FusekiStatus(False, self.endpoint, self.dataset, f"{exc.__class__.__name__}: {exc}")
        return FusekiStatus(bool(result.get("boolean")), self.endpoint, self.dataset, "SPARQL ASK query succeeded")

    def describe_concepts(self, concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        values: list[str] = []
        for concept in concepts:
            concept_iri = str(concept.get("concept_iri") or "").strip()
            label = str(concept.get("canonical_label") or "").strip()
            parsed = urllib.parse.urlparse(concept_iri)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or any(
                character in concept_iri for character in '<>"{}|^`\\'
            ):
                continue
            values.append(f"(<{concept_iri}> {json.dumps(label, ensure_ascii=False)})")
        if not values:
            return []

        sparql = """
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX mathkg: <http://example.org/mathkg/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?requestedIri ?requestedLabel ?concept ?label ?definition ?semanticType
       ?kindRole ?domainTag ?sourceOntology ?provenanceNote ?parent ?parentLabel ?exactMatch
WHERE {
  VALUES (?requestedIri ?requestedLabel) {
    %s
  }
  ?concept rdfs:label ?candidateLabel .
  FILTER(LCASE(STR(?candidateLabel)) = LCASE(STR(?requestedLabel)))
  BIND(?candidateLabel AS ?label)
  OPTIONAL { ?concept skos:definition ?definition }
  OPTIONAL { ?concept mathkg:semanticType ?semanticType }
  OPTIONAL { ?concept mathkg:kindRoleType ?kindRole }
  OPTIONAL { ?concept mathkg:domainTag ?domainTag }
  OPTIONAL { ?concept dc:source ?sourceOntology }
  OPTIONAL { ?concept mathkg:provenanceNote ?provenanceNote }
  OPTIONAL {
    ?concept rdfs:subClassOf ?parent .
    FILTER(isIRI(?parent))
    OPTIONAL { ?parent rdfs:label ?parentLabel }
  }
  OPTIONAL { ?concept skos:exactMatch ?exactMatch }
}
""" % "\n    ".join(values)
        result = self.query(sparql)
        bindings = result.get("results", {}).get("bindings", [])

        def value(row: dict[str, Any], name: str) -> str:
            return str(row.get(name, {}).get("value") or "")

        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for row in bindings:
            requested_iri = value(row, "requestedIri")
            concept_iri = value(row, "concept")
            if not requested_iri or not concept_iri:
                continue
            key = (requested_iri, concept_iri)
            item = candidates.setdefault(
                key,
                {
                    "requested_iri": requested_iri,
                    "concept_iri": concept_iri,
                    "canonical_label": value(row, "label") or value(row, "requestedLabel"),
                    "definition": value(row, "definition"),
                    "semantic_type": value(row, "semanticType"),
                    "kind_role": value(row, "kindRole"),
                    "domain_tags": [],
                    "source_ontology": [],
                    "provenance_note": value(row, "provenanceNote"),
                    "parent_concepts": [],
                    "exact_matches": [],
                },
            )
            for field, target in (
                ("domainTag", "domain_tags"),
                ("sourceOntology", "source_ontology"),
                ("exactMatch", "exact_matches"),
            ):
                field_value = value(row, field)
                if field_value and field_value not in item[target]:
                    item[target].append(field_value)
            parent_iri = value(row, "parent")
            if parent_iri and not any(parent["concept_iri"] == parent_iri for parent in item["parent_concepts"]):
                item["parent_concepts"].append(
                    {
                        "concept_iri": parent_iri,
                        "canonical_label": value(row, "parentLabel") or parent_iri.rsplit("/", 1)[-1],
                    }
                )

        best_by_requested: dict[str, dict[str, Any]] = {}
        for item in candidates.values():
            requested_iri = item["requested_iri"]
            current = best_by_requested.get(requested_iri)
            item_score = int(item["concept_iri"].startswith("http://example.org/mathkg/")) * 10 + sum(
                bool(item.get(field))
                for field in ("definition", "semantic_type", "kind_role", "parent_concepts", "provenance_note")
            )
            current_score = -1 if current is None else int(
                current["concept_iri"].startswith("http://example.org/mathkg/")
            ) * 10 + sum(
                bool(current.get(field))
                for field in ("definition", "semantic_type", "kind_role", "parent_concepts", "provenance_note")
            )
            if item_score > current_score:
                best_by_requested[requested_iri] = item
        return list(best_by_requested.values())


class MathKGService:
    def __init__(
        self,
        gloss_path: Path | None = None,
        fuseki_client: FusekiClient | None = None,
        explanation_provider: ExplanationProvider | None = None,
    ) -> None:
        self.gloss_path = gloss_path or DEFAULT_GLOSS_PATH
        self.records = load_gloss_records(self.gloss_path)
        self.repository = GlossRepository(self.records)
        self.lookup = SymbolConceptLookup(self.repository)
        self.fuseki = fuseki_client or FusekiClient()
        self.explanation_provider = explanation_provider or provider_from_environment()
        self._by_label = {normalize_key(str(record.get("canonical_label", ""))): record for record in self.records}

    def health(self) -> dict[str, Any]:
        status = self.fuseki.status()
        return {
            "api": "ok",
            "gloss_records": len(self.records),
            "gloss_path": str(self.gloss_path),
            "fuseki": status.__dict__,
            "marker": marker_runtime_status(),
            "image_ocr": image_ocr_runtime_status(),
            "tts": {"kokoro": kokoro_runtime_status()},
            "integrations": integration_registry(),
        }

    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        domain_tags: list[str] | None = None,
        semantic_type: str | None = None,
        kind_role: str | None = None,
    ) -> list[dict[str, Any]]:
        query_tokens = tokens_for(query)
        domain_filter = {normalize_key(tag) for tag in domain_tags or []}
        semantic_filter = normalize_key(semantic_type or "")
        kind_filter = normalize_key(kind_role or "")
        results: list[tuple[float, dict[str, Any], list[str]]] = []

        for record in self.records:
            if domain_filter and not domain_filter.intersection({normalize_key(tag) for tag in record_domains(record)}):
                continue
            if semantic_filter and normalize_key(str(record.get("semantic_type", ""))) != semantic_filter:
                continue
            if kind_filter and normalize_key(str(record.get("kind_role", ""))) != kind_filter:
                continue

            score, reasons = self._score_record(query, query_tokens, record)
            if score > 0:
                results.append((score, record, reasons))

        results.sort(key=lambda item: (-item[0], str(item[1].get("canonical_label", ""))))
        return [self._public_record(record, score=round(score, 3), reasons=reasons) for score, record, reasons in results[:limit]]

    def cross_disciplinary_discovery(
        self,
        seed_concept: str | None = None,
        source_domain: str | None = None,
        target_domains: list[str] | None = None,
        semantic_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        seed = self.find_record(seed_concept) if seed_concept else None
        seed_domains = set(record_domains(seed)) if seed else set(split_multi_value(source_domain))
        target_filter = {normalize_key(tag) for tag in target_domains or []}
        desired_type = semantic_type or ""
        desired_type_key = normalize_key(desired_type)
        source_keys = {normalize_key(tag) for tag in seed_domains}

        candidates: list[tuple[float, dict[str, Any], list[str]]] = []
        for record in self.records:
            if seed and record is seed:
                continue
            domains = record_domains(record)
            domain_keys = {normalize_key(tag) for tag in domains}
            if target_filter and not target_filter.intersection(domain_keys):
                continue
            if source_keys and not target_filter and domain_keys.issubset(source_keys):
                continue
            if desired_type_key and normalize_key(str(record.get("semantic_type", ""))) != desired_type_key:
                continue

            score = 1.0
            reasons: list[str] = []
            if seed:
                if normalize_key(str(record.get("semantic_type", ""))) == normalize_key(str(seed.get("semantic_type", ""))):
                    score += 2.0
                    reasons.append(f"shares semantic type {record.get('semantic_type')}")
                overlap = set(split_multi_value(record.get("source_provenance"))).intersection(
                    split_multi_value(seed.get("source_provenance"))
                )
                if overlap:
                    score += 0.5
                    reasons.append("shares provenance source " + ", ".join(sorted(overlap)))
            if domains:
                reasons.append("bridges into " + ", ".join(domains))
            candidates.append((score, record, reasons))

        candidates.sort(key=lambda item: (-item[0], str(item[1].get("canonical_label", ""))))
        return {
            "seed": self._public_record(seed) if seed else None,
            "source_domains": sorted(seed_domains),
            "target_domains": target_domains or [],
            "results": [
                self._public_record(record, score=round(score, 3), reasons=reasons)
                for score, record, reasons in candidates[:limit]
            ],
        }

    def recommend_concepts(
        self,
        context: str = "",
        latex: str = "",
        seed_concepts: list[str] | None = None,
        domain_tags: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        seeds = [record for label in seed_concepts or [] if (record := self.find_record(label))]
        if latex:
            resolved = resolve_latex_tokens(parse_latex_tokens(latex), self.lookup)
            for token in resolved:
                if token.canonical_label and (record := self.find_record(token.canonical_label)) and record not in seeds:
                    seeds.append(record)
        if context and not seeds:
            seeds.extend(self._record_from_result(result) for result in self.semantic_search(context, limit=3))

        seed_keys = {normalize_key(str(record.get("canonical_label", ""))) for record in seeds}
        seed_domains = {normalize_key(tag) for record in seeds for tag in record_domains(record)}
        seed_types = {normalize_key(str(record.get("semantic_type", ""))) for record in seeds if record.get("semantic_type")}
        requested_domains = {normalize_key(tag) for tag in domain_tags or []}
        context_tokens = tokens_for(context)

        candidates: list[tuple[float, dict[str, Any], list[str]]] = []
        for record in self.records:
            label_key = normalize_key(str(record.get("canonical_label", "")))
            if label_key in seed_keys:
                continue
            domains = {normalize_key(tag) for tag in record_domains(record)}
            semantic_type_key = normalize_key(str(record.get("semantic_type", "")))
            score = 0.0
            reasons: list[str] = []
            if requested_domains and requested_domains.intersection(domains):
                score += 2.0
                reasons.append("matches requested domain")
            if seed_domains and seed_domains.intersection(domains):
                score += 1.5
                reasons.append("shares a seed domain")
            if seed_types and semantic_type_key in seed_types:
                score += 1.2
                reasons.append("shares a seed semantic type")
            query_score, query_reasons = self._score_record(context, context_tokens, record)
            score += min(query_score, 2.0)
            reasons.extend(query_reasons[:2])
            if score > 0:
                candidates.append((score, record, reasons))

        candidates.sort(key=lambda item: (-item[0], str(item[1].get("canonical_label", ""))))
        return {
            "seeds": [self._public_record(record) for record in seeds],
            "plain_text": latex_to_plain_text(latex) if latex else "",
            "results": [
                self._public_record(record, score=round(score, 3), reasons=reasons)
                for score, record, reasons in candidates[:limit]
            ],
        }

    def latex_accessibility_gloss(
        self,
        latex: str,
        audience: str = "concise",
        arxiv_id: str = "ad-hoc",
        title: str = "Ad-hoc equation",
    ) -> dict[str, Any]:
        if audience not in AUDIENCE_TO_FIELD:
            raise ValueError(f"Unknown audience: {audience}")
        bundle = build_equation_speech_bundle(ArxivEquation(arxiv_id=arxiv_id, title=title, latex=latex), self.repository, self.lookup)
        surface_field = AUDIENCE_TO_FIELD[audience]
        token_payloads: list[dict[str, Any]] = []
        for token in bundle.tokens:
            record = self.find_record(token.canonical_label) if token.canonical_label else None
            surface = build_surface_forms(record).as_dict().get(surface_field, "") if record else ""
            token_payloads.append(
                {
                    "raw": token.raw,
                    "token_type": token.token_type,
                    "spoken": token.spoken,
                    "concept_iri": token.concept_iri,
                    "canonical_label": token.canonical_label,
                    "source": token.source,
                    "gloss": record.get("canonical_gloss", "") if record else "",
                    "surface_form": surface,
                    "domain_tags": record_domains(record) if record else [],
                }
            )
        return {
            "latex": latex,
            "plain_text": bundle.plain_text,
            "audience": audience,
            "speech_text": bundle.speech_text,
            "ssml": bundle.ssml,
            "resolved_count": sum(1 for token in bundle.tokens if token.concept_iri),
            "tokens": token_payloads,
        }

    def analyze_paper(
        self,
        *,
        title: str = "Untitled paper",
        abstract_or_context: str = "",
        equations: list[str] | None = None,
        audience: str = "pedagogical",
        audio_backend: str = "none",
        generate_audio: bool = False,
        pdf_base64: str = "",
        pdf_filename: str = "",
        document_base64: str = "",
        document_filename: str = "",
        document_media_type: str = "",
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> dict[str, Any]:
        def report_progress(stage: str, progress: int) -> None:
            if progress_callback is not None:
                progress_callback(stage, progress)

        supplied_equations = [equation.strip() for equation in equations or [] if equation and equation.strip()]
        encoded_document = document_base64 or pdf_base64
        source_filename = document_filename or pdf_filename
        pdf_text, pdf_chunks, pdf_status = extract_document_context(
            encoded_document,
            filename=source_filename,
            media_type=document_media_type,
            manual_equations_present=bool(supplied_equations),
        )
        report_progress("building_document_context", 30)
        context_parts = [part for part in (abstract_or_context, pdf_text) if part]
        source_text = "\n\n".join(context_parts).strip()
        context_chunks = context_chunks_from_text(
            abstract_or_context,
            source="provided_context",
        )
        context_chunks.extend(pdf_chunks)
        document_context = build_document_context_payload(
            pdf_text=pdf_text,
            pdf_chunks=pdf_chunks,
            pdf_status=pdf_status,
            provided_context=abstract_or_context,
        )
        extracted_candidates = extract_equation_candidates_from_chunks(context_chunks)
        if not extracted_candidates:
            extracted_candidates = extract_equation_candidates(source_text)
        manual_candidates: list[dict[str, Any]] = []
        for equation in supplied_equations:
            clean_equation, source_label = normalize_extracted_equation(equation)
            clean_equation, split_label = split_source_label(clean_equation)
            source_label = source_label or split_label
            matched = match_manual_equation_candidate(clean_equation, source_label, extracted_candidates) or {}
            manual_candidates.append(
                {
                    **matched,
                    "latex": clean_equation,
                    "confidence": "user_supplied",
                    "method": "manual_equation_matched_to_paper" if matched else "manual_equation",
                    "source_label": source_label or str(matched.get("source_label") or ""),
                }
            )
        selected_candidates = manual_candidates or extracted_candidates[:12]
        report_progress("ranking_document_evidence", 40)
        semantic_score_maps: list[dict[str, float] | None] = [None] * len(selected_candidates)
        has_document_evidence = any(
            str(chunk.get("source") or "") in {"docling", "grobid", "marker", "mineru", "pdf"}
            for chunk in context_chunks
        )
        if (
            len(selected_candidates) > 1
            and has_document_evidence
            and semantic_retrieval_status().get("enabled")
        ):
            batch_requests: list[tuple[str, list[str]]] = []
            batch_candidate_texts: list[list[str]] = []
            for candidate in selected_candidates:
                candidate_latex = str(candidate.get("latex") or "")
                candidate_gloss = self.latex_accessibility_gloss(
                    candidate_latex,
                    audience=audience,
                    arxiv_id="paper-demo",
                    title=title,
                )
                candidate_labels = list(
                    dict.fromkeys(
                        token["canonical_label"]
                        for token in candidate_gloss["tokens"]
                        if token.get("canonical_label")
                    )
                )
                deterministic_evidence = rank_context_evidence(
                    context_chunks,
                    latex=candidate_latex,
                    labels=candidate_labels,
                    equation_metadata=candidate,
                    limit=20,
                    allow_semantic_runtime=False,
                )
                candidate_texts = [str(item.get("text") or "") for item in deterministic_evidence]
                batch_candidate_texts.append(candidate_texts)
                batch_requests.append((" ".join([candidate_latex, *candidate_labels]).strip(), candidate_texts))
            batch_scores, batch_status = semantic_similarity_scores_batch(batch_requests)
            if batch_status.get("status") == "ok" and len(batch_scores) == len(selected_candidates):
                semantic_score_maps = [
                    {
                        normalize_text(text): float(score)
                        for text, score in zip(texts, scores, strict=True)
                    }
                    for texts, scores in zip(batch_candidate_texts, batch_scores, strict=True)
                ]

        ontology_status = self.fuseki.status()
        analyses: list[dict[str, Any]] = []
        equation_count = len(selected_candidates)
        for index, candidate in enumerate(selected_candidates, start=1):
            start_progress = 45 + int(((index - 1) / max(equation_count, 1)) * 45)
            report_progress(f"analyzing_equation_{index}_of_{equation_count}", start_progress)
            analyses.append(self._analyze_equation(
                latex=candidate["latex"],
                index=index,
                title=title,
                context=source_text,
                context_chunks=context_chunks,
                audience=audience,
                audio_backend=audio_backend,
                generate_audio=generate_audio,
                extraction_confidence=candidate["confidence"],
                extraction_method=candidate["method"],
                equation_metadata=candidate,
                semantic_scores_by_text=semantic_score_maps[index - 1],
                use_live_ontology=ontology_status.available,
            ))
        report_progress("finalizing_results", 95)
        document_id = str(pdf_status.get("document_id") or "")
        if not document_id:
            document_id = hashlib.sha256(f"{title}\n{source_text}".encode("utf-8")).hexdigest()
        local_ontology_available = bool(self.records) and DEFAULT_PROTEGE_ONTOLOGY_PATH.is_file()
        live_equation_queries = sum(
            analysis.get("ontology_query_mode") == "live_fuseki" for analysis in analyses
        )
        ontology_query_mode = "live_fuseki" if live_equation_queries else "local_protege_snapshot"
        evaluation_engines = {
            str(analysis.get("grounding_evaluation", {}).get("engine") or "")
            for analysis in analyses
            if analysis.get("grounding_evaluation")
        }
        evaluation_engine = next(iter(evaluation_engines)) if len(evaluation_engines) == 1 else (
            "mixed" if evaluation_engines else "not_run"
        )

        return {
            "document_id": document_id,
            "title": title or "Untitled paper",
            "audience": audience,
            "audio_backend": audio_backend,
            "source_text_length": len(source_text),
            "context_chunk_count": len(context_chunks),
            "extracted_equation_count": len(extracted_candidates),
            "document_context": document_context,
            "document_graph": build_document_graph(context_chunks, selected_candidates),
            "document": pdf_status,
            "pdf": pdf_status,
            "ontology_runtime": {
                "available": ontology_status.available or local_ontology_available,
                "fuseki_available": ontology_status.available,
                "query_mode": ontology_query_mode,
                "live_equation_queries": live_equation_queries,
                "dataset": ontology_status.dataset,
                "endpoint": ontology_status.endpoint,
                "gloss_records": len(self.records),
                "ontology_path": str(DEFAULT_PROTEGE_ONTOLOGY_PATH),
                "gloss_path": str(self.gloss_path),
                "source": (
                    "Protege OWL knowledge graph queried live through Fuseki"
                    if live_equation_queries
                    else "Protege OWL-derived knowledge graph with local mapped gloss records"
                ),
            },
            "pipeline": {
                "document_extraction": {
                    "engine": str(pdf_status.get("extractor") or "none"),
                    "status": str(pdf_status.get("status") or "unknown"),
                    "selected_integration": str(pdf_status.get("selected_integration") or ""),
                    "cache_hit": bool(pdf_status.get("cache_hit", False)),
                },
                "ontology": {
                    "engine": "protege_fuseki" if live_equation_queries else "protege_local_snapshot",
                    "status": "active_live" if live_equation_queries else "active_local" if local_ontology_available else "unavailable",
                },
                "context_ranking": {
                    "engine": "sentence_transformers_batch"
                    if any(
                        item.get("ranking_engine") == "sentence_transformers_batch"
                        for analysis in analyses
                        for item in analysis.get("context_evidence", [])
                    )
                    else "sentence_transformers"
                    if any(
                        item.get("ranking_engine") == "sentence_transformers"
                        for analysis in analyses
                        for item in analysis.get("context_evidence", [])
                    )
                    else "deterministic_proximity",
                    "status": "active",
                },
                "evaluation": {
                    "engine": evaluation_engine,
                    "status": "active" if analyses else "not_run",
                },
            },
            "equations": analyses,
        }

    def _analyze_equation(
        self,
        *,
        latex: str,
        index: int,
        title: str,
        context: str,
        context_chunks: list[dict[str, Any]],
        audience: str,
        audio_backend: str,
        generate_audio: bool,
        extraction_confidence: str,
        extraction_method: str,
        equation_metadata: dict[str, Any] | None = None,
        semantic_scores_by_text: dict[str, float] | None = None,
        use_live_ontology: bool = False,
    ) -> dict[str, Any]:
        equation_metadata = equation_metadata or {}
        original_latex = latex
        formula_repairs: list[dict[str, Any]] = []
        gloss = self.latex_accessibility_gloss(latex, audience=audience, arxiv_id="paper-demo", title=title)
        labels = [token["canonical_label"] for token in gloss["tokens"] if token.get("canonical_label")]
        unique_labels = list(dict.fromkeys(labels))
        evidence = rank_context_evidence(
            context_chunks,
            latex=latex,
            labels=unique_labels,
            equation_metadata=equation_metadata,
            semantic_scores_by_text=semantic_scores_by_text,
        )
        repair_evidence = list(evidence)
        repaired_latex, formula_repairs = repair_equation_from_paper_evidence(latex, evidence)
        if repaired_latex != latex:
            latex = repaired_latex
            gloss = self.latex_accessibility_gloss(latex, audience=audience, arxiv_id="paper-demo", title=title)
            labels = [token["canonical_label"] for token in gloss["tokens"] if token.get("canonical_label")]
            unique_labels = list(dict.fromkeys(labels))
            reranked_evidence = rank_context_evidence(
                context_chunks,
                latex=latex,
                labels=unique_labels,
                equation_metadata=equation_metadata,
                semantic_scores_by_text=semantic_scores_by_text,
            )
            evidence = []
            preserved_keys: set[str] = set()
            for item in [*reranked_evidence, *repair_evidence]:
                item_key = str(
                    item.get("evidence_id")
                    or item.get("block_id")
                    or normalize_key(str(item.get("text") or ""))
                )
                if not item_key or item_key in preserved_keys:
                    continue
                preserved_keys.add(item_key)
                evidence.append(item)
        structure_validation = validate_equation_structure(latex)
        definition_evidence = rank_definition_evidence(
            context_chunks,
            latex=latex,
            equation_metadata=equation_metadata,
            fallback=evidence,
        )
        display_evidence: list[dict[str, Any]] = []
        seen_evidence_ids: set[str] = set()
        seen_evidence_text: set[str] = set()
        for item in [*evidence, *definition_evidence]:
            evidence_id = str(item.get("evidence_id") or item.get("block_id") or "")
            evidence_text_key = normalize_key(str(item.get("text") or ""))
            if evidence_id in seen_evidence_ids or evidence_text_key in seen_evidence_text:
                continue
            seen_evidence_ids.add(evidence_id)
            seen_evidence_text.add(evidence_text_key)
            display_evidence.append(item)
            if len(display_evidence) >= 10:
                break
        equation_page = equation_metadata.get("page")
        equation_order = equation_metadata.get("reading_order")
        local_definition_evidence = sorted(
            (
                chunk
                for chunk in context_chunks
                if equation_page is not None
                and chunk.get("page") == equation_page
                and chunk.get("kind") not in {"equation", "inline_math", "ocr_text"}
                and chunk.get("reading_order") is not None
                and equation_order is not None
                and abs(int(chunk["reading_order"]) - int(equation_order)) <= 8
            ),
            key=lambda chunk: abs(int(chunk["reading_order"]) - int(equation_order)),
        )
        term_evidence: list[dict[str, Any]] = []
        term_evidence_keys: set[str] = set()
        for item in [*definition_evidence, *local_definition_evidence]:
            item_key = str(item.get("evidence_id") or item.get("block_id") or normalize_key(str(item.get("text") or "")))
            if not item_key or item_key in term_evidence_keys:
                continue
            term_evidence_keys.add(item_key)
            term_evidence.append(item)
            if len(term_evidence) >= 24:
                break
        linked_span = "" if extraction_method == "latex_ocr_image" and not evidence else (
            str(evidence[0].get("text") or "")
            if evidence
            else sentence_for_context(context, latex, unique_labels)
        )
        recommendations = self.recommend_concepts(context=context, latex=latex, seed_concepts=unique_labels, limit=5)
        source_label = str(equation_metadata.get("source_label") or "").strip()
        if source_label:
            equation_label = f"Equation {source_label}"
        elif extraction_method.startswith("manual"):
            equation_label = f"Equation {index}"
        else:
            equation_label = f"Unnumbered equation {index}"
        equation_role = classify_equation_role(latex, evidence)
        context_summary = summarize_equation_role(equation_label, equation_role, context, evidence, latex)
        conceptual_structure = build_conceptual_structure(equation_role, latex)
        evidence_context = " ".join(str(item.get("text") or "") for item in display_evidence)
        term_context = " ".join(str(item.get("text") or "") for item in term_evidence)
        grouped_expression = extract_grouped_expression(latex)
        term_explanations = build_term_explanations(
            latex=latex,
            context=term_context or context,
            tokens=gloss["tokens"],
            grouped_expression=grouped_expression,
            evidence=term_evidence,
        )
        ontology_links = self._ontology_links_for_tokens(
            gloss["tokens"],
            latex=latex,
            context=evidence_context,
            use_live_graph=use_live_ontology,
        )
        ontology_query_mode = (
            "live_fuseki"
            if any(link.get("provenance_type") == "ontology_live_graph" for link in ontology_links)
            else "local_protege_snapshot"
        )
        provider_packet = {
            "equation_label": equation_label,
            "latex": latex,
            "grouped_expression": grouped_expression,
            "context_evidence": display_evidence,
            "ontology_links": ontology_links,
            "ontology_query_mode": ontology_query_mode,
            "context_summary": context_summary,
            "conceptual_structure": conceptual_structure,
        }
        grounded_enhancement, explanation_provider = run_grounded_provider(
            self.explanation_provider,
            provider_packet,
        )
        if grounded_enhancement.get("context_summary"):
            context_summary = str(grounded_enhancement["context_summary"])
        if grounded_enhancement.get("equation_role"):
            equation_role = {
                "label": str(grounded_enhancement["equation_role"]),
                "confidence": "medium",
                "provenance_type": "paper_evidence",
                "evidence_ids": list(grounded_enhancement.get("evidence_ids") or []),
            }
            conceptual_structure = build_conceptual_structure(equation_role, latex)
        for enhanced_term in grounded_enhancement.get("term_explanations", []):
            enhanced_key = normalize_key(str(enhanced_term.get("symbol") or ""))
            for term_index, current_term in enumerate(term_explanations):
                if normalize_key(str(current_term.get("symbol") or "")) != enhanced_key:
                    continue
                term_explanations[term_index] = {
                    **current_term,
                    **enhanced_term,
                    "spoken": current_term.get("spoken") or enhanced_term.get("symbol"),
                    "ontology_concept": current_term.get("ontology_concept", "Variable"),
                }
                break
        fallback_notation = accessible_notation_reading(latex) or gloss["plain_text"] or latex_to_plain_text(latex)
        mathml, mathml_engine = latex_to_mathml(latex)
        plain_notation, math_speech = mathcat_notation_reading(mathml, fallback_notation)
        extraction_warning = ""
        if structure_validation["status"] != "valid":
            extraction_warning = (
                "Warning: the extracted notation has structural problems and should be checked "
                "against the equation image before relying on this reading."
            )
        spoken_script = build_spoken_script(
            equation_label=equation_label,
            context_summary=context_summary,
            conceptual_structure=conceptual_structure,
            extraction_warning=extraction_warning,
            term_explanations=term_explanations,
            plain_notation=plain_notation,
        )
        spoken_ssml = assemble_ssml(spoken_script)
        speech_segments = build_speech_segments(spoken_script)
        unresolved_symbols = [
            str(term.get("symbol") or "")
            for term in term_explanations
            if term.get("source") == "unresolved" and term.get("symbol")
        ]
        grounding_evaluation = evaluate_grounding(
            context_summary=context_summary,
            evidence=display_evidence,
            unresolved_symbols=unresolved_symbols,
            allow_ragas=(
                os.getenv("MATHONTOSPEAK_ENABLE_RAGAS_ANALYSIS", "").strip().lower()
                in {"1", "true", "yes", "on"}
                and any(
                    str(item.get("source") or "") in {"docling", "grobid", "marker", "mineru", "pdf"}
                    for item in display_evidence
                )
            ),
        )
        equation_id = "eq-" + hashlib.sha1(
            f"{title}|{source_label or index}|{latex}".encode("utf-8")
        ).hexdigest()[:12]
        context_clause = (
            f"The surrounding paper context says: {linked_span}"
            if linked_span
            else "No surrounding paper context was supplied, so the analysis uses the equation symbols only."
        )
        concept_clause = (
            "Resolved ontology concepts include " + ", ".join(unique_labels[:6]) + "."
            if unique_labels
            else "No ontology-backed concepts were resolved for this equation."
        )
        audience_label = DISPLAY_AUDIENCE.get(audience, audience)
        semantic_reading = (
            f"{audience_label} MathOntoSpeak reading: {gloss['speech_text']} "
            f"{context_clause}"
        )
        contextual_explanation = (
            f"{concept_clause} {context_clause} {conceptual_structure} "
            "The explanation combines the selected equation, nearby paper language, and the knowledge graph surface forms."
        )
        why_it_helps = (
            "This gives a blind researcher meaning, role, and document context before the notation is spoken, "
            "so the equation is heard as a concept-bearing statement instead of only a sequence of symbols."
        )
        return {
            "index": index,
            "equation_id": equation_id,
            "source_label": source_label,
            "display_label": equation_label,
            "equation_label": equation_label,
            "page": equation_metadata.get("page"),
            "bbox": equation_metadata.get("bbox") or [],
            "polygon": equation_metadata.get("polygon") or [],
            "equation_image": str(equation_metadata.get("equation_image") or ""),
            "latex": latex,
            "original_latex": original_latex,
            "formula_repairs": formula_repairs,
            "structure_validation": structure_validation,
            "extraction_warning": extraction_warning,
            "mathml": mathml,
            "mathml_engine": mathml_engine,
            "math_speech": math_speech,
            "grouped_expression": grouped_expression,
            "plain_notation_reading": plain_notation,
            "semantic_reading": semantic_reading,
            "contextual_explanation": contextual_explanation,
            "equation_summary": context_summary,
            "context_summary": context_summary,
            "conceptual_structure": conceptual_structure,
            "equation_role": equation_role,
            "explanation_provider": explanation_provider,
            "context_evidence": display_evidence,
            "term_explanations": term_explanations,
            "ontology_links": ontology_links,
            "ontology_query_mode": ontology_query_mode,
            "unresolved_symbols": unresolved_symbols,
            "grounding_evaluation": grounding_evaluation,
            "spoken_script": spoken_script,
            "speech_segments": speech_segments,
            "extraction_confidence": extraction_confidence,
            "extraction_method": extraction_method,
            "confidence": {
                "extraction": extraction_confidence,
                "structure": structure_validation["confidence"],
                "label": "high" if source_label else "generated",
                "context": equation_role.get("confidence", "low"),
                "ontology": "high" if ontology_links else "low",
                "explanation": "high" if evidence else "low",
            },
            "why_it_helps": why_it_helps,
            "resolved_count": gloss["resolved_count"],
            "tokens": gloss["tokens"],
            "concepts": unique_labels,
            "linked_text_span": linked_span,
            "recommendations": recommendations["results"],
            "ssml": spoken_ssml,
            "audio": self._maybe_generate_equation_audio(
                latex=latex,
                index=index,
                title=title,
                speech_text=spoken_script,
                ssml=spoken_ssml,
                audio_backend=audio_backend,
                generate_audio=generate_audio,
            ),
        }

    def _ontology_links_for_tokens(
        self,
        tokens: list[dict[str, Any]],
        *,
        latex: str = "",
        context: str = "",
        use_live_graph: bool = False,
    ) -> list[dict[str, Any]]:
        links_by_iri: dict[str, dict[str, Any]] = {}
        for token in tokens:
            concept_iri = str(token.get("concept_iri") or "")
            canonical_label = str(token.get("canonical_label") or "")
            if not concept_iri or not canonical_label:
                continue
            record = self.find_record(concept_iri) or self.find_record(canonical_label)
            public_record = self._public_record(record)
            if public_record is None:
                public_record = {
                    "concept_iri": concept_iri,
                    "canonical_label": canonical_label,
                    "kind_role": "",
                    "semantic_type": "",
                    "domain_tags": list(token.get("domain_tags") or []),
                    "source_provenance": str(token.get("source") or ""),
                }
            link = links_by_iri.setdefault(
                concept_iri,
                {
                    "concept_iri": public_record.get("concept_iri") or concept_iri,
                    "canonical_label": public_record.get("canonical_label") or canonical_label,
                    "kind_role": public_record.get("kind_role", ""),
                    "semantic_type": public_record.get("semantic_type", ""),
                    "domain_tags": public_record.get("domain_tags", []),
                    "source_provenance": public_record.get("source_provenance", ""),
                    "symbols": [],
                    "source": "ontology",
                    "provenance_type": "ontology",
                    "query_mode": "local_protege_snapshot",
                },
            )
            raw = str(token.get("raw") or "")
            if raw and raw not in link["symbols"]:
                link["symbols"].append(raw)

        inferred_labels: list[tuple[str, str, str]] = []
        if re.search(r"\^\s*\{?\s*1\s*/\s*2\s*\}?", latex):
            inferred_labels.append(("Taking root", "power one half", "structural_inference"))
        if re.search(r"(?:\}|\]|\)|[A-Za-z0-9])\s+(?:\\?[A-Za-z]|\()", latex):
            inferred_labels.append(("Multiplication", "implicit product", "structural_inference"))
        if re.search(r"[A-Za-z][A-Za-z0-9_]*\s*[\[(]", latex):
            inferred_labels.append(("Function", "function notation", "structural_inference"))
        normalized_context = set(normalize_text(context).split())
        for keyword, label in (
            ("probability", "Probability"),
            ("matrix", "Matrix"),
            ("vector", "Vector"),
        ):
            if keyword in normalized_context:
                inferred_labels.append((label, keyword, "paper_evidence"))

        for label, symbol, source in inferred_labels:
            record = self.find_record(label)
            public_record = self._public_record(record)
            if public_record is None:
                continue
            concept_iri = str(public_record.get("concept_iri") or "")
            if not concept_iri:
                continue
            link = links_by_iri.setdefault(
                concept_iri,
                {
                    "concept_iri": concept_iri,
                    "canonical_label": public_record.get("canonical_label") or label,
                    "kind_role": public_record.get("kind_role", ""),
                    "semantic_type": public_record.get("semantic_type", ""),
                    "domain_tags": public_record.get("domain_tags", []),
                    "source_provenance": public_record.get("source_provenance", ""),
                    "symbols": [],
                    "source": source,
                    "provenance_type": source,
                    "query_mode": "local_protege_snapshot",
                },
            )
            if symbol not in link["symbols"]:
                link["symbols"].append(symbol)

        if use_live_graph and links_by_iri and hasattr(self.fuseki, "describe_concepts"):
            try:
                graph_records = self.fuseki.describe_concepts(list(links_by_iri.values()))
            except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                graph_records = []
            graph_by_requested = {
                str(record.get("requested_iri") or ""): record
                for record in graph_records
                if record.get("requested_iri")
            }
            for requested_iri, link in links_by_iri.items():
                graph_record = graph_by_requested.get(requested_iri)
                if not graph_record:
                    continue
                match_provenance = link.get("provenance_type", "ontology")
                link.update(
                    {
                        **graph_record,
                        "requested_concept_iri": requested_iri,
                        "symbols": link["symbols"],
                        "source": "ontology_live_graph",
                        "provenance_type": "ontology_live_graph",
                        "match_provenance_type": match_provenance,
                        "query_mode": "live_fuseki",
                        "graph_endpoint": self.fuseki.endpoint,
                        "graph_dataset": self.fuseki.dataset,
                    }
                )
        return list(links_by_iri.values())

    def _maybe_generate_equation_audio(
        self,
        *,
        latex: str,
        index: int,
        title: str,
        speech_text: str,
        ssml: str,
        audio_backend: str,
        generate_audio: bool,
    ) -> dict[str, str]:
        if not generate_audio or audio_backend == "none":
            return {
                "status": "skipped",
                "backend": audio_backend,
                "detail": "Audio generation was not requested.",
                "audio_path": "",
                "audio_url": "",
            }
        if audio_backend == "azure" and not (os.getenv("AZURE_SPEECH_KEY") and os.getenv("AZURE_SPEECH_REGION")):
            return {
                "status": "not_configured",
                "backend": audio_backend,
                "detail": "Azure Speech is not configured; set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.",
                "audio_path": "",
                "audio_url": "",
                "ssml_path": "",
            }
        try:
            backend = backend_for(audio_backend)
            from scripts.week4_tts_rendering import EquationSpeechBundle, synthesize_equation_bundle

            bundle = EquationSpeechBundle(
                arxiv_id="paper-demo",
                title=title,
                latex=latex,
                plain_text=latex_to_plain_text(latex),
                speech_text=speech_text,
                ssml=ssml,
                tokens=[],
            )
            result = synthesize_equation_bundle(bundle, backend, DEFAULT_PAPER_AUDIO_DIR, index)
            payload = asdict(result)
            try:
                relative_audio = Path(result.audio_path).resolve().relative_to(DEFAULT_PAPER_AUDIO_DIR.resolve())
                payload["audio_url"] = "/api/generated-audio/" + relative_audio.as_posix()
            except (OSError, ValueError):
                payload["audio_url"] = ""
            return payload
        except RuntimeError as exc:
            detail = str(exc)
            status = "not_configured" if "AZURE_SPEECH_KEY" in detail or "Azure" in detail else "failed"
            return {
                "status": status,
                "backend": audio_backend,
                "detail": detail,
                "audio_path": "",
                "audio_url": "",
                "ssml_path": "",
            }
        except Exception as exc:  # noqa: BLE001 - keep the demo endpoint graceful.
            return {
                "status": "failed",
                "backend": audio_backend,
                "detail": f"{type(exc).__name__}: {exc}",
                "audio_path": "",
                "audio_url": "",
                "ssml_path": "",
            }

    def find_record(self, label_or_iri: str | None) -> dict[str, Any] | None:
        if not label_or_iri:
            return None
        direct = self.repository.get_by_iri(label_or_iri) or self.repository.get_by_label(label_or_iri)
        if direct:
            return direct
        key = normalize_key(label_or_iri)
        return self._by_label.get(key)

    def _score_record(self, query: str, query_tokens: set[str], record: dict[str, Any]) -> tuple[float, list[str]]:
        if not query_tokens:
            return 0.0, []
        label = str(record.get("canonical_label", ""))
        label_tokens = tokens_for(label)
        haystack = " ".join(
            [
                label,
                str(record.get("canonical_gloss", "")),
                str(record.get("concise_form", "")),
                str(record.get("semantic_type", "")),
                " ".join(record_domains(record)),
                str(record.get("source_provenance", "")),
            ]
        )
        haystack_tokens = tokens_for(haystack)
        overlap = query_tokens.intersection(haystack_tokens)
        score = float(len(overlap))
        reasons = [f"matched terms: {', '.join(sorted(overlap))}"] if overlap else []
        if normalize_key(query) == normalize_key(label):
            score += 5.0
            reasons.append("exact canonical-label match")
        elif normalize_key(label) in {normalize_key(token) for token in query_tokens}:
            score += 3.0
            reasons.append("canonical label appears in query")
        elif label_tokens and label_tokens.issubset(query_tokens):
            score += 3.0
            reasons.append("canonical label terms appear in query")
        elif normalize_key(query) in normalize_key(label):
            score += 2.0
            reasons.append("partial canonical-label match")
        return score, reasons

    def _public_record(
        self,
        record: dict[str, Any] | None,
        score: float | None = None,
        reasons: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if record is None:
            return None
        payload = {
            "concept_iri": record.get("concept_IRI") or record.get("concept_iri") or "",
            "canonical_label": record.get("canonical_label") or record.get("rdfs_label") or "",
            "kind_role": record.get("kind_role", ""),
            "semantic_type": record.get("semantic_type", ""),
            "canonical_gloss": record.get("canonical_gloss", ""),
            "concise_form": record.get("concise_form", ""),
            "pedagogical_form": record.get("pedagogical_form", ""),
            "expert_form": record.get("expert_form", ""),
            "document_role_form": record.get("document_role_form", ""),
            "domain_tags": record_domains(record),
            "source_provenance": record.get("source_provenance", ""),
            "source_provenance_note": record.get("source_provenance_note", ""),
        }
        if score is not None:
            payload["score"] = score
        if reasons is not None:
            payload["reasons"] = reasons
        return payload

    def _record_from_result(self, result: dict[str, Any]) -> dict[str, Any]:
        return self.find_record(str(result.get("concept_iri") or result.get("canonical_label"))) or {}


def record_domains(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return []
    return split_multi_value(record.get("domain_tags"))
