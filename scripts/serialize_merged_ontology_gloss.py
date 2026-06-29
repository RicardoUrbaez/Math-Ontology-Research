"""Serialize the merged ontology and gloss dictionary as RDF.

This script parses the Week 3 ontology Turtle file, attaches the semantic
gloss dictionary as RDF resources, and writes equivalent Turtle and JSON-LD
serializations for publication and validator checks.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DC, OWL, RDF, RDFS, SKOS, XSD


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ONTOLOGY = ROOT / "reports" / "reasoning" / "math_accessibility_kg_week3_clean.ttl"
DEFAULT_GLOSS = ROOT / "gloss" / "week3_gloss_dictionary.json"
DEFAULT_TTL = ROOT / "ontologies" / "merged" / "math_accessibility_kg_merged_gloss.ttl"
DEFAULT_JSONLD = ROOT / "ontologies" / "merged" / "math_accessibility_kg_merged_gloss.jsonld"

MATHKG = Namespace("http://example.org/mathkg/")
GLOSS = Namespace("http://example.org/mathkg/gloss/")
DCTERMS = Namespace("http://purl.org/dc/terms/")


def slugify(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    slug = "".join(part[:1].upper() + part[1:] for part in parts) or "GlossRecord"
    if slug[0].isdigit():
        slug = f"Concept{slug}"
    return slug


def load_gloss_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        records = json.load(handle)
    if not isinstance(records, list):
        raise ValueError(f"Expected a list of gloss records in {path}")
    return records


def bind_namespaces(graph: Graph) -> None:
    graph.bind("mathkg", MATHKG)
    graph.bind("gloss", GLOSS)
    graph.bind("owl", OWL)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("skos", SKOS)
    graph.bind("dc", DC)
    graph.bind("dcterms", DCTERMS)
    graph.bind("xsd", XSD)


def add_schema(graph: Graph) -> None:
    graph.add((MATHKG.GlossRecord, RDF.type, OWL.Class))
    graph.add((MATHKG.GlossRecord, RDFS.label, Literal("Gloss Record")))
    graph.add(
        (
            MATHKG.GlossRecord,
            SKOS.definition,
            Literal("A structured set of surface forms for a mathematical concept."),
        )
    )

    object_properties = {
        MATHKG.hasGlossRecord: "has gloss record",
        MATHKG.glossForConcept: "gloss for concept",
    }
    for predicate, label in object_properties.items():
        graph.add((predicate, RDF.type, OWL.ObjectProperty))
        graph.add((predicate, RDFS.label, Literal(label)))

    annotation_properties = {
        MATHKG.canonicalGloss: "canonical gloss",
        MATHKG.conciseForm: "concise form",
        MATHKG.pedagogicalForm: "pedagogical form",
        MATHKG.expertForm: "expert form",
        MATHKG.documentRoleForm: "document role form",
        MATHKG.sourceProvenance: "source provenance",
        MATHKG.sourceProvenanceNote: "source provenance note",
    }
    for predicate, label in annotation_properties.items():
        graph.add((predicate, RDF.type, OWL.AnnotationProperty))
        graph.add((predicate, RDFS.label, Literal(label)))


def label_index(graph: Graph) -> dict[str, URIRef]:
    index: dict[str, URIRef] = {}
    for subject, label in graph.subject_objects(RDFS.label):
        if isinstance(subject, URIRef):
            index[str(label).casefold()] = subject
    return index


def concept_for_record(record: dict[str, Any], labels: dict[str, URIRef]) -> URIRef:
    label = str(record.get("canonical_label", "")).strip()
    if label and label.casefold() in labels:
        return labels[label.casefold()]

    iri = str(record.get("concept_IRI", "")).strip()
    if iri.startswith(str(MATHKG)):
        return URIRef(iri)

    if label:
        return URIRef(MATHKG[slugify(label)])

    raise ValueError(f"Gloss record lacks canonical_label and usable concept_IRI: {record}")


def add_literal(graph: Graph, subject: URIRef, predicate: URIRef, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        graph.add((subject, predicate, Literal(text)))


def add_gloss_records(graph: Graph, records: list[dict[str, Any]]) -> None:
    labels = label_index(graph)
    used: set[str] = set()

    for index, record in enumerate(records, start=1):
        label = str(record.get("canonical_label", "")).strip()
        base_slug = slugify(label or f"GlossRecord{index}")
        slug = base_slug
        counter = 2
        while slug in used:
            slug = f"{base_slug}{counter}"
            counter += 1
        used.add(slug)

        concept = concept_for_record(record, labels)
        gloss_record = URIRef(GLOSS[slug])

        graph.add((gloss_record, RDF.type, MATHKG.GlossRecord))
        graph.add((gloss_record, MATHKG.glossForConcept, concept))
        graph.add((concept, MATHKG.hasGlossRecord, gloss_record))
        add_literal(graph, gloss_record, RDFS.label, f"{label} gloss record")
        add_literal(graph, gloss_record, SKOS.prefLabel, label)
        add_literal(graph, gloss_record, MATHKG.canonicalGloss, record.get("canonical_gloss"))
        add_literal(graph, gloss_record, MATHKG.conciseForm, record.get("concise_form"))
        add_literal(graph, gloss_record, MATHKG.pedagogicalForm, record.get("pedagogical_form"))
        add_literal(graph, gloss_record, MATHKG.expertForm, record.get("expert_form"))
        add_literal(graph, gloss_record, MATHKG.documentRoleForm, record.get("document_role_form"))
        add_literal(graph, gloss_record, MATHKG.sourceProvenance, record.get("source_provenance"))
        add_literal(graph, gloss_record, MATHKG.sourceProvenanceNote, record.get("source_provenance_note"))

        for tag in record.get("domain_tags") or []:
            add_literal(graph, gloss_record, MATHKG.domainTag, tag)

        concept_iri = str(record.get("concept_IRI", "")).strip()
        if concept_iri and concept_iri.startswith(("http://", "https://")):
            graph.add((gloss_record, DCTERMS.source, URIRef(concept_iri)))


def jsonld_context() -> dict[str, Any]:
    return {
        "mathkg": str(MATHKG),
        "gloss": str(GLOSS),
        "owl": str(OWL),
        "rdf": str(RDF),
        "rdfs": str(RDFS),
        "skos": str(SKOS),
        "dc": str(DC),
        "dcterms": str(DCTERMS),
        "xsd": str(XSD),
        "label": "rdfs:label",
        "definition": "skos:definition",
        "prefLabel": "skos:prefLabel",
        "hasGlossRecord": {"@id": "mathkg:hasGlossRecord", "@type": "@id"},
        "glossForConcept": {"@id": "mathkg:glossForConcept", "@type": "@id"},
        "canonicalGloss": "mathkg:canonicalGloss",
        "conciseForm": "mathkg:conciseForm",
        "pedagogicalForm": "mathkg:pedagogicalForm",
        "expertForm": "mathkg:expertForm",
        "documentRoleForm": "mathkg:documentRoleForm",
        "sourceProvenance": "mathkg:sourceProvenance",
        "sourceProvenanceNote": "mathkg:sourceProvenanceNote",
        "domainTag": "mathkg:domainTag",
        "source": {"@id": "dcterms:source", "@type": "@id"},
    }


def build_graph(ontology_path: Path, gloss_path: Path) -> Graph:
    graph = Graph()
    bind_namespaces(graph)
    graph.parse(ontology_path, format="turtle")
    add_schema(graph)
    add_gloss_records(graph, load_gloss_records(gloss_path))
    return graph


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY)
    parser.add_argument("--gloss", type=Path, default=DEFAULT_GLOSS)
    parser.add_argument("--ttl", type=Path, default=DEFAULT_TTL)
    parser.add_argument("--jsonld", type=Path, default=DEFAULT_JSONLD)
    args = parser.parse_args()

    graph = build_graph(args.ontology, args.gloss)
    args.ttl.parent.mkdir(parents=True, exist_ok=True)
    args.jsonld.parent.mkdir(parents=True, exist_ok=True)

    graph.serialize(destination=args.ttl, format="turtle", encoding="utf-8")
    graph.serialize(
        destination=args.jsonld,
        format="json-ld",
        context=jsonld_context(),
        indent=2,
        encoding="utf-8",
    )

    print(f"Serialized {len(graph)} RDF triples")
    print(f"Turtle: {display_path(args.ttl)}")
    print(f"JSON-LD: {display_path(args.jsonld)}")


if __name__ == "__main__":
    main()
