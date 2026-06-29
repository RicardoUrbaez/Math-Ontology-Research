from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GlossRecord:
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
    domain_tags: list[str] = field(default_factory=list)
    source_provenance: str = ""
    source_iri: str = ""
    mapping_quality: str = ""
    accessibility_note: str = ""
    examples: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GlossRecord":
        domain_tags = data.get("domain_tags") or []
        if isinstance(domain_tags, str):
            domain_tags = [tag.strip() for tag in domain_tags.split(";") if tag.strip()]
        examples = data.get("examples") or []
        if isinstance(examples, str):
            examples = [examples]
        return cls(
            concept_iri=str(data.get("concept_iri") or data.get("concept_IRI") or ""),
            local_name=str(data.get("local_name") or data.get("canonical_label") or ""),
            canonical_label=str(data.get("canonical_label") or ""),
            canonical_gloss=str(data.get("canonical_gloss") or data.get("skos_definition") or ""),
            concise_form=str(data.get("concise_form") or ""),
            pedagogical_form=str(data.get("pedagogical_form") or ""),
            expert_form=str(data.get("expert_form") or ""),
            document_role_form=str(data.get("document_role_form") or ""),
            concept_type=str(data.get("concept_type") or data.get("semantic_type") or ""),
            kind_role_classification=str(data.get("kind_role_classification") or data.get("kind_role") or ""),
            domain_tags=list(domain_tags),
            source_provenance=str(data.get("source_provenance") or ""),
            source_iri=str(data.get("source_iri") or data.get("source_IRI") or ""),
            mapping_quality=str(data.get("mapping_quality") or data.get("equivalence_decision") or ""),
            accessibility_note=str(data.get("accessibility_note") or data.get("source_provenance_note") or ""),
            examples=list(examples),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_jsonld_dict(self) -> dict[str, Any]:
        return {
            "@id": self.concept_iri,
            "@type": "mathkg:GlossRecord",
            "rdfs:label": self.canonical_label,
            "skos:prefLabel": self.canonical_label,
            "skos:definition": self.canonical_gloss,
            "mathkg:localName": self.local_name,
            "mathkg:conciseForm": self.concise_form,
            "mathkg:pedagogicalForm": self.pedagogical_form,
            "mathkg:expertForm": self.expert_form,
            "mathkg:documentRoleForm": self.document_role_form,
            "mathkg:conceptType": self.concept_type,
            "mathkg:kindRoleClassification": self.kind_role_classification,
            "mathkg:domainTag": self.domain_tags,
            "dc:source": self.source_provenance,
            "dcterms:source": {"@id": self.source_iri} if self.source_iri else self.source_provenance,
            "mathkg:mappingQuality": self.mapping_quality,
            "mathkg:accessibilityNote": self.accessibility_note,
            "mathkg:example": self.examples,
        }


def load_gloss_records(path: str | Path) -> list[GlossRecord]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    graph = payload.get("@graph") if isinstance(payload, dict) else payload
    if not isinstance(graph, list):
        raise ValueError(f"Expected a list of gloss records in {path}")
    return [GlossRecord.from_dict(record) for record in graph]


def save_gloss_records(records: list[GlossRecord], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps([record.to_dict() for record in records], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def gloss_records_to_jsonld(records: list[GlossRecord]) -> dict[str, Any]:
    return {
        "@context": {
            "mathkg": "http://example.org/mathkg/",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms": "http://purl.org/dc/terms/",
        },
        "@graph": [record.to_jsonld_dict() for record in records],
    }


def save_gloss_records_jsonld(records: list[GlossRecord], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(gloss_records_to_jsonld(records), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
