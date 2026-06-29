# Week 2 Provenance and Mapping Summary

This research log summarizes the current Week 2 provenance and mapping work for the Math Accessibility Knowledge Graph.

- Main mapping table: `validation/week2_cross_ontology_mapping_table.csv`
- Seed ontology files:
  - `ontologies/merged/math_accessibility_kg_seed.ttl`
  - `ontologies/merged/math_accessibility_kg_seed.owl`

Each mapped concept currently uses a project-local `mathkg` class and links to a canonical OntoMathPRO IRI through `skos:exactMatch`. This approach preserves a stable local modeling layer while retaining an explicit reference to the current canonical source concept.

`dc:source` annotations are used to record provenance for the seed source in the current ontology version. In addition, `rdfs:comment`, `skos:definition`, and `IAO:0000115` definitions were added to improve readability, accessibility, and ROBOT quality-report results.

Seventeen mapped concepts were included in the seed ontology. The unresolved concept `concept_019` (`Variable`) remains excluded because no exact general `Variable` concept was found across OntoMathPRO, OntoMathEdu, MathModDB, or OpenMath.

Searches did identify narrower variable-related matches, including Random Variable, Decision Variable, Spatial Variable, State Variable, `variable_of_integration`, and `indexed_variable`, but these were not collapsed into the broader concept `Variable`. This preserves semantic precision and avoids introducing a misleading canonical mapping.

The ontology hierarchy was also refined by adding `mathkg:MathematicalConcept` as the root class above `MathObject`, `MathOperation`, and `MathRelation`. This provides a cleaner top-level structure for the seed ontology while keeping the mapped concept classes organized under the three main Week 2 branches.

The final ROBOT report result is 1 total violation, with 0 `ERROR`, 0 `WARN`, and 1 `INFO`. The only remaining `INFO` item is expected because `mathkg:MathematicalConcept` is intentionally modeled as the root class of the seed ontology hierarchy.

Broad `owl:equivalentClass` assertions have not yet been added because exact cross-ontology duplicate IRIs still need to be confirmed. This avoids unsafe merging of narrower or context-specific concepts that may look similar lexically but differ semantically.

Later work will add exact OpenMath, MathModDB, and OntoMathEdu identifiers where the semantic match is confirmed.

## Next Steps

1. Continue confirming exact cross-source identifiers.
2. Add `owl:equivalentClass` only for exact duplicates.
3. Use `skos:closeMatch` or review notes for related but non-identical concepts.
4. Prepare for validation against the full 50-concept set.