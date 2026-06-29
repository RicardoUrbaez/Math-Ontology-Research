# Protege Visualization Notes

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
