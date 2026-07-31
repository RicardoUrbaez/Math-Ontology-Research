from __future__ import annotations

import base64
import binascii
import json
import os
import re
from dataclasses import asdict, dataclass
from io import BytesIO
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

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
DEFAULT_SPARQL_ENDPOINT = "http://localhost:3030/mathkg500/query"
DEFAULT_PAPER_AUDIO_DIR = ROOT / "reports" / "audio" / "paper_demo"
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


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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


def extract_plain_text_equations(text: str, limit: int = 12) -> list[str]:
    pattern = re.compile(
        r"(?P<lhs>[^\W\d_][\w]*(?:\s*[_^]\s*(?:\{[^}]+\}|[\w]+))?"
        r"(?:\s*[\[(][^\])]{1,32}[\])])?)\s*=\s*(?P<rhs>[^.;]{1,260})",
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
        rhs = re.sub(r"\s*\(\d+\)\s*$", "", rhs).strip()
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


def extract_equation_candidates(text: str, limit: int = 12) -> list[dict[str, str]]:
    patterns = [
        r"\$\$(.+?)\$\$",
        r"\\\[(.+?)\\\]",
        r"\\\((.+?)\\\)",
        r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$",
    ]
    equations: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.DOTALL):
            equation = re.sub(r"\s+", " ", match.group(1)).strip()
            if equation and equation not in seen:
                seen.add(equation)
                equations.append(
                    {
                        "latex": equation,
                        "confidence": "high",
                        "method": "latex_delimiter",
                    }
                )
            if len(equations) >= limit:
                return equations
    if equations:
        return equations
    for equation in extract_plain_text_equations(text, limit=limit):
        equations.append(
            {
                "latex": equation,
                "confidence": "medium",
                "method": "plain_text_equation",
            }
        )
    return equations


def extract_latex_equations(text: str, limit: int = 12) -> list[str]:
    return [candidate["latex"] for candidate in extract_equation_candidates(text, limit=limit)]


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
        for page_number, page in enumerate(reader.pages[:20], start=1):
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
            "detail": f"Extracted text from {len(reader.pages)} PDF page(s).",
            "page_count": len(reader.pages),
            "context_chunk_count": len(context_chunks),
        },
    )


def extract_pdf_text_from_base64(pdf_base64: str) -> tuple[str, dict[str, Any]]:
    text, _chunks, status = extract_pdf_context_from_base64(pdf_base64)
    return text, status


def split_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[;,]", str(value)) if part.strip()]


def rank_context_evidence(
    chunks: list[dict[str, Any]],
    *,
    latex: str,
    labels: list[str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    equation_terms = {
        normalize_key(term)
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_]*", latex)
        if len(term) > 1 or term.lower() in {"h", "n", "p", "r", "s", "x", "y"}
    }
    macro_names = {"bar", "hat", "left", "right", "sqrt", "sum", "tilde"}
    lhs_terms = [
        normalize_key(term)
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_]*", latex.split("=", 1)[0])
        if normalize_key(term) not in macro_names
    ]
    lhs_symbol = lhs_terms[0] if lhs_terms else ""
    label_terms = {token for label in labels for token in normalize_text(label).split()}
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for position, chunk in enumerate(chunks):
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
            - length_penalty
        )
        ranked.append((score, -position, chunk))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    evidence: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    seen_normalized: list[str] = []
    for score, _position, chunk in ranked:
        text = str(chunk.get("text") or "")
        if text in seen_text:
            continue
        normalized_candidate = normalize_text(text)
        if any(
            len(normalized_candidate) > 100
            and len(previous) > 100
            and (normalized_candidate in previous or previous in normalized_candidate)
            for previous in seen_normalized
        ):
            continue
        seen_text.add(text)
        seen_normalized.append(normalized_candidate)
        payload = dict(chunk)
        payload["relevance_score"] = round(score, 2)
        evidence.append(payload)
        if len(evidence) >= limit:
            break
    return evidence


def infer_context_summary(equation_label: str, context: str, evidence: list[dict[str, Any]]) -> str:
    evidence_text = " ".join(str(item.get("text") or "") for item in evidence)
    normalized = normalize_text(evidence_text or context)
    terms = set(normalized.split())
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
) -> list[dict[str, Any]]:
    terms: list[dict[str, Any]] = []
    covered: set[str] = set()

    token_by_symbol: dict[str, dict[str, Any]] = {}
    for token in tokens:
        raw = str(token.get("raw") or "")
        key = normalize_key(raw)
        if key and key not in token_by_symbol:
            token_by_symbol[key] = token

    for definition in context_symbol_definitions(context, latex):
        symbol = definition["symbol"]
        key = normalize_key(symbol)
        matching_token = token_by_symbol.get(key)
        if matching_token is None and key.startswith("n"):
            matching_token = token_by_symbol.get("n")
        terms.append(
            {
                "symbol": symbol,
                "spoken": str(matching_token.get("spoken") if matching_token else symbol),
                "meaning": definition["meaning"],
                "source": "paper_context",
                "ontology_concept": str(matching_token.get("canonical_label") if matching_token else ""),
                "confidence": "high",
            }
        )
        covered.add(key)

    operator_meanings = {
        "=": "states that the expression on the left is equal to the expression on the right",
        "+": "adds another quantity or component to the expression",
        "-": "subtracts one quantity or component from another",
        r"\sum": "combines a sequence of terms through summation",
        r"\sqrt": "takes a square root, often used here as part of a scaling factor",
    }
    operator_spoken = {
        "=": "equals",
        "+": "plus",
        "-": "minus",
        r"\sum": "summation",
        r"\sqrt": "square root",
    }
    seen_raw: set[str] = set()
    for token in tokens:
        raw = str(token.get("raw") or "").strip()
        if not raw or raw in seen_raw:
            continue
        seen_raw.add(raw)
        key = normalize_key(raw)
        if key and key in covered:
            continue

        canonical_label = str(token.get("canonical_label") or "")
        concept_iri = str(token.get("concept_iri") or "")
        if raw in operator_meanings:
            meaning = operator_meanings[raw]
            source = "ontology" if concept_iri else "notation"
            confidence = "medium"
        elif not concept_iri:
            meaning = (
                f"The available paper context and ontology do not define {raw}; "
                "it should be treated as unresolved notation."
            )
            source = "unresolved"
            confidence = "low"
        elif str(token.get("token_type") or "") == "identifier":
            meaning = (
                f"{raw} is recognized as a variable, but its domain-specific meaning "
                "is not stated in the available context"
            )
            source = "ontology"
            confidence = "medium"
        else:
            meaning = _definition_from_gloss(
                str(token.get("gloss") or ""),
                f"{raw} is linked to the ontology concept {canonical_label}",
            )
            source = "ontology"
            confidence = "medium"

        terms.append(
            {
                "symbol": raw,
                "spoken": operator_spoken.get(raw, str(token.get("spoken") or raw)),
                "meaning": meaning,
                "source": source,
                "ontology_concept": canonical_label,
                "confidence": confidence,
            }
        )
        if len(terms) >= 16:
            break
    return terms


def build_spoken_script(
    *,
    equation_label: str,
    context_summary: str,
    term_explanations: list[dict[str, Any]],
    plain_notation: str,
) -> str:
    script_parts = [f"Next I am going to read {equation_label}.", context_summary]
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
    def __init__(self, endpoint: str | None = None, timeout_seconds: float = 2.5) -> None:
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


class MathKGService:
    def __init__(self, gloss_path: Path | None = None, fuseki_client: FusekiClient | None = None) -> None:
        self.gloss_path = gloss_path or DEFAULT_GLOSS_PATH
        self.records = load_gloss_records(self.gloss_path)
        self.repository = GlossRepository(self.records)
        self.lookup = SymbolConceptLookup(self.repository)
        self.fuseki = fuseki_client or FusekiClient()
        self._by_label = {normalize_key(str(record.get("canonical_label", ""))): record for record in self.records}

    def health(self) -> dict[str, Any]:
        status = self.fuseki.status()
        return {
            "api": "ok",
            "gloss_records": len(self.records),
            "gloss_path": str(self.gloss_path),
            "fuseki": status.__dict__,
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
    ) -> dict[str, Any]:
        pdf_text, pdf_chunks, pdf_status = extract_pdf_context_from_base64(pdf_base64)
        if pdf_filename:
            pdf_status["filename"] = pdf_filename

        context_parts = [part for part in (abstract_or_context, pdf_text) if part]
        source_text = "\n\n".join(context_parts).strip()
        context_chunks = context_chunks_from_text(
            abstract_or_context,
            source="provided_context",
        )
        context_chunks.extend(pdf_chunks)
        supplied_equations = [equation.strip() for equation in equations or [] if equation and equation.strip()]
        extracted_candidates = extract_equation_candidates(source_text)
        selected_candidates = (
            [
                {
                    "latex": equation,
                    "confidence": "user_supplied",
                    "method": "manual_equation",
                }
                for equation in supplied_equations
            ]
            or extracted_candidates
        )

        analyses = [
            self._analyze_equation(
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
            )
            for index, candidate in enumerate(selected_candidates, start=1)
        ]

        return {
            "title": title or "Untitled paper",
            "audience": audience,
            "audio_backend": audio_backend,
            "source_text_length": len(source_text),
            "context_chunk_count": len(context_chunks),
            "extracted_equation_count": len(extracted_candidates),
            "pdf": pdf_status,
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
    ) -> dict[str, Any]:
        gloss = self.latex_accessibility_gloss(latex, audience=audience, arxiv_id="paper-demo", title=title)
        labels = [token["canonical_label"] for token in gloss["tokens"] if token.get("canonical_label")]
        unique_labels = list(dict.fromkeys(labels))
        evidence = rank_context_evidence(context_chunks, latex=latex, labels=unique_labels)
        linked_span = (
            str(evidence[0].get("text") or "")
            if evidence
            else sentence_for_context(context, latex, unique_labels)
        )
        recommendations = self.recommend_concepts(context=context, latex=latex, seed_concepts=unique_labels, limit=5)
        equation_label = f"Equation {index}"
        context_summary = infer_context_summary(equation_label, context, evidence)
        evidence_context = " ".join(str(item.get("text") or "") for item in evidence)
        term_explanations = build_term_explanations(
            latex=latex,
            context=evidence_context or context,
            tokens=gloss["tokens"],
        )
        ontology_links = self._ontology_links_for_tokens(
            gloss["tokens"],
            latex=latex,
            context=evidence_context,
        )
        plain_notation = gloss["plain_text"] or latex_to_plain_text(latex)
        spoken_script = build_spoken_script(
            equation_label=equation_label,
            context_summary=context_summary,
            term_explanations=term_explanations,
            plain_notation=plain_notation,
        )
        spoken_ssml = assemble_ssml(spoken_script)
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
            f"{concept_clause} {context_clause} "
            "The explanation combines the selected equation, nearby paper language, and the knowledge graph surface forms."
        )
        why_it_helps = (
            "This gives a blind researcher meaning, role, and document context before the notation is spoken, "
            "so the equation is heard as a concept-bearing statement instead of only a sequence of symbols."
        )
        return {
            "index": index,
            "equation_label": equation_label,
            "latex": latex,
            "plain_notation_reading": plain_notation,
            "semantic_reading": semantic_reading,
            "contextual_explanation": contextual_explanation,
            "equation_summary": context_summary,
            "context_summary": context_summary,
            "context_evidence": evidence,
            "term_explanations": term_explanations,
            "ontology_links": ontology_links,
            "spoken_script": spoken_script,
            "extraction_confidence": extraction_confidence,
            "extraction_method": extraction_method,
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
                    "source": "knowledge_graph",
                },
            )
            raw = str(token.get("raw") or "")
            if raw and raw not in link["symbols"]:
                link["symbols"].append(raw)

        inferred_labels: list[tuple[str, str, str]] = []
        if re.search(r"(?:\}|\]|\)|[A-Za-z0-9])\s+(?:\\?[A-Za-z]|\()", latex):
            inferred_labels.append(("Multiplication", "implicit product", "equation_structure"))
        if re.search(r"[A-Za-z][A-Za-z0-9_]*\s*[\[(]", latex):
            inferred_labels.append(("Function", "function notation", "equation_structure"))
        normalized_context = set(normalize_text(context).split())
        for keyword, label in (
            ("probability", "Probability"),
            ("matrix", "Matrix"),
            ("vector", "Vector"),
        ):
            if keyword in normalized_context:
                inferred_labels.append((label, keyword, "paper_context"))

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
                },
            )
            if symbol not in link["symbols"]:
                link["symbols"].append(symbol)
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
            }
        if audio_backend == "azure" and not (os.getenv("AZURE_SPEECH_KEY") and os.getenv("AZURE_SPEECH_REGION")):
            return {
                "status": "not_configured",
                "backend": audio_backend,
                "detail": "Azure Speech is not configured; set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.",
                "audio_path": "",
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
            return asdict(result)
        except RuntimeError as exc:
            detail = str(exc)
            status = "not_configured" if "AZURE_SPEECH_KEY" in detail or "Azure" in detail else "failed"
            return {
                "status": status,
                "backend": audio_backend,
                "detail": detail,
                "audio_path": "",
                "ssml_path": "",
            }
        except Exception as exc:  # noqa: BLE001 - keep the demo endpoint graceful.
            return {
                "status": "failed",
                "backend": audio_backend,
                "detail": f"{type(exc).__name__}: {exc}",
                "audio_path": "",
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
