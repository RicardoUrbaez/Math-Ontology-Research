from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .gloss_record import GlossRecord, load_gloss_records


DEFAULT_GLOSS_PATH = Path(__file__).resolve().parents[2] / "data" / "gloss_dictionary" / "gloss_records_50.json"


DIRECT_SYMBOL_LABELS = {
    "=": "Equality",
    "+": "Addition",
    "-": "Subtraction",
    "*": "Multiplication",
    r"\cdot": "Multiplication",
    "/": "Division",
    r"\frac": "Division",
    r"\sin": "Sine",
    r"\cos": "Cosine",
    r"\tan": "Tangent",
    r"\int": "Integral",
    r"\lim": "Limit",
    r"\det": "Determinant",
}


def _label_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _record_index(records: list[GlossRecord]) -> dict[str, GlossRecord]:
    return {_label_key(record.canonical_label): record for record in records}


def _candidate(record: GlossRecord, confidence: float, reason: str, ambiguity: str = "") -> dict[str, Any]:
    return {
        "concept_label": record.canonical_label,
        "concept_iri": record.concept_iri,
        "confidence": confidence,
        "reason": reason,
        "ambiguity_notes": ambiguity,
    }


def load_default_records(path: str | Path = DEFAULT_GLOSS_PATH) -> list[GlossRecord]:
    return load_gloss_records(path)


def lookup_symbol_candidates(
    symbol: dict[str, Any],
    records: list[GlossRecord] | None = None,
    context: str | None = None,
) -> list[dict[str, Any]]:
    records = records or load_default_records()
    by_label = _record_index(records)
    raw = str(symbol.get("raw") or "")
    normalized = str(symbol.get("normalized") or raw)
    symbol_type = str(symbol.get("symbol_type") or "")
    context_text = (context or "").lower()
    candidates: list[dict[str, Any]] = []

    def add(label: str, confidence: float, reason: str, ambiguity: str = "") -> None:
        record = by_label.get(_label_key(label))
        if record:
            candidates.append(_candidate(record, confidence, reason, ambiguity))

    direct_label = DIRECT_SYMBOL_LABELS.get(raw) or DIRECT_SYMBOL_LABELS.get(normalized)
    if direct_label:
        add(direct_label, 0.96, f"direct symbol mapping from {raw}")

    if raw == r"\sum":
        if "series" in context_text or "_{" in context_text:
            add("Series", 0.88, "summation notation can denote a series", "Summation can also express repeated addition.")
            add("Addition", 0.72, "summation aggregates terms by addition", "Ranked below Series when indexed notation is present.")
        else:
            add("Addition", 0.82, "summation aggregates terms by addition", "Could denote Series in sequence contexts.")
            add("Series", 0.7, "summation may introduce a series", "Context needed to separate finite sums from series.")

    if symbol_type == "matrix_hint":
        add("Matrix", 0.95, "matrix environment detected")

    if symbol_type == "vector_hint" or raw.startswith(r"\mathbf") or raw.startswith(r"\vec"):
        add("Vector", 0.92, "bold or vector notation detected")

    if raw == "E" and ("probab" in context_text or "statistic" in context_text):
        add("Mean", 0.82, "expectation notation in probability or statistics context", "E can also be a variable outside expectation notation.")

    if raw == "Var":
        add("Variance", 0.95, "variance notation")

    if raw == r"\mu" and ("mean" in context_text or "statistic" in context_text):
        add("Mean", 0.82, "mu often denotes a mean in statistics context", "Greek mu can also be a parameter or variable.")

    if raw in {r"\sigma", r"\sigma^2"} and ("variance" in context_text or "statistic" in context_text):
        add("Variance", 0.78, "sigma notation in variance context", "Sigma can denote standard deviation, variance, or summation depending on notation.")

    if symbol_type == "function_notation":
        add("Function", 0.86, "function application notation")

    if raw == "d" and r"\frac{d}{dx}" in (context or ""):
        add("Derivative", 0.82, "derivative operator pattern d over dx")

    if symbol_type == "matrix_variable" or (raw in {"A", "B"} and "matrix" in context_text):
        add("Matrix", 0.86, "uppercase symbol used in matrix context", "Uppercase letters can also be variables or sets.")

    if raw in {"x", "y", "z", "T", "P", "A", "B", "C", "X"} and not candidates:
        ambiguity = ""
        confidence = 0.8
        if raw == "T":
            ambiguity = "T may denote a variable, transpose, temperature, time, or a transformation."
            confidence = 0.64
        elif raw in {"A", "B", "C"}:
            ambiguity = "Uppercase letters may denote matrices, sets, constants, events, or variables."
            confidence = 0.68
        elif raw == "P":
            ambiguity = "P may denote probability, a point, a polynomial, or a variable."
            confidence = 0.66
        add("Variable", confidence, "single-letter mathematical identifier", ambiguity)

    if raw == "P" and "probab" in context_text:
        add("Probability", 0.78, "P appears in probability context", "P can also be a variable outside probability notation.")

    return sorted(candidates, key=lambda item: item["confidence"], reverse=True)


def lookup_symbols(
    symbols: list[dict[str, Any]],
    records: list[GlossRecord] | None = None,
    context: str | None = None,
) -> list[dict[str, Any]]:
    records = records or load_default_records()
    return [
        {
            **symbol,
            "candidates": lookup_symbol_candidates(symbol, records=records, context=context),
        }
        for symbol in symbols
    ]
