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


def extract_latex_equations(text: str, limit: int = 12) -> list[str]:
    patterns = [
        r"\$\$(.+?)\$\$",
        r"\\\[(.+?)\\\]",
        r"\\\((.+?)\\\)",
        r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$",
    ]
    equations: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.DOTALL):
            equation = re.sub(r"\s+", " ", match.group(1)).strip()
            if equation and equation not in seen:
                seen.add(equation)
                equations.append(equation)
            if len(equations) >= limit:
                return equations
    return equations


def extract_pdf_text_from_base64(pdf_base64: str) -> tuple[str, dict[str, str]]:
    if not pdf_base64:
        return "", {"status": "not_provided", "detail": "No PDF payload supplied."}
    try:
        raw = base64.b64decode(pdf_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        return "", {"status": "failed", "detail": f"PDF base64 decode failed: {exc}"}
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw))
        chunks = [(page.extract_text() or "") for page in reader.pages[:20]]
        text = re.sub(r"\s+", " ", "\n".join(chunks)).strip()
    except Exception as exc:  # noqa: BLE001 - returned as user-facing provenance.
        return "", {"status": "failed", "detail": f"PDF extraction failed: {type(exc).__name__}: {exc}"}
    if not text:
        return "", {"status": "empty", "detail": "PDF parsed, but no extractable text was found."}
    return text, {"status": "ok", "detail": f"Extracted text from {len(reader.pages)} PDF page(s)."}


def split_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[;,]", str(value)) if part.strip()]


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
        pdf_text, pdf_status = extract_pdf_text_from_base64(pdf_base64)
        if pdf_filename:
            pdf_status["filename"] = pdf_filename

        context_parts = [part for part in (abstract_or_context, pdf_text) if part]
        source_text = "\n\n".join(context_parts).strip()
        supplied_equations = [equation.strip() for equation in equations or [] if equation and equation.strip()]
        extracted_equations = extract_latex_equations(source_text)
        selected_equations = supplied_equations or extracted_equations

        analyses = [
            self._analyze_equation(
                latex=latex,
                index=index,
                title=title,
                context=source_text,
                audience=audience,
                audio_backend=audio_backend,
                generate_audio=generate_audio,
            )
            for index, latex in enumerate(selected_equations, start=1)
        ]

        return {
            "title": title or "Untitled paper",
            "audience": audience,
            "audio_backend": audio_backend,
            "source_text_length": len(source_text),
            "extracted_equation_count": len(extracted_equations),
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
        audience: str,
        audio_backend: str,
        generate_audio: bool,
    ) -> dict[str, Any]:
        gloss = self.latex_accessibility_gloss(latex, audience=audience, arxiv_id="paper-demo", title=title)
        labels = [token["canonical_label"] for token in gloss["tokens"] if token.get("canonical_label")]
        unique_labels = list(dict.fromkeys(labels))
        linked_span = sentence_for_context(context, latex, unique_labels)
        recommendations = self.recommend_concepts(context=context, latex=latex, seed_concepts=unique_labels, limit=5)
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
            "latex": latex,
            "plain_notation_reading": gloss["plain_text"] or latex_to_plain_text(latex),
            "semantic_reading": semantic_reading,
            "contextual_explanation": contextual_explanation,
            "why_it_helps": why_it_helps,
            "resolved_count": gloss["resolved_count"],
            "tokens": gloss["tokens"],
            "concepts": unique_labels,
            "linked_text_span": linked_span,
            "recommendations": recommendations["results"],
            "ssml": gloss["ssml"],
            "audio": self._maybe_generate_equation_audio(
                latex=latex,
                index=index,
                title=title,
                speech_text=semantic_reading,
                ssml=gloss["ssml"],
                audio_backend=audio_backend,
                generate_audio=generate_audio,
            ),
        }

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
