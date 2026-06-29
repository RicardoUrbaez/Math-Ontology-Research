# Week 3 500-Concept Expansion Plan

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
