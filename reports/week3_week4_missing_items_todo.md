# Week 3-4 Missing Items TODO Plan

## Priority 1

### Update paper Section 4.2 with current reasoner evidence

- File to modify: `paper/section_4_2_ontology_design.md`
- Why it matters: the current draft says HermiT/ROBOT were not installed, but the project now has successful HermiT evidence.
- Exact next command or prompt idea: "Update Section 4.2 to cite `reports/reasoning/week3_reasoner_report.md`, `week3_merged_gloss_hermit_classified.owl`, and the 0 unsatisfiable class result."

### Update paper Section 4.3 with validation/reasoner evidence

- File to modify: `paper/section_4_3_kind_role_classification.md`
- Why it matters: the draft explains the classification but does not yet connect it to HermiT validation or the current `mathkg:kindRoleType` storage property.
- Exact next command or prompt idea: "Revise Section 4.3 with the 487 kind / 13 role count, `mathkg:kindRoleType`, and the HermiT 0-unsatisfiable-class result."

### Add a Week 3 hierarchy traversal query

- File to create or modify: `queries/10_hierarchy_traversal.rq` or `queries/16_week3_kind_role_hierarchy_traversal.rq`
- Why it matters: the existing hierarchy benchmark query targets the older `MathObject`/`MathOperation` branches and returns 0 rows on the cleaned 500 dataset.
- Exact next command or prompt idea: "Create a SPARQL hierarchy query that traverses from `mathkg:KindConcept` and `mathkg:RoleConcept`, then rerun the Fuseki benchmark."

### Build the real spaCy/MathEntRuler corpus pipeline

- Files to create or modify: `requirements.txt`, `scripts/week3_build_artifacts.py`, optionally `src/mathontospeak/corpus_ner.py`
- Why it matters: current corpus extraction is a deterministic lexical MVP over titles and abstracts, not a spaCy/full-paper NER pipeline.
- Exact next command or prompt idea: "Implement a spaCy pipeline with a custom MathEntRuler component, using the 200 arXiv metadata rows and producing symbol/context extraction outputs."

### Complete the mentor review session record

- Files to modify: `validation/week3_teams_mentor_review_record.md`, `validation/week3_gloss_mentor_review_sample.csv`
- Why it matters: mentor review and inter-rater agreement cannot be claimed until real human scores are entered.
- Exact next command or prompt idea: "After the Teams review, enter Reviewer A/B scores for accuracy, naturalness, and cross-domain correctness for the 50 sampled gloss records."

## Priority 2

### Create top-100 symbol context records

- File to create: `reports/corpus/week3_top_100_symbol_contexts.csv`
- Why it matters: the project has top-100 symbol frequencies and separate concept contexts, but not a joined context record for each top symbol.
- Exact next command or prompt idea: "Merge `week3_top_100_symbols.csv` with arXiv title/abstract snippets into a top-symbol usage-context table."

### Compute inter-rater agreement after scoring

- File to create or modify: `validation/week3_inter_rater_agreement_status.md`
- Why it matters: agreement is currently pending and must not be fabricated.
- Exact next command or prompt idea: "Once two reviewers score the sample, compute agreement summaries or Cohen's kappa and write the result with methodology."

### Improve template gloss quality

- Files to modify: `gloss/week3_rewrite_templates.json`, `gloss/week3_gloss_dictionary.json`
- Why it matters: the 500 gloss records are structurally complete, but several template outputs are generic and need naturalness review.
- Exact next command or prompt idea: "Use mentor feedback to revise the eight templates and regenerate the 500 gloss records."

### Rerun real Fuseki benchmark after query updates

- Files to update: `reports/sparql/week3_fuseki_query_results_mathkg500.csv`, `reports/sparql/week3_fuseki_benchmark_status.md`
- Why it matters: benchmark evidence exists, but it should be refreshed after adding the Week 3 hierarchy traversal query.
- Exact next command or prompt idea: "Start Fuseki with `scripts/start_fuseki_mathkg.ps1`, load the cleaned dataset if needed, then rerun the query timing script or manual benchmark."

## Priority 3

### Add charts or tables for professor presentation

- Files to create: `reports/figures/` or a paper appendix table
- Why it matters: counts such as 500 concepts, 487/13 kind-role split, 1,031 corpus contexts, and benchmark response times are easier to present visually.
- Exact next command or prompt idea: "Generate a small chart/table package for kind-role counts, semantic-type distribution, and Fuseki response times."

### Prepare Protege/Fuseki screenshots

- Files to create: `reports/protege_screenshots/` or `reports/sparql/screenshots/`
- Why it matters: screenshots make the ontology and SPARQL endpoint easier to defend in a meeting.
- Exact next command or prompt idea: "Capture Protege class hierarchy screenshots and Fuseki query-result screenshots for the 500-concept dataset."

### Clean up project documentation

- Files to modify: `README.md`, `docs/fuseki_setup.md`, `docs/week4_setup.md`
- Why it matters: several artifacts are complete, but the docs should clearly distinguish structural completion, MVP corpus extraction, and pending human review.
- Exact next command or prompt idea: "Update the README with a short status matrix and links to the audit, TODO plan, reasoner report, benchmark CSV, and gloss dictionary."

### GitHub cleanup

- Files to review: generated reports, logs, audio outputs, and large artifacts
- Why it matters: the repo has many generated outputs; a clean `.gitignore` and artifact policy will make the project easier to share.
- Exact next command or prompt idea: "Review `git status`, decide which generated artifacts should be tracked, and update `.gitignore` for cache/log/audio outputs."
