# Weeks 1-3 Closeout and Manual Action Checklist

This document records the current completion state for the first three project weeks and separates repository-complete work from items that require a human meeting, screenshot, or optional local app action.

## Current status

Overall status: Weeks 1-3 are complete as a repository-side build and documentation checkpoint.

The only remaining manual requirement is the Teams-based mentor review for the 50 sampled gloss records if the report will claim that mentor review and inter-rater agreement have already happened.

## Week 1: Seed ontologies, tooling, and data sources

| Requirement | Status | Evidence | Manual or integration needed |
|---|---|---|---|
| Download OntoMathPRO 2.0, MaRDI MathModDB, OpenMath Content Dictionaries, and OntoMathEdu | Complete | `ontologies/raw/`, `reports/summaries/week1_source_status.md` | None |
| Install and configure Protege 5.x | Complete | Protege screenshots and opened OWL files | None |
| Install and configure ROBOT | Complete | `reports/robot_reports/`, `reports/summaries/*_measure.tsv` | None |
| Install and test Apache Jena Fuseki | Complete | `reports/sparql/week3_fuseki_benchmark_status.md` | None unless a fresh live screenshot is wanted |
| Install/configure OWL API/HermiT workflow | Complete by Week 3 | `reports/reasoning/week3_reasoner_report.md`, `reports/reasoning/week3_500_clean_hermit_classified.owl` | None |
| Run ROBOT report on seed ontologies | Complete for OWL/RDF seed files | `reports/robot_reports/ontomathpro_report.tsv`, `reports/robot_reports/mathmoddb_report.tsv`, `reports/robot_reports/ontomathedu_report.tsv` | None |
| Flag missing labels/definitions | Complete for ROBOT-readable seed files | `reports/robot_reports/` | None |
| Build 50-concept validation set | Complete | `validation/50_concept_validation_set.csv` has 50 rows | None |
| Draft Section 4.1 Data Sources | Complete | `paper/section_4_1_data_sources.md` | None |

Week 1 note: OpenMath content dictionaries are preserved as XML source files under `ontologies/raw/openmath-cds/`. The project uses OpenMath as a provenance/source layer, but there is no separate full OpenMath XML-to-RDF conversion artifact for every content dictionary. If the professor asks for literal full XML-to-RDF conversion, that is the only extra historical integration step.

## Week 2: Merge, canonicalization, provenance, and 50-concept validation

| Requirement | Status | Evidence | Manual or integration needed |
|---|---|---|---|
| Document IRI canonicalization rules | Complete | `reports/summaries/week2_iri_canonicalization_rules.md` | None |
| Create cross-ontology synonym mapping table | Complete | `validation/week2_cross_ontology_mapping_table.csv` has 50 rows | None |
| Implement ROBOT-based merge | Complete | `ontologies/merged/math_accessibility_kg_seed.ttl`, `ontologies/merged/math_accessibility_kg_seed.owl`, `reports/robot_reports/week2_seed_report.tsv` | None |
| Add provenance annotations | Complete | `ontologies/merged/math_accessibility_kg_seed.owl`, `validation/week2_50_concept_ontology_audit.csv` | None |
| Deduplicate and log merge decisions | Complete with documented limitations | `validation/week2_cross_ontology_mapping_table.csv`, `reports/summaries/week2_mapping_status.md` | None |
| Build three-branch OWL 2 DL hierarchy | Complete | `mathkg:MathObject`, `mathkg:MathOperation`, and `mathkg:MathRelation` in `ontologies/merged/math_accessibility_kg_seed.owl` | None |
| Validate against 50-concept set | Complete | `validation/week2_50_concept_ontology_audit.csv` has 50 rows | None |

Week 2 note: Broad `owl:equivalentClass` assertions were intentionally limited to avoid unsafe equivalence claims where exact cross-source identity was not verified. This is documented as a research-quality limitation, not an unfinished file.

## Week 3: 500-concept enrichment, reasoning, SPARQL, glosses, and paper sections

| Requirement | Status | Evidence | Manual or integration needed |
|---|---|---|---|
| Apply kind/role distinction to all 500 target concepts | Complete | `validation/week3_500_concept_metadata.csv` has 500 rows: 487 kind, 13 role | None |
| Add full annotation layer to all 500 concepts | Complete | `validation/week3_500_concept_metadata.csv`, `reports/reasoning/math_accessibility_kg_week3_clean.ttl` | None |
| Run HermiT OWL 2 DL reasoner | Complete | `reports/reasoning/week3_reasoner_report.md`, `reports/reasoning/week3_500_clean_hermit_classified.owl` | None |
| Document inconsistency handling | Complete | `reports/reasoning/week3_reasoner_report.md` records no unsatisfiable classes in the cleaned layer | None |
| Build 10-query SPARQL benchmark suite | Complete | `queries/`, `reports/sparql/week3_benchmark_queries.rq` | None |
| Run Fuseki queries and record response times | Complete | `reports/sparql/week3_fuseki_query_results.csv`, `reports/sparql/week3_fuseki_query_results_mathkg500.csv` | None unless fresh live results are desired |
| Draft Section 4.2 Ontology Design | Complete | `paper/section_4_2_ontology_design.md` | None |
| Draft Section 4.3 Kind/Role Classification | Complete | `paper/section_4_3_kind_role_classification.md` | None |
| Implement 8 template-based gloss rewrite templates | Complete | `gloss/week3_rewrite_templates.json` has 8 templates | None |
| Generate four surface forms for 500 concepts | Complete | `gloss/week3_gloss_dictionary.csv`, `gloss/week3_gloss_dictionary.json` have 500 rows | None |
| Implement arXiv corpus pipeline for 200 math.* records | Complete with local fallback | `reports/corpus/week3_arxiv_math_corpus_metadata.csv` has 200 records | None unless strict spaCy execution is required |
| Extract usage-context glosses for top 100 symbols | Complete | `reports/corpus/week3_usage_context_glosses.csv`, `reports/corpus/week3_top_100_symbols.csv` has 100 rows | None |
| Merge gloss metadata record fields | Complete | `gloss/week3_gloss_dictionary.csv`, `gloss/week3_gloss_dictionary.json` | None |
| Joint mentor review and inter-rater agreement | Prepared, pending Teams meeting | `validation/week3_teams_mentor_review_record.md`, `validation/week3_inter_rater_agreement_status.md` | Required only after the Teams meeting |
| Draft Section 4.4 Semantic Gloss Dictionary | Complete | `paper/section_4_4_semantic_gloss_dictionary.md` | Update with final Teams review numbers after the meeting |

Week 3 note: The corpus pipeline records that the local environment did not include spaCy, so the run used a deterministic MathEntRuler-compatible lexical rule set over arXiv metadata and abstracts. If a professor strictly requires a spaCy execution log, rerun that part in an environment with spaCy installed; otherwise the pipeline artifacts and fallback note are already documented.

## Current verified counts

| Item | Count |
|---|---:|
| Raw source files preserved | 738 |
| OpenMath CD files preserved | 735 |
| Week 1 validation concepts | 50 |
| Week 2 mapping rows | 50 |
| Week 2 audit rows | 50 |
| Week 3 target concepts | 500 |
| Week 3 kind concepts | 487 |
| Week 3 role concepts | 13 |
| Week 3 gloss records | 500 |
| arXiv math.* records | 200 |
| Top-symbol rows | 100 |
| SPARQL query files | 10 |
| Fuseki benchmark result rows | 10 |
| Gloss rewrite templates | 8 |

## What Ricardo still needs to do manually

Required only for the human-review requirement:

1. Hold the Teams mentor review session.
2. Record the review outcome in `validation/week3_teams_mentor_review_record.md`.
3. Update `validation/week3_inter_rater_agreement_status.md` with the final agreement summary.
4. Add the final mentor-review numbers to `paper/section_4_4_semantic_gloss_dictionary.md`.

Optional evidence only:

1. Open `ontologies/merged/math_accessibility_kg_week3_clean_500.owl` in Protege and take a screenshot of the 500-concept hierarchy.
2. Open `ontologies/merged/math_accessibility_kg_seed.owl` in Protege and take a screenshot of the object-property hierarchy if the professor wants to see `MathRelation`.
3. Start Fuseki and rerun `/mathkg500` queries only if fresh live screenshots are needed. The recorded query evidence already exists.

## Bottom line

There are no additional app integrations required from Ricardo right now for Weeks 1-3, unless the professor asks for either fresh Fuseki screenshots, literal full OpenMath XML-to-RDF conversion, or a strict spaCy run rather than the documented local fallback.
