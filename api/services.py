from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.week4_tts_rendering import (
    ArxivEquation,
    GlossRepository,
    SymbolConceptLookup,
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
AUDIENCE_TO_FIELD = {
    "concise": "concise_form",
    "pedagogical": "pedagogical_form",
    "expert": "expert_form",
    "document_role": "document_role_form",
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def tokens_for(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) > 1}


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
