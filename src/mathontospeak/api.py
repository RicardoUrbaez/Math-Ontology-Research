from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .concept_lookup import lookup_symbols
from .gloss_record import GlossRecord, load_gloss_records
from .latex_parser import parse_latex_symbols
from .ssml_builder import build_ssml
from .surface_forms import generate_surface_forms
from .tts_backends import get_tts_backend


ROOT = Path(__file__).resolve().parents[2]
APP_VERSION = "0.1.0-week4-api"
DEFAULT_GLOSS_PATH = ROOT / "data" / "gloss_dictionary" / "gloss_records_50.json"
DEFAULT_SPARQL_ENDPOINT = "http://127.0.0.1:3030/mathkg/query"
OUTPUT_ROOT = ROOT / "outputs"
SURFACE_FORM_TO_FIELD = {
    "concise": "concise_form",
    "pedagogical": "pedagogical_form",
    "expert": "expert_form",
    "document_role": "document_role_form",
}


class ConceptRecord(BaseModel):
    concept_iri: str
    local_name: str
    canonical_label: str
    canonical_gloss: str
    concise_form: str = ""
    pedagogical_form: str = ""
    expert_form: str = ""
    document_role_form: str = ""
    concept_type: str = ""
    kind_role_classification: str = ""
    domain_tags: list[str] = Field(default_factory=list)
    source_provenance: str = ""
    source_iri: str = ""
    mapping_quality: str = ""
    accessibility_note: str = ""
    examples: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str
    backend_readiness: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    limit: int
    result_count: int
    results: list[dict[str, Any]]


class LatexGlossRequest(BaseModel):
    latex: str = Field(..., min_length=1)
    context: str = ""
    surface_form: Literal["concise", "pedagogical", "expert", "document_role"] = "pedagogical"
    backend: Literal["mock", "gtts", "azure"] = "mock"


class LatexGlossResponse(BaseModel):
    input_latex: str
    parsed_symbols: list[dict[str, Any]]
    concept_candidates: list[dict[str, Any]]
    selected_glosses: list[dict[str, Any]]
    surface_forms: dict[str, dict[str, str]]
    selected_surface_form: str
    ssml: str
    provenance: list[dict[str, str]]
    accessibility_notes: list[str]
    output_file_paths: dict[str, str | None]
    backend_status: dict[str, Any]


app = FastAPI(
    title="MathOntoSpeak Week 4 API",
    description=(
        "Local FastAPI surface for the Week 4 math accessibility glossary, "
        "LaTeX parser, concept lookup, SSML, and mock/gTTS/Azure-ready TTS backends."
    ),
    version=APP_VERSION,
)


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.sub(r"[^a-z0-9]+", " ", value.lower()).split()
        if len(token) > 1
    }


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return cleaned[:80] or "latex_gloss"


def _record_to_model(record: GlossRecord) -> ConceptRecord:
    return ConceptRecord(**record.to_dict())


def _record_public(record: GlossRecord, score: float | None = None, reasons: list[str] | None = None) -> dict[str, Any]:
    payload = record.to_dict()
    if score is not None:
        payload["score"] = round(score, 3)
    if reasons is not None:
        payload["reasons"] = reasons
    return payload


@lru_cache(maxsize=1)
def get_records() -> tuple[GlossRecord, ...]:
    return tuple(load_gloss_records(DEFAULT_GLOSS_PATH))


def _records_by_local_name() -> dict[str, GlossRecord]:
    return {_normalize_key(record.local_name): record for record in get_records()}


def _records_by_label() -> dict[str, GlossRecord]:
    return {_normalize_key(record.canonical_label): record for record in get_records()}


def _records_by_iri() -> dict[str, GlossRecord]:
    return {record.concept_iri: record for record in get_records()}


def _find_record(value: str | None) -> GlossRecord | None:
    if not value:
        return None
    return (
        _records_by_local_name().get(_normalize_key(value))
        or _records_by_label().get(_normalize_key(value))
        or _records_by_iri().get(value)
    )


def _score_record(query: str, record: GlossRecord) -> tuple[float, list[str]]:
    query_key = _normalize_key(query)
    query_tokens = _tokenize(query)
    if not query_key and not query_tokens:
        return 0.0, []

    fields = {
        "canonical label": record.canonical_label,
        "local name": record.local_name,
        "gloss/definition": record.canonical_gloss,
        "surface forms": " ".join(
            [
                record.concise_form,
                record.pedagogical_form,
                record.expert_form,
                record.document_role_form,
            ]
        ),
        "source provenance": f"{record.source_provenance} {record.source_iri}",
        "domain tags": " ".join(record.domain_tags),
        "accessibility notes": record.accessibility_note,
        "mapping metadata": f"{record.concept_type} {record.kind_role_classification} {record.mapping_quality}",
    }

    score = 0.0
    reasons: list[str] = []
    label_key = _normalize_key(record.canonical_label)
    local_key = _normalize_key(record.local_name)
    if query_key in {label_key, local_key}:
        score += 8.0
        reasons.append("exact concept-name match")
    elif query_key and (query_key in label_key or query_key in local_key):
        score += 4.0
        reasons.append("partial concept-name match")

    for field_name, field_text in fields.items():
        field_tokens = _tokenize(field_text)
        overlap = query_tokens.intersection(field_tokens)
        if not overlap:
            continue
        weight = 2.5 if field_name in {"canonical label", "local name"} else 1.0
        if field_name in {"gloss/definition", "domain tags", "accessibility notes"}:
            weight = 1.5
        score += len(overlap) * weight
        reasons.append(f"{field_name} matched: {', '.join(sorted(overlap))}")

    return score, reasons


def _semantic_search_records(query: str, limit: int) -> list[dict[str, Any]]:
    ranked: list[tuple[float, GlossRecord, list[str]]] = []
    for record in get_records():
        score, reasons = _score_record(query, record)
        if score > 0:
            ranked.append((score, record, reasons))
    ranked.sort(key=lambda item: (-item[0], item[1].canonical_label.lower()))
    return [_record_public(record, score=score, reasons=reasons) for score, record, reasons in ranked[:limit]]


SYMBOL_AMBIGUITIES: dict[str, list[dict[str, Any]]] = {
    "T": [
        {
            "meaning": "variable or parameter",
            "domain": "general-mathematics",
            "concept_label": "Variable",
            "confidence": 0.62,
            "ambiguity_note": "Single uppercase T is often a context-dependent variable.",
        },
        {
            "meaning": "transpose marker",
            "domain": "linear-algebra",
            "concept_label": "Matrix",
            "confidence": 0.58,
            "ambiguity_note": "A superscript T commonly marks matrix or vector transpose.",
        },
        {
            "meaning": "temperature",
            "domain": "physics",
            "concept_label": "",
            "confidence": 0.4,
            "ambiguity_note": "Physics and thermodynamics texts often use T for temperature.",
        },
        {
            "meaning": "period",
            "domain": "dynamical-systems",
            "concept_label": "",
            "confidence": 0.36,
            "ambiguity_note": "Periodic functions and signals may use T for the period.",
        },
        {
            "meaning": "tesla unit",
            "domain": "physics",
            "concept_label": "",
            "confidence": 0.32,
            "ambiguity_note": "Capital T can denote the SI unit tesla in electromagnetic contexts.",
        },
        {
            "meaning": "linear transformation",
            "domain": "linear-algebra",
            "concept_label": "Transformation",
            "confidence": 0.52,
            "ambiguity_note": "Linear algebra often uses T as a named transformation.",
        },
    ],
    "P": [
        {
            "meaning": "probability",
            "domain": "statistics",
            "concept_label": "Probability",
            "confidence": 0.66,
            "ambiguity_note": "P often denotes probability when used as P(A) or in statistics prose.",
        },
        {
            "meaning": "point, polynomial, or variable",
            "domain": "general-mathematics",
            "concept_label": "Variable",
            "confidence": 0.46,
            "ambiguity_note": "P remains ambiguous without context.",
        },
    ],
    "E": [
        {
            "meaning": "expectation",
            "domain": "statistics",
            "concept_label": "Mean",
            "confidence": 0.66,
            "ambiguity_note": "E[X] usually denotes expected value or mean.",
        },
        {
            "meaning": "event, set, or variable",
            "domain": "general-mathematics",
            "concept_label": "Variable",
            "confidence": 0.44,
            "ambiguity_note": "E can also be a named event, set, or identifier.",
        },
    ],
}


def _symbol_discovery(symbol: str, domain: str | None = None) -> dict[str, Any]:
    records_by_label = _records_by_label()
    normalized_domain = _normalize_key(domain or "")
    seeded = SYMBOL_AMBIGUITIES.get(symbol, [])
    meanings = []
    for item in seeded:
        if normalized_domain and normalized_domain not in _normalize_key(str(item["domain"])):
            continue
        concept_label = str(item.get("concept_label") or "")
        record = records_by_label.get(_normalize_key(concept_label)) if concept_label else None
        meanings.append(
            {
                **item,
                "concept_iri": record.concept_iri if record else None,
                "source": "curated API ambiguity table plus local concept lookup",
            }
        )

    if not meanings:
        parsed = parse_latex_symbols(symbol)
        resolved = lookup_symbols(parsed, records=list(get_records()), context=domain or symbol)
        for token in resolved:
            for candidate in token.get("candidates", []):
                meanings.append(
                    {
                        "meaning": candidate.get("concept_label"),
                        "domain": domain or "context-dependent",
                        "concept_label": candidate.get("concept_label"),
                        "concept_iri": candidate.get("concept_iri"),
                        "confidence": candidate.get("confidence", 0.0),
                        "ambiguity_note": candidate.get("ambiguity_notes") or "Derived from local LaTeX symbol lookup.",
                        "source": "local parser and concept lookup",
                    }
                )

    return {
        "symbol": symbol,
        "domain_filter": domain,
        "meanings": meanings,
        "ambiguity_notes": [
            "Symbol meanings are context-sensitive; use domain, surrounding LaTeX, and prose context before selecting a gloss.",
            "Entries without concept_iri are retained as cross-disciplinary hints outside the current 50-concept glossary.",
        ],
    }


def _flatten_concept_candidates(resolved_symbols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for symbol in resolved_symbols:
        for candidate in symbol.get("candidates", []):
            key = (str(symbol.get("raw")), str(candidate.get("concept_iri")))
            if key in seen:
                continue
            seen.add(key)
            flattened.append(
                {
                    "symbol": symbol.get("raw"),
                    "normalized_symbol": symbol.get("normalized"),
                    **candidate,
                }
            )
    flattened.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
    return flattened


def _backend_readiness() -> dict[str, Any]:
    try:
        get_records()
        glossary = {
            "status": "ready",
            "path": str(DEFAULT_GLOSS_PATH),
            "record_count": len(get_records()),
        }
    except Exception as exc:
        glossary = {"status": "error", "path": str(DEFAULT_GLOSS_PATH), "detail": str(exc)}

    try:
        import gtts  # noqa: F401

        gtts_status = "package_available"
    except Exception as exc:
        gtts_status = f"package_unavailable: {exc.__class__.__name__}"

    azure_configured = bool(os.getenv("AZURE_SPEECH_KEY") and os.getenv("AZURE_SPEECH_REGION"))
    return {
        "gloss_dictionary": glossary,
        "mock_tts": {"status": "ready", "detail": "writes local transcript files; default for reproducible tests"},
        "gtts": {"status": gtts_status, "detail": "requires package plus network access at synthesis time"},
        "azure": {
            "status": "configured" if azure_configured else "not_configured",
            "detail": "set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION to use Azure synthesis",
        },
        "fuseki": _fuseki_status(),
    }


def _fuseki_status() -> dict[str, Any]:
    endpoint = os.getenv("MATHKG_SPARQL_ENDPOINT", DEFAULT_SPARQL_ENDPOINT)
    request_body = urllib.parse.urlencode({"query": "ASK { ?s ?p ?o }"}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=request_body,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        ready = bool(payload.get("boolean"))
        detail = "SPARQL ASK query succeeded" if ready else "Fuseki answered, but no triples were found"
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        ready = False
        detail = f"Fuseki not confirmed from API health check: {exc.__class__.__name__}: {exc}"
    return {
        "status": "ready" if ready else "not_running_or_empty",
        "endpoint": endpoint,
        "dataset": urllib.parse.urlparse(endpoint).path.strip("/").split("/")[0],
        "detail": detail,
    }


def _write_accessibility_outputs(payload: dict[str, Any], ssml: str, speech_text: str, backend: str) -> dict[str, Any]:
    digest = hashlib.sha1(
        f"{payload['input_latex']}|{payload['selected_surface_form']}|{backend}".encode("utf-8")
    ).hexdigest()[:10]
    stem = _safe_stem(f"api_{digest}")
    json_dir = OUTPUT_ROOT / "json_glosses"
    ssml_dir = OUTPUT_ROOT / "ssml"
    audio_dir = OUTPUT_ROOT / "audio"
    for directory in (json_dir, ssml_dir, audio_dir):
        directory.mkdir(parents=True, exist_ok=True)

    ssml_path = ssml_dir / f"{stem}.ssml"
    ssml_path.write_text(ssml, encoding="utf-8")
    synthesis = get_tts_backend(backend).synthesize(speech_text, ssml, audio_dir / stem)

    json_path = json_dir / f"{stem}.json"
    output_paths = {
        "json_gloss_path": str(json_path),
        "ssml_path": str(ssml_path),
        "audio_path": synthesis.get("audio_path"),
    }
    payload["output_file_paths"] = output_paths
    payload["backend_status"] = synthesis
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_paths


def _build_latex_gloss_response(request: LatexGlossRequest) -> dict[str, Any]:
    records = list(get_records())
    records_by_iri = _records_by_iri()
    parsed_symbols = parse_latex_symbols(request.latex)
    lookup_context = f"{request.context} {request.latex}".strip()
    resolved_symbols = lookup_symbols(parsed_symbols, records=records, context=lookup_context)
    concept_candidates = _flatten_concept_candidates(resolved_symbols)
    selected_surface_field = SURFACE_FORM_TO_FIELD[request.surface_form]

    selected_glosses: list[dict[str, Any]] = []
    surface_forms_by_iri: dict[str, dict[str, str]] = {}
    provenance: list[dict[str, str]] = []
    accessibility_notes: list[str] = []
    selected_phrases: list[str] = []
    seen_iris: set[str] = set()

    for symbol in resolved_symbols:
        candidates = symbol.get("candidates") or []
        if not candidates:
            continue
        candidate = candidates[0]
        iri = str(candidate.get("concept_iri") or "")
        if not iri or iri in seen_iris:
            continue
        record = records_by_iri.get(iri)
        if not record:
            continue
        seen_iris.add(iri)
        forms = generate_surface_forms(record)
        selected_text = forms[selected_surface_field]
        selected_phrases.append(selected_text)
        surface_forms_by_iri[iri] = {
            "concise": forms["concise_form"],
            "pedagogical": forms["pedagogical_form"],
            "expert": forms["expert_form"],
            "document_role": forms["document_role_form"],
        }
        selected_glosses.append(
            {
                "symbol": symbol.get("raw"),
                "candidate": candidate,
                "concept": _record_public(record),
                "selected_text": selected_text,
            }
        )
        provenance.append(
            {
                "concept_iri": record.concept_iri,
                "source_provenance": record.source_provenance,
                "source_iri": record.source_iri,
                "mapping_quality": record.mapping_quality,
            }
        )
        if record.accessibility_note:
            accessibility_notes.append(record.accessibility_note)

    gloss_text = " ".join(selected_phrases) or "No ontology-backed concept gloss was found for this expression."
    speech_text = f"LaTeX expression: {request.latex}. {gloss_text}"
    ssml_payload = build_ssml(speech_text)
    payload: dict[str, Any] = {
        "input_latex": request.latex,
        "parsed_symbols": resolved_symbols,
        "concept_candidates": concept_candidates,
        "selected_glosses": selected_glosses,
        "surface_forms": surface_forms_by_iri,
        "selected_surface_form": request.surface_form,
        "ssml": ssml_payload["ssml"],
        "provenance": provenance,
        "accessibility_notes": accessibility_notes,
        "output_file_paths": {},
        "backend_status": {},
    }
    _write_accessibility_outputs(payload, ssml_payload["ssml"], ssml_payload["plain_text"], request.backend)
    return payload


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "backend_readiness": _backend_readiness(),
    }


@app.get("/concepts", response_model=list[ConceptRecord])
def concepts() -> list[ConceptRecord]:
    return [_record_to_model(record) for record in get_records()]


@app.get("/concepts/{local_name}", response_model=ConceptRecord)
def concept_by_local_name(local_name: str) -> ConceptRecord:
    record = _records_by_local_name().get(_normalize_key(local_name))
    if not record:
        raise HTTPException(status_code=404, detail=f"Concept not found: {local_name}")
    return _record_to_model(record)


@app.get("/semantic-search", response_model=SearchResponse)
def semantic_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    results = _semantic_search_records(q, limit)
    return {"query": q, "limit": limit, "result_count": len(results), "results": results}


@app.get("/cross-disciplinary-discovery")
def cross_disciplinary_discovery(
    symbol: str = Query(..., min_length=1),
    domain: str | None = Query(default=None),
) -> dict[str, Any]:
    return _symbol_discovery(symbol=symbol, domain=domain)


@app.get("/concept-recommender")
def concept_recommender(
    latex: str = Query(..., min_length=1),
    context: str | None = Query(default=None),
) -> dict[str, Any]:
    parsed_symbols = parse_latex_symbols(latex)
    resolved_symbols = lookup_symbols(parsed_symbols, records=list(get_records()), context=f"{context or ''} {latex}".strip())
    candidates = _flatten_concept_candidates(resolved_symbols)
    return {
        "latex": latex,
        "context": context,
        "parsed_symbols": resolved_symbols,
        "recommendations": candidates,
        "limitations": "Confidence values are rule-based MVP scores from the local parser and 50-record glossary.",
    }


@app.post("/accessibility/latex-to-json-gloss", response_model=LatexGlossResponse)
def latex_to_json_gloss(request: LatexGlossRequest) -> dict[str, Any]:
    try:
        return _build_latex_gloss_response(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

