from __future__ import annotations

import re

from .gloss_record import GlossRecord


SURFACE_FORM_KEYS = ("concise_form", "pedagogical_form", "expert_form", "document_role_form")


TEMPLATE_FAMILIES = {
    "operator": "an operation or procedure that acts on mathematical inputs",
    "relation": "a relation that states how mathematical objects are connected",
    "set": "a set-theoretic object or relation involving membership, grouping, or containment",
    "function": "a function-like concept that connects inputs with outputs",
    "scalar": "a single mathematical value or quantity in context",
    "vector": "a directed or ordered mathematical object, often used in linear algebra",
    "matrix": "a rectangular array or matrix-related object used to organize values or transformations",
    "transformation": "a rule or process that changes one mathematical object into another",
    "general math object": "a mathematical object whose specific role should be read from context",
}


def _sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    return text if text.endswith((".", "?", "!")) else f"{text}."


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def infer_template_family(record: GlossRecord) -> str:
    label = record.canonical_label.lower()
    type_text = f"{record.concept_type} {' '.join(record.domain_tags)}".lower()
    if any(term in label for term in ("matrix", "determinant")) or "matrix" in type_text:
        return "matrix"
    if "vector" in label or "vector" in type_text:
        return "vector"
    if any(term in label for term in ("function", "sine", "cosine", "tangent", "logarithm", "exponential")):
        return "function"
    if any(term in label for term in ("equality", "inequality", "relation", "subset")) or "relation" in type_text:
        return "relation"
    if any(term in label for term in ("set", "element")) or "set" in type_text:
        return "set"
    if any(term in label for term in ("addition", "subtraction", "multiplication", "division", "integral", "limit", "derivative", "operation", "series")):
        return "operator"
    if any(term in label for term in ("scalar", "number", "coefficient", "constant", "mean", "variance", "probability")):
        return "scalar"
    if any(term in label for term in ("map", "transformation")):
        return "transformation"
    return "general math object"


def generate_surface_forms(record: GlossRecord) -> dict[str, str]:
    """Return four accessible surface forms, preserving curated forms when present."""

    label = record.canonical_label or record.local_name or "Unknown concept"
    lower = label.lower()
    family = infer_template_family(record)
    family_phrase = TEMPLATE_FAMILIES[family]
    gloss = _sentence(record.canonical_gloss) or _sentence(f"{label} is {family_phrase}.")
    source = record.source_provenance or "the Week 2 validation sources"
    qualifier = ""
    if "provisional" in f"{record.mapping_quality} {record.accessibility_note}".lower():
        qualifier = " This record keeps a provisional mapping note, so the wording should be treated as context-sensitive."

    generated = {
        "concise_form": f"{label}: {gloss}",
        "pedagogical_form": f"Think of {lower} as {family_phrase}. {gloss}{qualifier}",
        "expert_form": f"{label} denotes {family_phrase}. {gloss}{qualifier}",
        "document_role_form": (
            f"In a mathematical document, {lower} usually signals {family_phrase}; "
            f"source provenance: {source}.{qualifier}"
        ),
    }
    return {
        key: _sentence(getattr(record, key) or generated[key])
        for key in SURFACE_FORM_KEYS
    }
