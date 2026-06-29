# Week 3 Reasoner Report

## Local reasoning status

HermiT reasoning was executed with ROBOT on the Week 3 500-concept expansion artifact after ROBOT became available locally.

## Structural checks completed

- Cleaned Week 3 TTL file: `reports/reasoning/math_accessibility_kg_week3_clean.ttl`
- Converted OWL file for reasoning: `reports/reasoning/math_accessibility_kg_week3_clean.owl`
- HermiT classified output: `reports/reasoning/week3_500_clean_hermit_classified.owl`
- Target concept classes generated: 500
- Kind concepts: 487
- Role concepts: 13
- OWL class declarations detected in TTL: 502
- No disjointness axioms were introduced between KindConcept and RoleConcept, so the enrichment layer does not create local unsatisfiable classes from the kind/role distinction.
- Each generated concept has `rdfs:label`, `skos:definition`, `skos:altLabel`, `skos:example`, `dc:source`, `mathkg:kindRoleType`, and `mathkg:semanticType` annotations.
- URL-style source definitions were replaced with readable formal definitions; 0 URL-like definitions remain in the cleaned metadata.
- ROBOT metadata reporting on the cleaned 500 ontology found no violations.

## HermiT reproduction command

Run the following after installing ROBOT with HermiT support:

```powershell
java -jar C:\Robot\robot.jar convert --input reports\reasoning\math_accessibility_kg_week3_clean.ttl --input-format ttl --output reports\reasoning\math_accessibility_kg_week3_clean.owl
java -jar C:\Robot\robot.jar reason --reasoner HermiT --input reports\reasoning\math_accessibility_kg_week3_clean.owl --output reports\reasoning\week3_500_clean_hermit_classified.owl
```

## Current inconsistency log

No local structural inconsistency was detected, and HermiT completed without reporting unsatisfiable classes. The cleaned 500-concept expansion has 0 URL-like definitions and 0 `needs_review` or `candidate` provenance flags in the metadata.
