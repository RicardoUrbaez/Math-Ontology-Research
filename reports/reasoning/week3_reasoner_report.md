# Week 3 Reasoner Report

## Local reasoning status

HermiT reasoning was executed with ROBOT on the Week 3 500-concept expansion artifact after ROBOT became available locally. A fresh merged-ontology run was completed on 2026-07-10 against `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`.

## Structural checks completed

- Cleaned Week 3 TTL file: `reports/reasoning/math_accessibility_kg_week3_clean.ttl`
- Converted OWL file for reasoning: `reports/reasoning/math_accessibility_kg_week3_clean.owl`
- HermiT classified output: `reports/reasoning/week3_500_clean_hermit_classified.owl`
- Merged gloss TTL file: `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`
- Converted merged OWL file: `reports/reasoning/math_accessibility_kg_merged_gloss.owl`
- Merged HermiT classified output: `reports/reasoning/week3_merged_gloss_hermit_classified.owl`
- Merged ROBOT report: `reports/reasoning/week3_merged_gloss_hermit_report.tsv`
- Target concept classes generated: 500
- Kind concepts: 487
- Role concepts: 13
- OWL class declarations detected in TTL: 502
- Unsatisfiable classes detected in merged HermiT output: 0
- No disjointness axioms were introduced between KindConcept and RoleConcept, so the enrichment layer does not create local unsatisfiable classes from the kind/role distinction.
- Each generated concept has `rdfs:label`, `skos:definition`, `skos:altLabel`, `skos:example`, `dc:source`, `mathkg:kindRoleType`, and `mathkg:semanticType` annotations.
- URL-style source definitions were replaced with readable formal definitions; 0 URL-like definitions remain in the cleaned metadata.
- ROBOT metadata reporting on the cleaned 500 ontology found no violations.
- ROBOT metadata reporting on the merged gloss ontology found 10 warnings for missing IAO definitions on gloss-vocabulary terms. These warnings are schema-documentation issues, not logical inconsistencies or unsatisfiable classes.

## HermiT reproduction command

Run the following after installing ROBOT with HermiT support:

```powershell
java -jar C:\Robot\robot.jar convert --input reports\reasoning\math_accessibility_kg_week3_clean.ttl --input-format ttl --output reports\reasoning\math_accessibility_kg_week3_clean.owl
java -jar C:\Robot\robot.jar reason --reasoner HermiT --input reports\reasoning\math_accessibility_kg_week3_clean.owl --output reports\reasoning\week3_500_clean_hermit_classified.owl
java -jar C:\Robot\robot.jar convert --input ontologies\merged\math_accessibility_kg_merged_gloss.ttl --input-format ttl --output reports\reasoning\math_accessibility_kg_merged_gloss.owl
java -jar C:\Robot\robot.jar reason --reasoner HermiT --input reports\reasoning\math_accessibility_kg_merged_gloss.owl --output reports\reasoning\week3_merged_gloss_hermit_classified.owl
java -jar C:\Robot\robot.jar report --input reports\reasoning\week3_merged_gloss_hermit_classified.owl --output reports\reasoning\week3_merged_gloss_hermit_report.tsv
```

## Current inconsistency log

No local structural inconsistency was detected, and HermiT completed without reporting unsatisfiable classes. The merged HermiT classified output contains 0 classes asserted as subclasses of `owl:Nothing` and 0 classes equivalent to `owl:Nothing`, so no unsatisfiable classes required repair.

The cleaned 500-concept expansion has 0 URL-like definitions and 0 `needs_review` or `candidate` provenance flags in the metadata. The merged ROBOT report lists missing IAO definition warnings for gloss-vocabulary terms only: `GlossRecord`, `canonicalGloss`, `conciseForm`, `documentRoleForm`, `expertForm`, `glossForConcept`, `hasGlossRecord`, `pedagogicalForm`, `sourceProvenance`, and `sourceProvenanceNote`. These were documented as metadata warnings and left out of the inconsistency-resolution list because they do not make the ontology unsatisfiable.
