"""Apply the professor-facing Week 3 metadata pass to the seed ontology.

This script keeps the Week 2 seed ontology as the Protégé-facing ontology,
adds project annotation properties and 50-concept metadata, and creates the
planning/query files requested in INFO.txt.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_TTL = ROOT / "ontologies" / "merged" / "math_accessibility_kg_seed.ttl"
VALIDATION_SET = ROOT / "validation" / "50_concept_validation_set.csv"
MAPPING_TABLE = ROOT / "validation" / "week2_cross_ontology_mapping_table.csv"
AUDIT_TABLE = ROOT / "validation" / "week2_50_concept_ontology_audit.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def local_name(label: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", label)
    return "".join(part[:1].upper() + part[1:] for part in parts)


def ttl_literal(value: str, lang: str | None = None) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    suffix = f"@{lang}" if lang else ""
    return f'"{escaped}"{suffix}'


def starter_definition(label: str, concept_type: str) -> str:
    low = label.lower()
    if concept_type == "MathOperation":
        return f"{label} is a mathematical operation used to transform one or more inputs into a result."
    if concept_type == "MathRelation":
        return f"{label} is a mathematical relation used to compare or connect mathematical objects."
    if concept_type == "Role":
        return f"{label} is a context-dependent mathematical role used inside expressions, formulas, or models."
    if low in {"coefficient", "constant", "variable"}:
        return f"{label} is a context-dependent mathematical role used inside expressions, formulas, or models."
    return f"{label} is a mathematical concept used as an object, quantity, structure, or named idea in mathematical discourse."


def starter_example(label: str, concept_type: str) -> str:
    low = label.lower()
    if concept_type == "MathOperation":
        return f"Use {low} when reading a step that applies a mathematical rule to inputs."
    if concept_type == "MathRelation":
        return f"Use {low} when explaining how two mathematical objects or expressions are connected."
    if concept_type == "Role":
        return f"Use {low} when a symbol's meaning depends on its role in an expression or model."
    return f"Use {low} as the spoken semantic name for this concept in accessible math output."


def kind_role(label: str, concept_type: str) -> str:
    role_terms = {
        "variable",
        "coefficient",
        "constant",
        "operand",
        "parameter",
        "argument",
        "index",
        "term",
        "factor",
        "exponent",
    }
    if concept_type == "Role" or label.lower() in role_terms:
        return "role"
    return "kind"


def accessibility_note(label: str, concept_type: str) -> str:
    if kind_role(label, concept_type) == "role":
        return "Speech rendering should preserve the expression context because this concept changes meaning by role."
    if concept_type == "MathOperation":
        return "Speech rendering should name the operation and, where possible, identify its operands and result."
    if concept_type == "MathRelation":
        return "Speech rendering should make the relation explicit rather than relying only on symbol names."
    return "Speech rendering should use the canonical label and a concise definition when the notation may be ambiguous."


def metadata_rows() -> list[dict[str, str]]:
    validation = {row["concept_id"]: row for row in read_csv(VALIDATION_SET)}
    mapping = {row["concept_id"]: row for row in read_csv(MAPPING_TABLE)}
    audit = {row["concept_id"]: row for row in read_csv(AUDIT_TABLE)}
    rows: list[dict[str, str]] = []
    for concept_id in sorted(validation.keys()):
        v = validation[concept_id]
        m = mapping.get(concept_id, {})
        a = audit.get(concept_id, {})
        label = v["concept_label"]
        concept_type = v["concept_type"]
        class_iri = a.get("project_class_iri") or f"http://example.org/mathkg/{local_name(label)}"
        if label == "Relation":
            class_iri = "http://example.org/mathkg/RelationConcept"
        definition = starter_definition(label, concept_type)
        review_status = "ready_for_metadata_review"
        if v.get("validation_status") in {"needs_review", "candidate"}:
            review_status = "needs_definition_review"
        rows.append(
            {
                "concept_id": concept_id,
                "concept_label": label,
                "local_class_iri": class_iri,
                "concept_type": concept_type,
                "kind_role_classification": kind_role(label, concept_type),
                "rdfs_label": label,
                "skos_definition": definition,
                "skos_altLabel": "; ".join(
                    dict.fromkeys(
                        item
                        for item in [label.lower(), re.sub(r"\s+", "", label).lower()]
                        if item and item != label
                    )
                ),
                "skos_example": starter_example(label, concept_type),
                "canonical_source": m.get("canonical_source") or v.get("expected_seed_sources", ""),
                "canonical_source_iri": m.get("canonical_iri", ""),
                "mapping_quality": m.get("equivalence_decision") or m.get("merge_status") or a.get("merge_status", ""),
                "provenance_note": m.get("provenance_note") or a.get("notes") or v.get("source_ontology_notes", ""),
                "accessibility_note": accessibility_note(label, concept_type),
                "review_status": review_status,
            }
        )
    return rows


def write_metadata_csv(rows: list[dict[str, str]]) -> None:
    path = ROOT / "validation" / "week3_50_concept_metadata_template.csv"
    fields = [
        "concept_id",
        "concept_label",
        "local_class_iri",
        "concept_type",
        "kind_role_classification",
        "rdfs_label",
        "skos_definition",
        "skos_altLabel",
        "skos_example",
        "canonical_source",
        "canonical_source_iri",
        "mapping_quality",
        "provenance_note",
        "accessibility_note",
        "review_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_prodigy_jsonl(rows: list[dict[str, str]]) -> None:
    path = ROOT / "validation" / "week3_50_concept_metadata_prodigy.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = {
                "text": row["concept_label"],
                "meta": {
                    "concept_id": row["concept_id"],
                    "local_class_iri": row["local_class_iri"],
                    "concept_type": row["concept_type"],
                    "kind_role_classification": row["kind_role_classification"],
                    "definition": row["skos_definition"],
                    "canonical_source": row["canonical_source"],
                    "canonical_source_iri": row["canonical_source_iri"],
                    "mapping_quality": row["mapping_quality"],
                    "provenance_note": row["provenance_note"],
                    "accessibility_note": row["accessibility_note"],
                    "review_status": row["review_status"],
                },
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_annotation_declarations(ttl: str) -> str:
    declarations = [
        ('mathkg:conceptType', 'Concept type', 'An annotation property recording the project-level type assigned to a mathematical concept.'),
        ('mathkg:kindRoleClassification', 'Kind/role classification', 'An annotation property recording whether a concept is treated as a rigid kind or a context-dependent role.'),
        ('mathkg:mappingQuality', 'Mapping quality', 'An annotation property recording the confidence or decision status for a concept mapping.'),
        ('mathkg:accessibilityNote', 'Accessibility note', 'An annotation property recording speech, readability, or accessibility guidance for a concept.'),
        ('mathkg:reviewStatus', 'Review status', 'An annotation property recording whether a concept metadata record is ready or needs further review.'),
        ('mathkg:provenanceNote', 'Provenance note', 'An annotation property recording source and merge-decision notes for a concept.'),
    ]
    insert = []
    for iri, label, definition in declarations:
        if f"{iri} a owl:AnnotationProperty" not in ttl and f"{iri} rdf:type owl:AnnotationProperty" not in ttl:
            insert.extend(
                [
                    f'{iri} a owl:AnnotationProperty ;',
                    f'    rdfs:label "{label}"@en ;',
                    f"    obo:IAO_0000115 {ttl_literal(definition, 'en')} .",
                    "",
                ]
            )
        pattern = re.compile(rf"({re.escape(iri)}\s+(?:a|rdf:type)\s+owl:AnnotationProperty\s*;.*?)(?=\n\n|$)", re.S)
        match = pattern.search(ttl)
        if match and "obo:IAO_0000115" not in match.group(1) and "IAO:0000115" not in match.group(1):
            block = match.group(1).rstrip()
            if block.endswith("."):
                block = block[:-1].rstrip() + " ;"
            block += f"\n    obo:IAO_0000115 {ttl_literal(definition, 'en')} ."
            ttl = ttl[: match.start()] + block + ttl[match.end() :]
    if not insert:
        return ttl
    marker = "#################################################################\n# Upper-level OWL 2 DL hierarchy\n#################################################################\n"
    if marker in ttl:
        return ttl.replace(marker, "\n".join(insert) + "\n" + marker)
    annotation_marker = "#################################################################\n#    Object Properties\n#################################################################\n"
    if annotation_marker in ttl:
        return ttl.replace(annotation_marker, "\n".join(insert) + "\n" + annotation_marker)
    return "\n".join(insert) + "\n" + ttl


def ensure_relation_property_definitions(ttl: str) -> str:
    definitions = {
        "hasElement": "Relates a mathematical object, such as a set, to an element that belongs to it.",
        "isElementOf": "Relates an element to the mathematical object it belongs to.",
        "isSubsetOf": "Relates one set to another set that contains it.",
        "isEqualTo": "Relates two mathematical objects that are considered equal.",
        "isLessThan": "Relates one mathematical object or value to another that is greater than it.",
        "dependsOn": "Relates a mathematical object or concept to another concept it depends on.",
        "hasOperand": "Connects a mathematical operation to one of its input mathematical objects.",
        "hasResult": "Connects a mathematical operation to its output or result.",
    }
    for name, definition in definitions.items():
        pattern = re.compile(
            rf"(mathkg:{name}\s+(?:a|rdf:type)\s+owl:ObjectProperty\s*;.*?)(?=\n\n###|\n\nmathkg:|\Z)",
            re.S,
        )
        match = pattern.search(ttl)
        if not match or "obo:IAO_0000115" in match.group(1) or "IAO:0000115" in match.group(1):
            continue
        block = match.group(1).rstrip()
        if block.endswith("."):
            block = block[:-1].rstrip() + " ;"
        block += f"\n    obo:IAO_0000115 {ttl_literal(definition, 'en')} ."
        ttl = ttl[: match.start()] + block + ttl[match.end() :]
    return ttl


def update_class_block(block: str, row: dict[str, str]) -> str:
    label = re.escape(row["rdfs_label"])
    block = re.sub(rf'rdfs:label\s+"{label}"\s*([;,])', rf'rdfs:label "{row["rdfs_label"]}"@en \1', block)
    block = re.sub(
        rf'\n\s+rdfs:label\s+"{label}"@en\s*[;,]\s*\n\s+rdfs:label\s+"{label}"\s*[;,]',
        f'\n    rdfs:label "{row["rdfs_label"]}"@en ;',
        block,
    )
    block = re.sub(
        rf'\n\s+rdfs:label\s+"{label}"\s*[;,]\s*\n\s+rdfs:label\s+"{label}"@en\s*[;,]',
        f'\n    rdfs:label "{row["rdfs_label"]}"@en ;',
        block,
    )
    block = re.sub(
        rf'\n\s+rdfs:label\s+"{label}"@en\s*[;,]\s*\n\s+rdfs:label\s+"{label}"@en\s*[;,]',
        f'\n    rdfs:label "{row["rdfs_label"]}"@en ;',
        block,
    )
    seen_lines: set[str] = set()
    deduped_lines: list[str] = []
    for line in block.splitlines():
        key = line.strip()
        normalized_key = key.rstrip(" ;.")
        if key.startswith(("skos:altLabel ", "skos:exactMatch ", "dc:source ", "mathkg:", "skos:example ")):
            if normalized_key in seen_lines:
                continue
            seen_lines.add(normalized_key)
        deduped_lines.append(line)
    block = "\n".join(deduped_lines)
    additions: list[tuple[str, str]] = [
        ("rdfs:label", ttl_literal(row["rdfs_label"], "en")),
        ("skos:definition", ttl_literal(row["skos_definition"], "en")),
        ("skos:example", ttl_literal(row["skos_example"], "en")),
        ("mathkg:conceptType", ttl_literal(row["concept_type"])),
        ("mathkg:kindRoleClassification", ttl_literal(row["kind_role_classification"])),
        ("mathkg:mappingQuality", ttl_literal(row["mapping_quality"])),
        ("mathkg:provenanceNote", ttl_literal(row["provenance_note"])),
        ("mathkg:accessibilityNote", ttl_literal(row["accessibility_note"], "en")),
        ("mathkg:reviewStatus", ttl_literal(row["review_status"])),
        ("skos:note", ttl_literal(f"merge_status: {row['mapping_quality']}")),
    ]
    for alt in [item.strip() for item in row["skos_altLabel"].split(";") if item.strip()]:
        additions.append(("skos:altLabel", ttl_literal(alt, "en")))
    if row["canonical_source"] and "dc:source" not in block:
        additions.append(("dc:source", ttl_literal(row["canonical_source"])))
    if row["canonical_source_iri"] and "skos:exactMatch" not in block:
        additions.append(("skos:exactMatch", f"<{row['canonical_source_iri']}>"))

    existing = set()
    for predicate, obj in re.findall(r"\n\s+([A-Za-z0-9_:.-]+)\s+(.+?)\s*[;.]", block):
        existing.add((predicate, obj.strip()))
        if predicate == "rdfs:label" and obj.strip().startswith(ttl_literal(row["rdfs_label"])):
            existing.add(("rdfs:label", ttl_literal(row["rdfs_label"], "en")))

    block = block.rstrip()
    if block.endswith("."):
        block = block[:-1].rstrip() + " ;"
    for predicate, obj in additions:
        if (predicate, obj) not in existing:
            block += f"\n    {predicate} {obj} ;"
    block = block.rstrip()
    if block.endswith(";"):
        block = block[:-1].rstrip() + " ."
    return block


def update_seed_ttl(rows: list[dict[str, str]]) -> None:
    ttl = SEED_TTL.read_text(encoding="utf-8")
    ttl = ensure_annotation_declarations(ttl)
    ttl = ensure_relation_property_definitions(ttl)
    for row in rows:
        name = row["local_class_iri"].rstrip("/#").rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        pattern = re.compile(
            rf"(mathkg:{re.escape(name)}\s+(?:a|rdf:type)\s+owl:Class\s*;.*?)(?=\n\n###|\n\nmathkg:|\Z)",
            re.S,
        )
        match = pattern.search(ttl)
        if not match:
            continue
        updated = update_class_block(match.group(1), row)
        ttl = ttl[: match.start()] + updated + ttl[match.end() :]
    SEED_TTL.write_text(ttl, encoding="utf-8")


def write_metadata_plan() -> None:
    path = ROOT / "validation" / "week3_concept_metadata_plan.md"
    path.write_text(
        """# Week 3 Concept Metadata Plan

## Purpose

Week 3 enriches the current seed ontology with human-readable and machine-queryable metadata. Labels, definitions, examples, provenance, mapping quality, concept type, kind/role classification, and accessibility notes make the ontology easier to inspect in Protege, easier to query with SPARQL, and easier to reuse later for semantic speech and gloss generation.

## Pilot Set and Expansion Target

The current 50 concepts are the pilot and validation subset. Week 2 already validated that these 50 concepts are present, mapped, classified, and provenance-tagged. Week 3 and the next phase enrich those same 50 concepts first, then extend the same metadata pattern toward the future 500-concept target.

## Visualization and Querying

Protege is the primary manual inspection and visualization tool. The Classes tab should show MathObject and MathOperation, the Object properties tab should show MathRelation, and OntoGraf or OWLViz can be used to visualize selected concept neighborhoods. SPARQL queries will be used in Apache Jena Fuseki to audit metadata, retrieve definitions, inspect hierarchy branches, trace provenance, and support future accessibility endpoints.

## Metadata Layer

Each concept should include:

- `rdfs:label`
- `skos:definition`
- `skos:altLabel`
- `skos:example`
- `dc:source` or `dcterms:source`
- `skos:exactMatch` when a canonical source IRI is confirmed
- concept type
- kind/role classification
- mapping quality
- provenance notes
- accessibility notes
- review status

The seed ontology declares local annotation properties for project-specific fields: `mathkg:conceptType`, `mathkg:kindRoleClassification`, `mathkg:mappingQuality`, `mathkg:provenanceNote`, `mathkg:accessibilityNote`, and `mathkg:reviewStatus`.
""",
        encoding="utf-8",
    )


def write_expansion_plan() -> None:
    path = ROOT / "validation" / "week3_500_concept_expansion_plan.md"
    path.write_text(
        """# Week 3 500-Concept Expansion Plan

The current 50 concepts are the validated pilot set. The next target is to expand the ontology to 500 concepts while preserving the same metadata schema and review discipline used for the 50-concept layer.

Each added concept should include concept ID, label, definition, source IRI, source ontology, concept type, kind/role classification, alt labels or synonyms, example usage, accessibility note, provenance note, and review status.

Suggested method:

1. Extract candidate concepts from OntoMathPRO, MathModDB, OpenMath, and OntoMathEdu.
2. Normalize labels and remove duplicate surface forms.
3. Deduplicate concepts by definition, source mapping, and domain usage.
4. Assign canonical IRIs, preferring the project canonicalization rules.
5. Add metadata using the same 50-concept template.
6. Classify concepts as MathObject, MathOperation, MathRelation/role, or another documented category where appropriate.
7. Validate with ROBOT and HermiT.
8. Inspect the expanded ontology in Protege.
9. Query the expanded ontology with SPARQL in Fuseki.
10. Document limitations, provisional mappings, and source gaps.

The existing `validation/week3_500_concept_metadata.csv` and `ontologies/merged/math_accessibility_kg_week3.ttl` are generated expansion artifacts from the earlier Week 3 build. They should be treated as expansion work products requiring review before replacing the 50-concept seed ontology.
""",
        encoding="utf-8",
    )


def write_protege_notes() -> None:
    path = ROOT / "reports" / "protege_visualization_notes.md"
    path.write_text(
        """# Protege Visualization Notes

Open this OWL file in Protege:

`ontologies/merged/math_accessibility_kg_seed.owl`

If Protege shows an empty untitled ontology, use **File > Open...** and select the file above. The screenshot showed an untitled ontology with zero classes, which means the project OWL file was not loaded yet.

## What to Inspect

- Classes tab: `MathObject` and `MathOperation` hierarchy.
- Object properties tab: `MathRelation` hierarchy.
- OntoGraf tab: graph visualization of selected concept neighborhoods.
- OWLViz, if installed: asserted/inferred class hierarchy after reasoner classification.
- Annotations panel: `rdfs:label`, `skos:definition`, `skos:altLabel`, `skos:example`, source metadata, mapping quality, kind/role classification, and accessibility notes.

## Suggested Screenshots

- `MathObject` class hierarchy.
- `MathOperation` class hierarchy.
- `MathRelation` object-property hierarchy.
- OntoGraf visualization for `Constant` or `Equation`.
- Annotation panel showing `rdfs` and `skos` metadata for one concept.

## HermiT

In Protege, choose **Reasoner > HermiT** and then **Reasoner > Start reasoner**. Keep **Show Inferences** checked if you want inferred hierarchy views.
""",
        encoding="utf-8",
    )


def write_prodigy_notes() -> None:
    path = ROOT / "reports" / "prodigy_metadata_notes.md"
    path.write_text(
        """# Prodigy Metadata Notes

The file `validation/week3_50_concept_metadata_prodigy.jsonl` is a Prodigy-style JSONL export for the 50 pilot concepts. Each row uses the concept label as `text` and stores ontology metadata inside `meta`.

This is intended for review or annotation workflows. It does not replace the OWL ontology; the authoritative ontology metadata remains in `ontologies/merged/math_accessibility_kg_seed.ttl` and `ontologies/merged/math_accessibility_kg_seed.owl`.
""",
        encoding="utf-8",
    )


PREFIXES = """PREFIX mathkg: <http://example.org/mathkg/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>

"""


def write_queries() -> None:
    qdir = ROOT / "queries"
    qdir.mkdir(exist_ok=True)
    queries = {
        "01_list_all_concepts.rq": """# Purpose: list all local mathkg concepts with labels and definitions.
SELECT ?concept ?label ?definition
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label .
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
  OPTIONAL { ?concept skos:definition ?definition . }
}
ORDER BY ?label
""",
        "02_concepts_missing_definitions.rq": """# Purpose: find concepts missing skos:definition.
SELECT ?concept ?label
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label .
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
  FILTER NOT EXISTS { ?concept skos:definition ?definition . }
}
ORDER BY ?label
""",
        "03_concepts_by_type.rq": """# Purpose: list concepts grouped by MathObject, MathOperation, Role, etc.
SELECT ?concept ?label ?conceptType ?parent
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label .
  OPTIONAL { ?concept mathkg:conceptType ?conceptType . }
  OPTIONAL { ?concept rdfs:subClassOf ?parent . }
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
}
ORDER BY ?conceptType ?label
""",
        "04_kind_role_lookup.rq": """# Purpose: list concepts with kind/role classification.
SELECT ?concept ?label ?kindRole
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label .
  OPTIONAL { ?concept mathkg:kindRoleClassification ?kindRole . }
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
}
ORDER BY ?kindRole ?label
""",
        "05_provenance_trace.rq": """# Purpose: list each concept with source ontology, source IRI, and mapping quality.
SELECT ?concept ?label ?source ?sourceIRI ?mappingQuality ?provenanceNote
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label .
  OPTIONAL { ?concept dc:source ?source . }
  OPTIONAL { ?concept dcterms:source ?source . }
  OPTIONAL { ?concept skos:exactMatch ?sourceIRI . }
  OPTIONAL { ?concept mathkg:mappingQuality ?mappingQuality . }
  OPTIONAL { ?concept mathkg:provenanceNote ?provenanceNote . }
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
}
ORDER BY ?label
""",
        "06_relation_properties.rq": """# Purpose: list MathRelation subproperties with labels, definitions, domains, and ranges.
SELECT ?property ?label ?definition ?domain ?range
WHERE {
  ?property rdfs:subPropertyOf* mathkg:MathRelation .
  OPTIONAL { ?property rdfs:label ?label . }
  OPTIONAL { ?property skos:definition ?definition . }
  OPTIONAL { ?property rdfs:domain ?domain . }
  OPTIONAL { ?property rdfs:range ?range . }
}
ORDER BY ?label
""",
        "07_alt_labels_synonyms.rq": """# Purpose: list concepts with skos:altLabel values.
SELECT ?concept ?label ?altLabel
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label ;
           skos:altLabel ?altLabel .
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
}
ORDER BY ?label ?altLabel
""",
        "08_accessibility_notes.rq": """# Purpose: list concepts with accessibility notes or speech/readability notes.
SELECT ?concept ?label ?accessibilityNote
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label .
  OPTIONAL { ?concept mathkg:accessibilityNote ?accessibilityNote . }
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
}
ORDER BY ?label
""",
        "09_provisional_mappings.rq": """# Purpose: list concepts with provisional or specialized source mappings.
SELECT ?concept ?label ?note ?mappingQuality ?reviewStatus
WHERE {
  ?concept rdf:type owl:Class ;
           rdfs:label ?label .
  OPTIONAL { ?concept skos:note ?note . }
  OPTIONAL { ?concept mathkg:mappingQuality ?mappingQuality . }
  OPTIONAL { ?concept mathkg:reviewStatus ?reviewStatus . }
  FILTER(STRSTARTS(STR(?concept), STR(mathkg:)))
  FILTER(
    CONTAINS(LCASE(STR(?note)), "provisional") ||
    CONTAINS(LCASE(STR(?note)), "specialized") ||
    CONTAINS(LCASE(STR(?mappingQuality)), "needs") ||
    CONTAINS(LCASE(STR(?reviewStatus)), "review")
  )
}
ORDER BY ?label
""",
        "10_hierarchy_traversal.rq": """# Purpose: traverse subclass hierarchy under MathObject and MathOperation.
SELECT ?root ?concept ?label
WHERE {
  VALUES ?root { mathkg:MathObject mathkg:MathOperation }
  ?concept rdfs:subClassOf* ?root ;
           rdfs:label ?label .
}
ORDER BY ?root ?label
""",
    }
    for filename, body in queries.items():
        (qdir / filename).write_text(PREFIXES + body, encoding="utf-8")
    (qdir / "README.md").write_text(
        """# SPARQL Starter Queries

These are starter SPARQL benchmark and audit queries for the Math Accessibility Knowledge Graph.

They are designed to be run against Apache Jena Fuseki after loading `ontologies/merged/math_accessibility_kg_seed.owl` or `ontologies/merged/math_accessibility_kg_seed.ttl` into a dataset.

The query set supports hierarchy traversal, metadata auditing, kind/role lookup, synonym lookup, relation-property inspection, provisional mapping review, accessibility-note review, and provenance tracing. This matches the research plan requirement to begin SPARQL query development before the 500-concept expansion.
""",
        encoding="utf-8",
    )


def main() -> None:
    rows = metadata_rows()
    write_metadata_csv(rows)
    write_prodigy_jsonl(rows)
    update_seed_ttl(rows)
    write_metadata_plan()
    write_expansion_plan()
    write_protege_notes()
    write_prodigy_notes()
    write_queries()
    print(f"Week 3 professor metadata pass complete for {len(rows)} concepts.")


if __name__ == "__main__":
    main()
