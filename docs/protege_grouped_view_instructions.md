# Grouped Protege View Instructions

This grouped ontology is a presentation copy for viewing the Week 3 math
ontology in Protege and OntoGraf. It does not replace the official merged
research ontology.

## Files

- Grouped OWL for Protege:
  `ontologies/merged/math_accessibility_kg_week3_grouped_for_protege.owl`
- Grouped Turtle copy:
  `ontologies/merged/math_accessibility_kg_week3_grouped_for_protege.ttl`
- Overview figures:
  `figures/protege_grouped_ontology_overview.svg`
  `figures/protege_grouped_ontology_overview.png`
- Rebuild script:
  `scripts/build_protege_grouped_ontology.py`

## How to open it in Protege

1. Open Protege.
2. Choose **File > Open**.
3. Select `ontologies/merged/math_accessibility_kg_week3_grouped_for_protege.owl`.
4. Start in the **Classes** tab.
5. Expand `Mathematical Concept`.
6. Expand `Kind Concept` or `Role Concept`.

The grouped file adds intermediate buckets such as `Operator Concept`,
`Matrix Concept`, `Transformation Concept`, and `Coefficient Role Concept`.
These buckets keep the class hierarchy from appearing as one long flat list.

## How to use OntoGraf without making a cluster

1. In the **Classes** tab, select one group class, such as `Operator Concept`.
2. Open the **OntoGraf** tab.
3. Start the graph from that selected group, not from `Mathematical Concept`.
4. Hide `owl:Thing` and any unrelated parent nodes if they distract from the
   screenshot.
5. Repeat with another group class when you need a different focused view.

Good starting groups for screenshots:

- `Operator Concept`
- `Transformation Concept`
- `Matrix Concept`
- `Function Concept`
- `Coefficient Role Concept`
- `Constant Role Concept`

## Rebuilding the grouped files

Run:

```powershell
python scripts/build_protege_grouped_ontology.py
```

The script reads the official merged ontology and the Week 3 metadata table,
then regenerates the grouped OWL, grouped TTL, and overview figures.

## What changed in the grouped copy

- The original ontology data, labels, definitions, examples, provenance, and
  gloss records are preserved.
- Week 3 concepts are moved under more specific display groups.
- The official merged ontology is not changed.
