from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol


class ExplanationProvider(Protocol):
    name: str

    def explain(self, packet: dict[str, Any]) -> dict[str, Any]: ...


class DeterministicExplanationProvider:
    name = "deterministic"

    def explain(self, _packet: dict[str, Any]) -> dict[str, Any]:
        return {}


def _provider_prompt(packet: dict[str, Any]) -> str:
    compact_packet = {
        "equation_label": packet.get("equation_label"),
        "latex": packet.get("latex"),
        "grouped_expression": packet.get("grouped_expression"),
        "context_evidence": packet.get("context_evidence"),
        "ontology_links": packet.get("ontology_links"),
        "current_summary": packet.get("context_summary"),
    }
    return (
        "Explain this research-paper equation for a blind or low-vision reader. "
        "Use only the supplied paper evidence and ontology records. Every contextual claim and every "
        "domain-specific symbol meaning must cite one or more supplied evidence_id values. If the paper "
        "does not define a symbol, omit that symbol from term_explanations. Return JSON with "
        "context_summary, evidence_ids, equation_role, and term_explanations.\n\n"
        + json.dumps(compact_packet, ensure_ascii=True)
    )


class OllamaExplanationProvider:
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.getenv("MATHONTOSPEAK_OLLAMA_MODEL", "qwen3:8b")

    def explain(self, packet: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": _provider_prompt(packet)}],
            "options": {"temperature": 0},
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload.get("message", {}).get("content", "")
        return json.loads(content) if isinstance(content, str) else dict(content)


class OpenAIExplanationProvider:
    name = "openai"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("MATHONTOSPEAK_OPENAI_MODEL", "gpt-4.1-mini")

    def explain(self, packet: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        body = {
            "model": self.model,
            "input": _provider_prompt(packet),
            "temperature": 0,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        output_text = str(payload.get("output_text") or "")
        if not output_text:
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text += str(content.get("text") or "")
        return json.loads(output_text)


def provider_from_environment() -> ExplanationProvider:
    configured = os.getenv("MATHONTOSPEAK_EXPLANATION_PROVIDER", "deterministic").strip().lower()
    if configured == "ollama":
        return OllamaExplanationProvider()
    if configured == "openai":
        return OpenAIExplanationProvider()
    return DeterministicExplanationProvider()


def validate_grounded_explanation(
    candidate: dict[str, Any],
    packet: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed_evidence = {
        str(item.get("evidence_id"))
        for item in packet.get("context_evidence", [])
        if item.get("evidence_id")
    }
    allowed_symbols = {
        str(item.get("symbol") or item.get("raw") or "")
        for item in packet.get("grouped_expression", [])
        if item.get("kind") == "symbol"
    }
    accepted: dict[str, Any] = {}
    rejected_claims = 0

    summary = str(candidate.get("context_summary") or "").strip()
    summary_evidence = {str(value) for value in candidate.get("evidence_ids", []) if value}
    if summary and summary_evidence and summary_evidence.issubset(allowed_evidence):
        accepted["context_summary"] = summary
        accepted["evidence_ids"] = sorted(summary_evidence)
    elif summary:
        rejected_claims += 1

    role = str(candidate.get("equation_role") or "").strip()
    if role and summary_evidence and summary_evidence.issubset(allowed_evidence):
        accepted["equation_role"] = role

    accepted_terms: list[dict[str, Any]] = []
    for term in candidate.get("term_explanations", []):
        if not isinstance(term, dict):
            rejected_claims += 1
            continue
        symbol = str(term.get("symbol") or "")
        meaning = str(term.get("meaning") or "").strip()
        evidence_ids = {str(value) for value in term.get("evidence_ids", []) if value}
        symbol_matches = symbol in allowed_symbols or any(symbol == value.split("[")[0] for value in allowed_symbols)
        if symbol_matches and meaning and evidence_ids and evidence_ids.issubset(allowed_evidence):
            accepted_terms.append(
                {
                    "symbol": symbol,
                    "meaning": meaning,
                    "evidence_ids": sorted(evidence_ids),
                    "source": "paper_context",
                    "provenance_type": "paper_evidence",
                    "confidence": "medium",
                }
            )
        else:
            rejected_claims += 1
    if accepted_terms:
        accepted["term_explanations"] = accepted_terms

    status = "accepted" if accepted and not rejected_claims else "partial" if accepted else "rejected"
    return accepted, {
        "status": status,
        "accepted_claims": int(bool(accepted.get("context_summary"))) + len(accepted_terms),
        "rejected_claims": rejected_claims,
    }


def run_grounded_provider(
    provider: ExplanationProvider,
    packet: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if provider.name == "deterministic":
        return {}, {"name": provider.name, "status": "not_requested", "accepted_claims": 0, "rejected_claims": 0}
    try:
        candidate = provider.explain(packet)
        accepted, metadata = validate_grounded_explanation(candidate, packet)
        return accepted, {"name": provider.name, **metadata}
    except (RuntimeError, OSError, ValueError, TypeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {}, {
            "name": provider.name,
            "status": "failed",
            "accepted_claims": 0,
            "rejected_claims": 0,
            "detail": f"{type(exc).__name__}: {exc}",
        }
