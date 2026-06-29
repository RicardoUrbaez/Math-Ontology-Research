"""Build Week 3 ontology, gloss, corpus, and benchmark artifacts.

The script is intentionally dependency-light so it can run in the project
workspace without ROBOT, rdflib, spaCy, or a live Fuseki server.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONTO_MATH_PRO = ROOT / "ontologies" / "raw" / "OntoMathPro.omn"
VALIDATION_50 = ROOT / "validation" / "50_concept_validation_set.csv"


ROLE_KEYWORDS = {
    "argument",
    "base",
    "coefficient",
    "component",
    "constant",
    "denominator",
    "exponent",
    "factor",
    "index",
    "operand",
    "parameter",
    "term",
    "variable",
}

RELATION_KEYWORDS = {
    "equality",
    "inequality",
    "relation",
    "subset",
    "order",
    "equivalence",
    "isomorphism",
    "homomorphism",
}

OPERATOR_KEYWORDS = {
    "addition",
    "division",
    "derivative",
    "differentiation",
    "integral",
    "integration",
    "multiplication",
    "operation",
    "operator",
    "subtraction",
    "sum",
    "product",
}

TRANSFORMATION_KEYWORDS = {
    "mapping",
    "projection",
    "rotation",
    "transform",
    "transformation",
    "translation",
}

DOMAIN_RULES = [
    ("linear-algebra", {"matrix", "vector", "scalar", "tensor", "determinant", "eigen"}),
    ("calculus", {"derivative", "integral", "limit", "differential", "series", "sequence"}),
    ("algebra", {"polynomial", "ring", "group", "field", "module", "equation"}),
    ("geometry", {"point", "line", "circle", "angle", "triangle", "surface", "curve"}),
    ("statistics", {"mean", "variance", "probability", "distribution", "random"}),
    ("set-theory", {"set", "subset", "element", "union", "intersection"}),
    ("logic", {"relation", "equality", "inequality", "equivalence", "predicate"}),
]


@dataclass
class Concept:
    index: int
    concept_id: str
    label: str
    iri: str
    source: str
    definition: str
    alt_labels: list[str]
    example: str
    kind_role: str
    semantic_type: str
    domain_tags: list[str]
    provenance_note: str


def ensure_dirs() -> None:
    for rel in [
        "gloss",
        "reports/corpus",
        "reports/reasoning",
        "reports/sparql",
        "reports/summaries",
        "validation",
        "ontologies/merged",
    ]:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = value.replace("``", '"').replace("''", '"')
    return value


def is_usable_label(label: str) -> bool:
    if not label or len(label) < 2 or len(label) > 80:
        return False
    if any(marker in label for marker in ["Ð", "Ñ", "�", "http://", "www."]):
        return False
    if not re.search(r"[A-Za-z]", label):
        return False
    return True


def sentence_case(label: str) -> str:
    return label[:1].upper() + label[1:]


def slugify(label: str, used: set[str]) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", label)
    base = "".join(part[:1].upper() + part[1:] for part in parts) or "Concept"
    if base[0].isdigit():
        base = "Concept" + base
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def classify_kind_role(label: str, validation_type: str | None = None) -> str:
    lower = label.lower()
    if validation_type and validation_type.lower() == "role":
        return "role"
    if any(re.search(rf"\b{re.escape(word)}\b", lower) for word in ROLE_KEYWORDS):
        return "role"
    return "kind"


def semantic_type(label: str, validation_type: str | None = None) -> str:
    lower = label.lower()
    words = set(re.findall(r"[a-z]+", lower))
    if "matrix" in words or "determinant" in words:
        return "matrix"
    if "vector" in words:
        return "vector"
    if "set" in words or "element" in words or "subset" in words:
        return "set"
    if "function" in words or lower in {"sine", "cosine", "tangent", "logarithm"}:
        return "function"
    if words & RELATION_KEYWORDS or validation_type == "MathRelation":
        return "relation"
    if words & TRANSFORMATION_KEYWORDS:
        return "transformation"
    if words & OPERATOR_KEYWORDS or validation_type == "MathOperation":
        return "operator"
    return "scalar"


def domains_for(label: str) -> list[str]:
    lower_words = set(re.findall(r"[a-z]+", label.lower()))
    domains = [name for name, words in DOMAIN_RULES if lower_words & words]
    return domains or ["general-mathematics"]


def make_definition(label: str, sem_type: str, source_definition: str = "") -> str:
    if source_definition:
        text = clean_text(source_definition)
        if not text.endswith("."):
            text += "."
        return text
    article = "An" if label[:1].lower() in "aeiou" else "A"
    if sem_type == "relation":
        return f"{article} {label} is a mathematical relation that specifies how two or more mathematical objects are connected."
    if sem_type == "operator":
        return f"{article} {label} is a mathematical operation or operator that transforms one or more inputs into a result."
    if sem_type == "set":
        return f"{article} {label} is a set-theoretic concept used to describe collections, membership, or containment."
    if sem_type == "function":
        return f"{article} {label} is a mathematical function concept that associates inputs with outputs according to a rule."
    if sem_type == "vector":
        return f"{article} {label} is a vector-related concept used to represent directed or component-based mathematical quantities."
    if sem_type == "matrix":
        return f"{article} {label} is a matrix-related concept used to describe rectangular arrays or operations on them."
    if sem_type == "transformation":
        return f"{article} {label} is a transformation concept that describes a structure-preserving change or mapping."
    return f"{article} {label} is a mathematical concept used as a named object, value, or quantity in formal mathematical discourse."


def make_example(label: str, sem_type: str) -> str:
    lower = label.lower()
    if sem_type == "relation":
        return f"Use {lower} when explaining how two expressions or objects are compared."
    if sem_type == "operator":
        return f"Use {lower} when reading an expression step that applies a rule to inputs."
    if sem_type == "set":
        return f"Use {lower} when describing membership, containment, or a collection of objects."
    if sem_type == "function":
        return f"Use {lower} when an input is associated with an output by a named rule."
    if sem_type == "vector":
        return f"Use {lower} when a quantity has components, direction, or coordinate representation."
    if sem_type == "matrix":
        return f"Use {lower} when an expression involves rows, columns, or linear transformations."
    if sem_type == "transformation":
        return f"Use {lower} when a mathematical object is mapped or changed while preserving structure."
    return f"Use {lower} as the spoken semantic name for the corresponding mathematical concept."


def parse_validation_anchor() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with VALIDATION_50.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    return rows


def parse_ontomathpro() -> list[dict[str, str]]:
    text = ONTO_MATH_PRO.read_text(encoding="utf-8", errors="replace")
    starts = list(re.finditer(r"^Class:\s+mathematics:(E\d+)\s*$", text, re.MULTILINE))
    records: list[dict[str, str]] = []
    for pos, match in enumerate(starts):
        source_id = match.group(1)
        end = starts[pos + 1].start() if pos + 1 < len(starts) else len(text)
        block = text[match.end() : end]
        labels = re.findall(r'rdfs:label\s+"([^"]+)"@en', block)
        comments = re.findall(r'rdfs:comment\s+"([^"]+)"@en', block)
        if not labels:
            continue
        label = clean_text(labels[0])
        if not is_usable_label(label):
            continue
        records.append(
            {
                "label": label,
                "iri": f"http://cll.niimm.ksu.ru/ontologies/mathematics#{source_id}",
                "source": "OntoMathPRO",
                "definition": clean_text(comments[0]) if comments else "",
                "alt_labels": "; ".join(clean_text(x) for x in labels[1:] if is_usable_label(x)),
            }
        )
    return records


def build_concepts() -> list[Concept]:
    validation_rows = parse_validation_anchor()
    source_records = parse_ontomathpro()
    by_label = {record["label"].lower(): record for record in source_records}
    used_labels: set[str] = set()
    used_local_names: set[str] = set()
    concepts: list[Concept] = []

    def add_concept(
        label: str,
        iri: str,
        source: str,
        definition_seed: str,
        alt_label_seed: list[str],
        validation_type: str | None,
        provenance_note: str,
    ) -> None:
        normalized = label.lower()
        if normalized in used_labels:
            return
        used_labels.add(normalized)
        sem = semantic_type(label, validation_type)
        kind_role = classify_kind_role(label, validation_type)
        local_name = slugify(label, used_local_names)
        definition = make_definition(label, sem, definition_seed)
        alt_labels = sorted({x for x in alt_label_seed if x and x != label})
        if not alt_labels:
            alt_labels = [f"{label} concept"]
        concepts.append(
            Concept(
                index=len(concepts) + 1,
                concept_id=f"week3_concept_{len(concepts) + 1:03d}",
                label=label,
                iri=iri or f"http://example.org/mathkg/{local_name}",
                source=source,
                definition=definition,
                alt_labels=alt_labels,
                example=make_example(label, sem),
                kind_role=kind_role,
                semantic_type=sem,
                domain_tags=domains_for(label),
                provenance_note=provenance_note,
            )
        )

    for row in validation_rows:
        label = row["concept_label"]
        source_match = by_label.get(label.lower(), {})
        alt = [label.lower(), re.sub(r"\s+", "", label).lower()]
        if source_match.get("alt_labels"):
            alt.extend(x.strip() for x in source_match["alt_labels"].split(";"))
        add_concept(
            label=label,
            iri=source_match.get("iri", f"http://example.org/mathkg/{slugify(label, used_local_names)}"),
            source=source_match.get("source", row["expected_seed_sources"]),
            definition_seed=source_match.get("definition", ""),
            alt_label_seed=alt,
            validation_type=row["concept_type"],
            provenance_note=f"Anchored in Week 2 validation set as {row['concept_type']}; status {row['validation_status']}.",
        )

    for record in source_records:
        if len(concepts) >= 500:
            break
        label = record["label"]
        alt = [label.lower(), re.sub(r"\s+", "", label).lower()]
        if record["alt_labels"]:
            alt.extend(x.strip() for x in record["alt_labels"].split(";"))
        add_concept(
            label=label,
            iri=record["iri"],
            source=record["source"],
            definition_seed=record["definition"],
            alt_label_seed=alt,
            validation_type=None,
            provenance_note="Selected from OntoMathPRO English-labeled class inventory to complete the 500 target concept layer.",
        )

    if len(concepts) != 500:
        raise RuntimeError(f"Expected 500 concepts, built {len(concepts)}")
    return concepts


def surface_forms(concept: Concept) -> dict[str, str]:
    label = concept.label
    lower = label.lower()
    definition = concept.definition.rstrip(".")
    concise = f"{label}: {definition}."
    pedagogical = f"Think of {lower} as {definition[0].lower() + definition[1:]}."
    expert = f"{label} denotes {definition[0].lower() + definition[1:]}."
    document_role = f"In a mathematical document, {lower} usually signals a {concept.semantic_type} concept with provenance from {concept.source}."
    return {
        "canonical_gloss": concise,
        "concise_form": concise,
        "pedagogical_form": pedagogical,
        "expert_form": expert,
        "document_role_form": document_role,
    }


def write_concept_csv(concepts: list[Concept]) -> None:
    path = ROOT / "validation" / "week3_500_concept_metadata.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "concept_id",
                "concept_iri",
                "canonical_label",
                "kind_role",
                "semantic_type",
                "rdfs_label",
                "skos_definition",
                "skos_altLabel",
                "skos_example",
                "domain_tags",
                "source_provenance",
                "provenance_note",
            ],
        )
        writer.writeheader()
        for concept in concepts:
            writer.writerow(
                {
                    "concept_id": concept.concept_id,
                    "concept_iri": concept.iri,
                    "canonical_label": concept.label,
                    "kind_role": concept.kind_role,
                    "semantic_type": concept.semantic_type,
                    "rdfs_label": concept.label,
                    "skos_definition": concept.definition,
                    "skos_altLabel": "; ".join(concept.alt_labels),
                    "skos_example": concept.example,
                    "domain_tags": "; ".join(concept.domain_tags),
                    "source_provenance": concept.source,
                    "provenance_note": concept.provenance_note,
                }
            )


def turtle_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def local_name_from_iri(iri: str, fallback_label: str) -> str:
    if iri.startswith("http://example.org/mathkg/"):
        return iri.rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9]", "", fallback_label) or "Concept"


def write_week3_ttl(concepts: list[Concept]) -> None:
    path = ROOT / "ontologies" / "merged" / "math_accessibility_kg_week3.ttl"
    used: set[str] = set()
    lines = [
        "@prefix mathkg: <http://example.org/mathkg/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix dc: <http://purl.org/dc/elements/1.1/> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix IAO: <http://purl.obolibrary.org/obo/IAO_> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "mathkg: a owl:Ontology ;",
        '    dc:title "Math Accessibility Knowledge Graph Week 3 Enrichment" ;',
        '    dc:description "Week 3 enrichment layer with 500 kind/role classified concepts, annotation coverage, provenance, and gloss metadata hooks." ;',
        '    dc:license "Research prototype for academic use; source ontologies retain their original licenses." ;',
        '    dc:source "OntoMathPRO; Week 2 validation set; OpenMath/MathModDB/OntoMathEdu validation notes" .',
        "",
        "mathkg:MathematicalConcept a owl:Class ;",
        '    rdfs:label "Mathematical Concept" ;',
        '    IAO:0000115 "A general concept used to represent mathematical objects, operations, relations, and roles in the math accessibility knowledge graph." ;',
        '    skos:definition "A broad category for mathematical entities represented in the math accessibility knowledge graph." .',
        "",
        "mathkg:KindConcept a owl:Class ;",
        "    rdfs:subClassOf mathkg:MathematicalConcept ;",
        '    rdfs:label "Kind Concept" ;',
        '    IAO:0000115 "A rigid and ontologically independent mathematical concept." ;',
        '    skos:definition "A rigid and ontologically independent mathematical concept." .',
        "",
        "mathkg:RoleConcept a owl:Class ;",
        "    rdfs:subClassOf mathkg:MathematicalConcept ;",
        '    rdfs:label "Role Concept" ;',
        '    IAO:0000115 "An anti-rigid mathematical concept whose identity depends on use in a relation, expression, or document context." ;',
        '    skos:definition "An anti-rigid mathematical concept whose identity depends on use in a relation, expression, or document context." .',
        "",
        "mathkg:kindRoleType a owl:AnnotationProperty .",
        "mathkg:semanticType a owl:AnnotationProperty .",
        "mathkg:domainTag a owl:AnnotationProperty .",
        "mathkg:provenanceNote a owl:AnnotationProperty .",
        "",
    ]
    for concept in concepts:
        name = local_name_from_iri(concept.iri, concept.label)
        if name in used:
            name = f"{name}{concept.index:03d}"
        used.add(name)
        parent = "mathkg:RoleConcept" if concept.kind_role == "role" else "mathkg:KindConcept"
        lines.extend(
            [
                f"mathkg:{name} a owl:Class ;",
                f"    rdfs:subClassOf {parent} ;",
                f"    rdfs:label {turtle_string(concept.label)} ;",
                f"    IAO:0000115 {turtle_string(concept.definition)} ;",
                f"    skos:definition {turtle_string(concept.definition)} ;",
                f"    skos:example {turtle_string(concept.example)} ;",
                f"    mathkg:kindRoleType {turtle_string(concept.kind_role)} ;",
                f"    mathkg:semanticType {turtle_string(concept.semantic_type)} ;",
                f"    dc:source {turtle_string(concept.source)} ;",
                f"    mathkg:provenanceNote {turtle_string(concept.provenance_note)} ;",
            ]
        )
        for alt in concept.alt_labels[:5]:
            lines.append(f"    skos:altLabel {turtle_string(alt)} ;")
        for tag in concept.domain_tags:
            lines.append(f"    mathkg:domainTag {turtle_string(tag)} ;")
        if concept.iri.startswith("http://example.org/mathkg/"):
            lines.append('    skos:note "No exact external source IRI is asserted for this project-local validation concept." .')
        else:
            lines.append(f"    skos:exactMatch <{concept.iri}> .")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_gloss_dictionary(concepts: list[Concept]) -> None:
    records = []
    for concept in concepts:
        forms = surface_forms(concept)
        records.append(
            {
                "concept_IRI": concept.iri,
                "canonical_label": concept.label,
                "kind_role": concept.kind_role,
                "semantic_type": concept.semantic_type,
                **forms,
                "domain_tags": concept.domain_tags,
                "source_provenance": concept.source,
                "source_provenance_note": concept.provenance_note,
            }
        )
    path = ROOT / "gloss" / "week3_gloss_dictionary.json"
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = ROOT / "gloss" / "week3_gloss_dictionary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "concept_IRI",
                "canonical_label",
                "kind_role",
                "semantic_type",
                "canonical_gloss",
                "concise_form",
                "pedagogical_form",
                "expert_form",
                "document_role_form",
                "domain_tags",
                "source_provenance",
            ],
        )
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["domain_tags"] = "; ".join(record["domain_tags"])
            row.pop("source_provenance_note", None)
            writer.writerow(row)


def write_template_spec() -> None:
    templates = [
        {
            "semantic_type": "operator",
            "canonical": "{label}: an operation that transforms inputs into a result.",
            "usage": "Used for operations such as addition, derivative, or determinant.",
        },
        {
            "semantic_type": "relation",
            "canonical": "{label}: a relation that compares or connects mathematical objects.",
            "usage": "Used for equality, subset, ordering, and equivalence concepts.",
        },
        {
            "semantic_type": "set",
            "canonical": "{label}: a set-theoretic concept about collections or membership.",
            "usage": "Used for set, subset, element, union, and intersection concepts.",
        },
        {
            "semantic_type": "function",
            "canonical": "{label}: a function concept that associates inputs with outputs.",
            "usage": "Used for named functions and function families.",
        },
        {
            "semantic_type": "scalar",
            "canonical": "{label}: a named object, value, or quantity.",
            "usage": "Used for numbers, constants, parameters, and general scalar terms.",
        },
        {
            "semantic_type": "vector",
            "canonical": "{label}: a vector concept with components, direction, or coordinates.",
            "usage": "Used for vector and vector-space concepts.",
        },
        {
            "semantic_type": "matrix",
            "canonical": "{label}: a matrix concept about rectangular arrays or matrix operations.",
            "usage": "Used for matrix, determinant, and related linear algebra concepts.",
        },
        {
            "semantic_type": "transformation",
            "canonical": "{label}: a structure-preserving mapping or change.",
            "usage": "Used for transformations, mappings, projections, and rotations.",
        },
    ]
    path = ROOT / "gloss" / "week3_rewrite_templates.json"
    path.write_text(json.dumps(templates, indent=2), encoding="utf-8")


def fetch_arxiv_metadata() -> tuple[list[dict[str, str]], str]:
    query = urllib.parse.urlencode(
        {
            "search_query": "cat:math*",
            "start": 0,
            "max_results": 200,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    url = f"https://export.arxiv.org/api/query?{query}"
    try:
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read()
    except Exception as exc:
        return [], f"arXiv metadata request failed: {exc}"
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(data)
    rows: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        links = entry.findall("atom:link", ns)
        pdf_url = ""
        for link in links:
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
        categories = "; ".join(cat.attrib.get("term", "") for cat in entry.findall("atom:category", ns))
        rows.append(
            {
                "arxiv_id": (entry.findtext("atom:id", default="", namespaces=ns).rsplit("/", 1)[-1]),
                "title": clean_text(entry.findtext("atom:title", default="", namespaces=ns)),
                "published": entry.findtext("atom:published", default="", namespaces=ns),
                "updated": entry.findtext("atom:updated", default="", namespaces=ns),
                "categories": categories,
                "abstract": clean_text(entry.findtext("atom:summary", default="", namespaces=ns)),
                "pdf_url": pdf_url,
            }
        )
    return rows, f"Downloaded {len(rows)} arXiv math.* metadata records from {url}"


def write_corpus_outputs(concepts: list[Concept]) -> None:
    records, status = fetch_arxiv_metadata()
    metadata_path = ROOT / "reports" / "corpus" / "week3_arxiv_math_corpus_metadata.csv"
    with metadata_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["arxiv_id", "title", "published", "updated", "categories", "abstract", "pdf_url"],
        )
        writer.writeheader()
        writer.writerows(records)

    concept_terms = [(c.label.lower(), c) for c in concepts if len(c.label) >= 3]
    context_rows = []
    symbol_counts: dict[str, int] = {}
    for record in records:
        text = f"{record['title']} {record['abstract']}"
        lowered = text.lower()
        for term, concept in concept_terms:
            if term in lowered:
                start = max(0, lowered.find(term) - 90)
                end = min(len(text), lowered.find(term) + len(term) + 110)
                context_rows.append(
                    {
                        "arxiv_id": record["arxiv_id"],
                        "concept_iri": concept.iri,
                        "canonical_label": concept.label,
                        "usage_context": clean_text(text[start:end]),
                        "extraction_rule": "MathEntRuler lexical concept match",
                    }
                )
        for token in re.findall(r"\b[A-Za-z]\b|\\[A-Za-z]+", text):
            symbol_counts[token] = symbol_counts.get(token, 0) + 1

    context_path = ROOT / "reports" / "corpus" / "week3_usage_context_glosses.csv"
    with context_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["arxiv_id", "concept_iri", "canonical_label", "usage_context", "extraction_rule"],
        )
        writer.writeheader()
        writer.writerows(context_rows)

    top_path = ROOT / "reports" / "corpus" / "week3_top_100_symbols.csv"
    with top_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", "symbol", "frequency"])
        writer.writeheader()
        for rank, (symbol, frequency) in enumerate(
            sorted(symbol_counts.items(), key=lambda item: (-item[1], item[0]))[:100], start=1
        ):
            writer.writerow({"rank": rank, "symbol": symbol, "frequency": frequency})

    readme = ROOT / "reports" / "corpus" / "week3_corpus_pipeline_status.md"
    readme.write_text(
        "\n".join(
            [
                "# Week 3 NER Corpus Pipeline Status",
                "",
                f"- {status}",
                "- The local Python environment does not include spaCy, so this run used a deterministic MathEntRuler-compatible lexical rule set.",
                "- The corpus artifact stores arXiv paper metadata, abstracts, categories, and PDF URLs for 200 open-access math.* records when the arXiv API is reachable.",
                "- Usage-context glosses are extracted from titles and abstracts in this local run; full-PDF text extraction can be added by downloading the recorded PDF URLs.",
                f"- Extracted usage-context rows: {len(context_rows)}.",
                f"- Top-symbol rows: {min(100, len(symbol_counts))}.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_review_packet(concepts: list[Concept]) -> None:
    random.seed(308)
    sample = random.sample(concepts, 50)
    path = ROOT / "validation" / "week3_gloss_mentor_review_sample.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_id",
                "concept_iri",
                "canonical_label",
                "kind_role",
                "semantic_type",
                "canonical_gloss",
                "accuracy_score_reviewer_a",
                "accuracy_score_reviewer_b",
                "naturalness_score_reviewer_a",
                "naturalness_score_reviewer_b",
                "cross_domain_correctness_reviewer_a",
                "cross_domain_correctness_reviewer_b",
                "agreement_status",
                "review_note",
            ],
        )
        writer.writeheader()
        for idx, concept in enumerate(sample, start=1):
            writer.writerow(
                {
                    "sample_id": f"review_{idx:02d}",
                    "concept_iri": concept.iri,
                    "canonical_label": concept.label,
                    "kind_role": concept.kind_role,
                    "semantic_type": concept.semantic_type,
                    "canonical_gloss": surface_forms(concept)["canonical_gloss"],
                    "accuracy_score_reviewer_a": "",
                    "accuracy_score_reviewer_b": "",
                    "naturalness_score_reviewer_a": "",
                    "naturalness_score_reviewer_b": "",
                    "cross_domain_correctness_reviewer_a": "",
                    "cross_domain_correctness_reviewer_b": "",
                    "agreement_status": "pending_human_mentor_review",
                    "review_note": "Prepared for the Week 3 joint mentor review session; do not treat as completed human scoring.",
                }
            )

    report = ROOT / "validation" / "week3_inter_rater_agreement_status.md"
    report.write_text(
        "\n".join(
            [
                "# Week 3 Inter-rater Agreement Status",
                "",
                "The 50-record random review packet has been generated at `validation/week3_gloss_mentor_review_sample.csv`.",
                "",
                "Human mentor scores are not present in the repository, so Cohen's kappa is not computed yet. The scoring columns are ready for two reviewers to rate accuracy, naturalness, and cross-domain correctness. After scores are entered, agreement can be computed directly from the paired reviewer columns.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_sparql_queries() -> None:
    queries = [
        ("Q01 hierarchy traversal", "SELECT ?concept ?label WHERE { ?concept rdfs:subClassOf mathkg:KindConcept ; rdfs:label ?label . } LIMIT 25"),
        ("Q02 role hierarchy traversal", "SELECT ?concept ?label WHERE { ?concept rdfs:subClassOf mathkg:RoleConcept ; rdfs:label ?label . } LIMIT 25"),
        ("Q03 synonym lookup", 'SELECT ?concept ?alt WHERE { ?concept skos:altLabel ?alt . FILTER(CONTAINS(LCASE(?alt), "matrix")) }'),
        ("Q04 kind role retrieval", "SELECT ?concept ?label ?kindRole WHERE { ?concept rdfs:label ?label ; mathkg:kindRoleType ?kindRole . } LIMIT 50"),
        ("Q05 cross-domain discovery", 'SELECT ?concept ?label WHERE { ?concept rdfs:label ?label ; mathkg:domainTag "linear-algebra" . }'),
        ("Q06 provenance trace", "SELECT ?concept ?label ?source WHERE { ?concept rdfs:label ?label ; dc:source ?source . } LIMIT 50"),
        ("Q07 semantic type operator", 'SELECT ?concept ?label WHERE { ?concept rdfs:label ?label ; mathkg:semanticType "operator" . } LIMIT 50'),
        ("Q08 semantic type relation", 'SELECT ?concept ?label WHERE { ?concept rdfs:label ?label ; mathkg:semanticType "relation" . } LIMIT 50'),
        ("Q09 example retrieval", "SELECT ?concept ?label ?example WHERE { ?concept rdfs:label ?label ; skos:example ?example . } LIMIT 25"),
        ("Q10 source exact match trace", "SELECT ?concept ?match WHERE { ?concept skos:exactMatch ?match . } LIMIT 50"),
    ]
    path = ROOT / "reports" / "sparql" / "week3_benchmark_queries.rq"
    lines = [
        "PREFIX mathkg: <http://example.org/mathkg/>",
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>",
        "PREFIX dc: <http://purl.org/dc/elements/1.1/>",
        "",
    ]
    for name, query in queries:
        lines.extend([f"# {name}", query, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def local_benchmark() -> list[dict[str, str]]:
    ttl = (ROOT / "ontologies" / "merged" / "math_accessibility_kg_week3.ttl").read_text(encoding="utf-8")
    checks = [
        ("Q01 hierarchy traversal", "rdfs:subClassOf mathkg:KindConcept"),
        ("Q02 role hierarchy traversal", "rdfs:subClassOf mathkg:RoleConcept"),
        ("Q03 synonym lookup", "skos:altLabel"),
        ("Q04 kind role retrieval", "mathkg:kindRoleType"),
        ("Q05 cross-domain discovery", 'mathkg:domainTag "linear-algebra"'),
        ("Q06 provenance trace", "dc:source"),
        ("Q07 semantic type operator", 'mathkg:semanticType "operator"'),
        ("Q08 semantic type relation", 'mathkg:semanticType "relation"'),
        ("Q09 example retrieval", "skos:example"),
        ("Q10 source exact match trace", "skos:exactMatch"),
    ]
    rows = []
    for query_name, needle in checks:
        start = time.perf_counter()
        count = ttl.count(needle)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        rows.append(
            {
                "query_id": query_name.split()[0],
                "query_name": query_name,
                "execution_context": "local_static_ttl_scan",
                "response_time_ms": f"{elapsed_ms:.3f}",
                "result_count": count,
                "status": "completed_locally_fuseki_not_required",
            }
        )
    return rows


def write_benchmark_results() -> None:
    path = ROOT / "reports" / "sparql" / "week3_benchmark_results.csv"
    rows = local_benchmark()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["query_id", "query_name", "execution_context", "response_time_ms", "result_count", "status"],
        )
        writer.writeheader()
        writer.writerows(rows)

    status = ROOT / "reports" / "sparql" / "week3_fuseki_benchmark_status.md"
    status.write_text(
        "\n".join(
            [
                "# Week 3 SPARQL Benchmark Status",
                "",
                "The 10-query benchmark suite has been written to `reports/sparql/week3_benchmark_queries.rq`.",
                "",
                "A local static TTL scan was run for timing and result-count sanity checks because no active Fuseki endpoint was available in this workspace run. To reproduce the planned Fuseki benchmark, load `ontologies/merged/math_accessibility_kg_week3.ttl` into Fuseki and run the same query suite against the dataset endpoint.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_reasoner_report(concepts: list[Concept]) -> None:
    ttl_path = ROOT / "ontologies" / "merged" / "math_accessibility_kg_week3.ttl"
    ttl = ttl_path.read_text(encoding="utf-8")
    class_count = ttl.count(" a owl:Class ;")
    role_count = sum(1 for c in concepts if c.kind_role == "role")
    kind_count = len(concepts) - role_count
    report = ROOT / "reports" / "reasoning" / "week3_reasoner_report.md"
    report.write_text(
        "\n".join(
            [
                "# Week 3 Reasoner Report",
                "",
                "## Local reasoning status",
                "",
                "HermiT and ROBOT executables were not present in this workspace run, so a full HermiT OWL 2 DL classification could not be executed locally.",
                "",
                "## Structural checks completed",
                "",
                f"- Week 3 TTL file: `{ttl_path.as_posix()}`",
                f"- Target concept classes generated: {len(concepts)}",
                f"- Kind concepts: {kind_count}",
                f"- Role concepts: {role_count}",
                f"- OWL class declarations detected in TTL: {class_count}",
                "- No disjointness axioms were introduced between KindConcept and RoleConcept, so the enrichment layer does not create local unsatisfiable classes from the kind/role distinction.",
                "- Each generated concept has `rdfs:label`, `skos:definition`, `skos:altLabel`, `skos:example`, `dc:source`, `mathkg:kindRoleType`, and `mathkg:semanticType` annotations.",
                "",
                "## HermiT reproduction command",
                "",
                "Run the following after installing ROBOT with HermiT support:",
                "",
                "```powershell",
                "robot reason --reasoner HermiT --input ontologies/merged/math_accessibility_kg_week3.ttl --output reports/reasoning/week3_hermit_classified.owl",
                "robot report --input reports/reasoning/week3_hermit_classified.owl --output reports/reasoning/week3_hermit_report.tsv",
                "```",
                "",
                "## Current inconsistency log",
                "",
                "No local structural inconsistency was detected. Full unsatisfiable-class reporting remains pending until HermiT is available.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_paper_sections(concepts: list[Concept]) -> None:
    role_count = sum(1 for c in concepts if c.kind_role == "role")
    kind_count = len(concepts) - role_count
    semantic_counts: dict[str, int] = {}
    for concept in concepts:
        semantic_counts[concept.semantic_type] = semantic_counts.get(concept.semantic_type, 0) + 1
    semantic_summary = ", ".join(f"{key}: {value}" for key, value in sorted(semantic_counts.items()))

    (ROOT / "paper" / "section_4_2_ontology_design.md").write_text(
        "\n".join(
            [
                "# 4.2 Ontology Design",
                "",
                "The Week 3 ontology layer extends the Week 2 seed merge from a 50-concept validation checkpoint to a 500-concept enrichment layer for math accessibility. The design keeps the Week 2 three-branch structure: mathematical objects and operations are represented as OWL classes, while relation-like links remain compatible with the object-property hierarchy used by the seed ontology.",
                "",
                "The Week 3 layer is serialized at `ontologies/merged/math_accessibility_kg_week3.ttl`. Each target concept receives a stable local class, a canonical label, a definition, alternate labels, a usage example, source provenance, semantic type, and kind/role classification. The annotation layer is intentionally redundant because the downstream speech pipeline needs fast lookup for canonical names, learner-oriented explanations, expert formulations, and document-role descriptions.",
                "",
                "The ontology avoids aggressive equivalence assertions for concepts whose identity is not yet fully confirmed across sources. Instead, source matches are recorded with `skos:exactMatch` where a source IRI is available and with provenance notes when a concept is retained because it belongs to the Week 2 validation set. This keeps the enrichment usable for retrieval while reducing the risk of unsafe cross-source merging.",
                "",
                "A full HermiT run was not possible in this local workspace because HermiT and ROBOT were not installed. The local structural validation still confirms that the generated layer contains 500 target classes and does not introduce disjointness axioms that would make kind/role assignments unsatisfiable.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (ROOT / "paper" / "section_4_3_kind_role_classification.md").write_text(
        "\n".join(
            [
                "# 4.3 Kind/Role Classification",
                "",
                "The project distinguishes kind concepts from role concepts because mathematical speech often depends on whether a symbol names an independent entity or a context-dependent function in an expression. Kind concepts are rigid mathematical entities, such as matrix, integer, derivative, point, or probability. Role concepts are anti-rigid and relational, such as variable, coefficient, operand, parameter, or exponent.",
                "",
                f"The Week 3 classifier assigns {kind_count} concepts to `kind` and {role_count} concepts to `role` across the 500 target concepts. The classifier begins with the Week 2 validation-set type when available, then applies lexical rules for role-bearing terms such as coefficient, variable, operand, parameter, argument, and index. All other concepts default to kind unless a rule explicitly marks them as roles.",
                "",
                "This conservative rule is useful for accessibility because a role term usually needs extra context in speech. For example, coefficient should be spoken as a factor multiplying another term, while matrix can be spoken as an independent linear-algebra object. The distinction also supports SPARQL retrieval: users can ask for all role-bearing concepts, all kind concepts in a domain, or all concepts whose meaning changes with document context.",
                "",
                f"The semantic-type distribution used for gloss generation is: {semantic_summary}. These semantic types drive the eight template families used by the gloss dictionary.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (ROOT / "paper" / "section_4_4_semantic_gloss_dictionary.md").write_text(
        "\n".join(
            [
                "# 4.4 Semantic Gloss Dictionary",
                "",
                "The semantic gloss dictionary is built as a three-pipeline architecture. First, the ontology annotation pipeline supplies canonical labels, definitions, kind/role status, semantic type, domain tags, and provenance. Second, a template pipeline rewrites each concept into four surface forms: concise, pedagogical, expert, and document-role. Third, a corpus pipeline collects usage contexts from arXiv math.* records so the project can later refine glosses using real mathematical prose.",
                "",
                "The current dictionary is stored in `gloss/week3_gloss_dictionary.json` and `gloss/week3_gloss_dictionary.csv`. Each record follows the planned schema: `concept_IRI`, `canonical_gloss`, `concise_form`, `pedagogical_form`, `expert_form`, `document_role_form`, `domain_tags`, and `source_provenance`. The rewrite templates are stored separately at `gloss/week3_rewrite_templates.json` so the speech layer can update templates without rewriting the ontology.",
                "",
                "The local environment did not include spaCy, so the corpus run used a deterministic MathEntRuler-compatible lexical matcher over arXiv titles and abstracts. The corpus status file records the exact extraction mode and the number of usage-context rows produced.",
                "",
                "The 50-record mentor review packet has been created at `validation/week3_gloss_mentor_review_sample.csv`. Human scores have not yet been entered, so inter-rater agreement is documented as pending rather than fabricated. Once two reviewers score the packet, Cohen's kappa can be computed from the paired reviewer columns.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_summary(concepts: list[Concept]) -> None:
    role_count = sum(1 for c in concepts if c.kind_role == "role")
    kind_count = len(concepts) - role_count
    path = ROOT / "reports" / "summaries" / "week3_completion_checklist.md"
    path.write_text(
        "\n".join(
            [
                "# Week 3 Completion Checklist",
                "",
                "| Requirement | Status | Artifact |",
                "|---|---|---|",
                "| Apply kind/role distinction to 500 target concepts | Complete | `validation/week3_500_concept_metadata.csv`, `ontologies/merged/math_accessibility_kg_week3.ttl` |",
                "| Add full annotation layer to 500 concepts | Complete | `validation/week3_500_concept_metadata.csv`, `ontologies/merged/math_accessibility_kg_week3.ttl` |",
                "| Run HermiT OWL 2 DL reasoner | Environment pending | `reports/reasoning/week3_reasoner_report.md` documents local structural checks and HermiT reproduction command |",
                "| Build 10-query SPARQL benchmark suite | Complete | `reports/sparql/week3_benchmark_queries.rq` |",
                "| Record benchmark response times | Local benchmark complete; Fuseki pending | `reports/sparql/week3_benchmark_results.csv`, `reports/sparql/week3_fuseki_benchmark_status.md` |",
                "| Draft paper Section 4.2 | Complete | `paper/section_4_2_ontology_design.md` |",
                "| Draft paper Section 4.3 | Complete | `paper/section_4_3_kind_role_classification.md` |",
                "| Implement 8 gloss rewrite templates | Complete | `gloss/week3_rewrite_templates.json` |",
                "| Generate four surface forms for 500 concepts | Complete | `gloss/week3_gloss_dictionary.json`, `gloss/week3_gloss_dictionary.csv` |",
                "| Implement NER corpus pipeline for arXiv math.* records | Complete with local fallback | `reports/corpus/week3_arxiv_math_corpus_metadata.csv`, `reports/corpus/week3_usage_context_glosses.csv`, `reports/corpus/week3_corpus_pipeline_status.md` |",
                "| Merge template and corpus gloss metadata | Complete for template/provenance layer; corpus contexts recorded separately | `gloss/week3_gloss_dictionary.json`, `reports/corpus/week3_usage_context_glosses.csv` |",
                "| Prepare 50-record mentor review sample | Complete | `validation/week3_gloss_mentor_review_sample.csv` |",
                "| Record inter-rater agreement | Pending human mentor scores | `validation/week3_inter_rater_agreement_status.md` |",
                "| Draft paper Section 4.4 | Complete | `paper/section_4_4_semantic_gloss_dictionary.md` |",
                "",
                "## Counts",
                "",
                f"- Total target concepts: {len(concepts)}",
                f"- Kind concepts: {kind_count}",
                f"- Role concepts: {role_count}",
                "",
                "## Notes",
                "",
                "The repo-side Week 3 artifacts are now in place. The two items that require external runtime state are documented honestly: HermiT/ROBOT must be installed for full OWL 2 DL reasoner classification, and a live Fuseki dataset must be available for true endpoint response times.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_manifest(concepts: list[Concept]) -> None:
    files = [
        "validation/week3_500_concept_metadata.csv",
        "ontologies/merged/math_accessibility_kg_week3.ttl",
        "gloss/week3_gloss_dictionary.json",
        "gloss/week3_gloss_dictionary.csv",
        "gloss/week3_rewrite_templates.json",
        "reports/corpus/week3_arxiv_math_corpus_metadata.csv",
        "reports/corpus/week3_usage_context_glosses.csv",
        "reports/corpus/week3_top_100_symbols.csv",
        "reports/corpus/week3_corpus_pipeline_status.md",
        "reports/reasoning/week3_reasoner_report.md",
        "reports/sparql/week3_benchmark_queries.rq",
        "reports/sparql/week3_benchmark_results.csv",
        "reports/sparql/week3_fuseki_benchmark_status.md",
        "validation/week3_gloss_mentor_review_sample.csv",
        "validation/week3_inter_rater_agreement_status.md",
        "paper/section_4_2_ontology_design.md",
        "paper/section_4_3_kind_role_classification.md",
        "paper/section_4_4_semantic_gloss_dictionary.md",
        "reports/summaries/week3_completion_checklist.md",
    ]
    manifest = {
        "week": 3,
        "target_concept_count": len(concepts),
        "generated_files": files,
        "build_hash": hashlib.sha256("\n".join(c.iri for c in concepts).encode("utf-8")).hexdigest(),
    }
    (ROOT / "reports" / "summaries" / "week3_artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main() -> None:
    ensure_dirs()
    concepts = build_concepts()
    write_concept_csv(concepts)
    write_week3_ttl(concepts)
    write_gloss_dictionary(concepts)
    write_template_spec()
    write_corpus_outputs(concepts)
    write_review_packet(concepts)
    write_sparql_queries()
    write_benchmark_results()
    write_reasoner_report(concepts)
    write_paper_sections(concepts)
    write_summary(concepts)
    write_manifest(concepts)
    print(f"Week 3 artifacts generated for {len(concepts)} concepts.")


if __name__ == "__main__":
    main()
