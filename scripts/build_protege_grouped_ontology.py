"""Build a grouped Protégé view of the Math Accessibility ontology.

The source ontology remains unchanged. This script creates a presentation
copy that adds intermediate class buckets so Protégé and OntoGraf do not show
all 500 Week 3 concepts as one flat cluster.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ONTOLOGY = ROOT / "ontologies" / "merged" / "math_accessibility_kg_merged_gloss.ttl"
DEFAULT_METADATA = ROOT / "validation" / "week3_500_concept_metadata.csv"
DEFAULT_TTL = ROOT / "ontologies" / "merged" / "math_accessibility_kg_week3_grouped_for_protege.ttl"
DEFAULT_OWL = ROOT / "ontologies" / "merged" / "math_accessibility_kg_week3_grouped_for_protege.owl"
DEFAULT_SVG = ROOT / "figures" / "protege_grouped_ontology_overview.svg"
DEFAULT_PNG = ROOT / "figures" / "protege_grouped_ontology_overview.png"

MATHKG = Namespace("http://example.org/mathkg/")
DCTERMS = Namespace("http://purl.org/dc/terms/")


@dataclass(frozen=True)
class GroupSpec:
    key: str
    iri: URIRef
    label: str
    parent: URIRef
    definition: str
    color: str


KIND_GROUPS: dict[str, GroupSpec] = {
    "set": GroupSpec(
        "set",
        MATHKG.SetConcept,
        "Set Concept",
        MATHKG.KindConcept,
        "A display group for set-theoretic mathematical concepts.",
        "#4C78A8",
    ),
    "function": GroupSpec(
        "function",
        MATHKG.FunctionConcept,
        "Function Concept",
        MATHKG.KindConcept,
        "A display group for function-related mathematical concepts.",
        "#59A14F",
    ),
    "relation": GroupSpec(
        "relation",
        MATHKG.RelationGroupConcept,
        "Relation Concept",
        MATHKG.KindConcept,
        "A display group for relation-related mathematical concepts.",
        "#E15759",
    ),
    "operator": GroupSpec(
        "operator",
        MATHKG.OperatorConcept,
        "Operator Concept",
        MATHKG.KindConcept,
        "A display group for mathematical operators and operations.",
        "#F28E2B",
    ),
    "transformation": GroupSpec(
        "transformation",
        MATHKG.TransformationConcept,
        "Transformation Concept",
        MATHKG.KindConcept,
        "A display group for mappings, transforms, and structural changes.",
        "#B07AA1",
    ),
    "matrix": GroupSpec(
        "matrix",
        MATHKG.MatrixConcept,
        "Matrix Concept",
        MATHKG.KindConcept,
        "A display group for matrix-related mathematical concepts.",
        "#76B7B2",
    ),
    "vector": GroupSpec(
        "vector",
        MATHKG.VectorConcept,
        "Vector Concept",
        MATHKG.KindConcept,
        "A display group for vector-related mathematical concepts.",
        "#EDC948",
    ),
    "scalar": GroupSpec(
        "scalar",
        MATHKG.ScalarConcept,
        "Scalar Concept",
        MATHKG.KindConcept,
        "A display group for scalar and general mathematical concepts.",
        "#9C755F",
    ),
}

ROLE_GROUPS: dict[str, GroupSpec] = {
    "variable": GroupSpec(
        "variable",
        MATHKG.VariableRoleConcept,
        "Variable Role Concept",
        MATHKG.RoleConcept,
        "A display group for variable roles in mathematical expressions.",
        "#8CD17D",
    ),
    "coefficient": GroupSpec(
        "coefficient",
        MATHKG.CoefficientRoleConcept,
        "Coefficient Role Concept",
        MATHKG.RoleConcept,
        "A display group for coefficient roles in mathematical expressions.",
        "#FF9DA7",
    ),
    "constant": GroupSpec(
        "constant",
        MATHKG.ConstantRoleConcept,
        "Constant Role Concept",
        MATHKG.RoleConcept,
        "A display group for constant and tensor-like role concepts.",
        "#BAB0AC",
    ),
    "other": GroupSpec(
        "other",
        MATHKG.OtherNamedRoleConcept,
        "Other Named Role Concept",
        MATHKG.RoleConcept,
        "A display group for named role concepts that are not variables, coefficients, or constants.",
        "#D37295",
    ),
}


def bind_namespaces(graph: Graph) -> None:
    graph.bind("mathkg", MATHKG)
    graph.bind("owl", OWL)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("skos", SKOS)
    graph.bind("dcterms", DCTERMS)
    graph.bind("xsd", XSD)


def load_metadata(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 500:
        raise ValueError(f"Expected 500 metadata rows, found {len(rows)} in {path}")
    return rows


def label_index(graph: Graph) -> dict[str, URIRef]:
    index: dict[str, URIRef] = {}
    for subject, label in graph.subject_objects(RDFS.label):
        if isinstance(subject, URIRef):
            index.setdefault(str(label).casefold(), subject)
    return index


def subject_exists(graph: Graph, subject: URIRef) -> bool:
    return any(True for _ in graph.triples((subject, None, None)))


def concept_uri_for_row(row: dict[str, str], graph: Graph, labels: dict[str, URIRef]) -> URIRef:
    iri = row["concept_iri"].strip()
    if iri:
        candidate = URIRef(iri)
        if subject_exists(graph, candidate):
            return candidate

    label = row["canonical_label"].strip().casefold()
    if label in labels:
        return labels[label]

    raise ValueError(f"Could not match metadata concept to ontology: {row}")


def role_group_key(label: str) -> str:
    folded = label.casefold()
    if folded == "variable":
        return "variable"
    if "coefficient" in folded:
        return "coefficient"
    if "constant" in folded or "tensor" in folded:
        return "constant"
    return "other"


def group_for_row(row: dict[str, str]) -> GroupSpec:
    kind_role = row["kind_role"].strip().casefold()
    if kind_role == "kind":
        semantic_type = row["semantic_type"].strip().casefold()
        try:
            return KIND_GROUPS[semantic_type]
        except KeyError as exc:
            raise ValueError(f"Unknown semantic_type '{semantic_type}' for {row}") from exc

    if kind_role == "role":
        return ROLE_GROUPS[role_group_key(row["canonical_label"])]

    raise ValueError(f"Unknown kind_role '{kind_role}' for {row}")


def add_group_schema(graph: Graph) -> None:
    graph.add((MATHKG.protegeDisplayGroup, RDF.type, OWL.AnnotationProperty))
    graph.add((MATHKG.protegeDisplayGroup, RDFS.label, Literal("Protege display group")))
    graph.add((MATHKG.groupingBasis, RDF.type, OWL.AnnotationProperty))
    graph.add((MATHKG.groupingBasis, RDFS.label, Literal("grouping basis")))

    for spec in [*KIND_GROUPS.values(), *ROLE_GROUPS.values()]:
        graph.add((spec.iri, RDF.type, OWL.Class))
        graph.add((spec.iri, RDFS.subClassOf, spec.parent))
        graph.add((spec.iri, RDFS.label, Literal(spec.label)))
        graph.add((spec.iri, SKOS.definition, Literal(spec.definition)))
        graph.add((spec.iri, MATHKG.protegeDisplayGroup, Literal(True, datatype=XSD.boolean)))


def build_grouped_graph(ontology_path: Path, metadata_path: Path) -> tuple[Graph, Counter[str]]:
    graph = Graph()
    bind_namespaces(graph)
    graph.parse(ontology_path, format="turtle")
    add_group_schema(graph)

    rows = load_metadata(metadata_path)
    labels = label_index(graph)
    counts: Counter[str] = Counter()

    for row in rows:
        concept = concept_uri_for_row(row, graph, labels)
        group = group_for_row(row)
        parent = MATHKG.KindConcept if row["kind_role"].strip().casefold() == "kind" else MATHKG.RoleConcept

        graph.remove((concept, RDFS.subClassOf, parent))
        graph.add((concept, RDFS.subClassOf, group.iri))
        graph.add((concept, MATHKG.groupingBasis, Literal(group.key)))
        counts[group.label] += 1

    validate_grouping(graph, rows, counts)
    return graph, counts


def validate_grouping(graph: Graph, rows: list[dict[str, str]], counts: Counter[str]) -> None:
    labels = label_index(graph)
    direct_parent_errors: list[str] = []
    missing_group_edges: list[str] = []

    for row in rows:
        concept = concept_uri_for_row(row, graph, labels)
        group = group_for_row(row)
        parent = MATHKG.KindConcept if row["kind_role"].strip().casefold() == "kind" else MATHKG.RoleConcept

        if (concept, RDFS.subClassOf, parent) in graph:
            direct_parent_errors.append(row["canonical_label"])
        if (concept, RDFS.subClassOf, group.iri) not in graph:
            missing_group_edges.append(row["canonical_label"])

    if direct_parent_errors:
        sample = ", ".join(direct_parent_errors[:10])
        raise ValueError(f"Concepts still directly under KindConcept/RoleConcept: {sample}")
    if missing_group_edges:
        sample = ", ".join(missing_group_edges[:10])
        raise ValueError(f"Concepts missing grouped subclass edge: {sample}")

    if sum(counts.values()) != len(rows):
        raise ValueError(f"Grouped {sum(counts.values())} rows, expected {len(rows)}")


def write_grouped_graph(graph: Graph, ttl_path: Path, owl_path: Path) -> None:
    ttl_path.parent.mkdir(parents=True, exist_ok=True)
    owl_path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=ttl_path, format="turtle", encoding="utf-8")
    graph.serialize(destination=owl_path, format="xml", encoding="utf-8")


def draw_overview(counts: Counter[str], svg_path: Path, png_path: Path) -> None:
    group_specs = [*KIND_GROUPS.values(), *ROLE_GROUPS.values()]
    total = sum(counts.values())

    fig, ax = plt.subplots(figsize=(16, 9), dpi=160)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(
        8,
        8.42,
        "Math Accessibility Knowledge Graph - Grouped Protege View",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
    )
    ax.text(
        8,
        8.0,
        f"500 Week 3 concepts organized into {len(KIND_GROUPS)} kind groups and {len(ROLE_GROUPS)} role groups",
        ha="center",
        va="center",
        fontsize=11,
        color="#4A4A4A",
    )

    root_box = dict(boxstyle="round,pad=0.35", facecolor="#EAF2F8", edgecolor="#305C8A", linewidth=1.5)
    ax.text(8, 7.22, "Mathematical Concept", ha="center", va="center", fontsize=13, fontweight="bold", bbox=root_box)

    parent_box = dict(boxstyle="round,pad=0.32", facecolor="#F4F4F4", edgecolor="#666666", linewidth=1.2)
    ax.text(4.7, 6.25, "Kind Concept\n487 concepts", ha="center", va="center", fontsize=11, bbox=parent_box)
    ax.text(12.3, 6.25, "Role Concept\n13 concepts", ha="center", va="center", fontsize=11, bbox=parent_box)

    ax.plot([8, 4.7], [6.95, 6.48], color="#8AA7C5", linewidth=1.1)
    ax.plot([8, 12.3], [6.95, 6.48], color="#8AA7C5", linewidth=1.1)

    positions = {
        "Set Concept": (1.4, 5.0),
        "Function Concept": (3.6, 5.0),
        "Relation Concept": (5.8, 5.0),
        "Operator Concept": (8.0, 5.0),
        "Transformation Concept": (1.9, 3.75),
        "Matrix Concept": (4.25, 3.75),
        "Vector Concept": (6.25, 3.75),
        "Scalar Concept": (8.35, 3.75),
        "Variable Role Concept": (11.1, 5.0),
        "Coefficient Role Concept": (14.0, 5.0),
        "Constant Role Concept": (11.15, 3.75),
        "Other Named Role Concept": (14.05, 3.75),
    }
    display_labels = {
        "Set Concept": "Set\nConcept",
        "Function Concept": "Function\nConcept",
        "Relation Concept": "Relation\nConcept",
        "Operator Concept": "Operator\nConcept",
        "Transformation Concept": "Transformation\nConcept",
        "Matrix Concept": "Matrix\nConcept",
        "Vector Concept": "Vector\nConcept",
        "Scalar Concept": "Scalar\nConcept",
        "Variable Role Concept": "Variable Role\nConcept",
        "Coefficient Role Concept": "Coefficient Role\nConcept",
        "Constant Role Concept": "Constant Role\nConcept",
        "Other Named Role Concept": "Other Named Role\nConcept",
    }

    for spec in group_specs:
        x, y = positions[spec.label]
        count = counts[spec.label]
        box = dict(boxstyle="round,pad=0.28", facecolor=spec.color, edgecolor="#333333", linewidth=1.0, alpha=1.0)
        ax.text(
            x,
            y,
            f"{display_labels[spec.label]}\n{count}",
            ha="center",
            va="center",
            fontsize=9.5,
            color="white",
            fontweight="bold",
            bbox=box,
        )
        parent_x, parent_y = (4.7, 5.92) if spec.parent == MATHKG.KindConcept else (12.3, 5.92)
        ax.plot([parent_x, x], [parent_y, y + 0.28], color="#B0B0B0", linewidth=0.8, zorder=0)

    ax.text(
        8,
        0.85,
        "Open the grouped OWL in Protege, expand Kind Concept or Role Concept, then start OntoGraf from one group.",
        ha="center",
        va="center",
        fontsize=10,
        color="#4A4A4A",
    )

    svg_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--ttl", type=Path, default=DEFAULT_TTL)
    parser.add_argument("--owl", type=Path, default=DEFAULT_OWL)
    parser.add_argument("--svg", type=Path, default=DEFAULT_SVG)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    args = parser.parse_args()

    graph, counts = build_grouped_graph(args.ontology, args.metadata)
    write_grouped_graph(graph, args.ttl, args.owl)
    draw_overview(counts, args.svg, args.png)

    print(f"Grouped {sum(counts.values())} metadata concepts")
    for label, count in sorted(counts.items()):
        print(f"- {label}: {count}")
    print(f"Turtle: {display_path(args.ttl)}")
    print(f"OWL/XML: {display_path(args.owl)}")
    print(f"SVG: {display_path(args.svg)}")
    print(f"PNG: {display_path(args.png)}")


if __name__ == "__main__":
    main()
