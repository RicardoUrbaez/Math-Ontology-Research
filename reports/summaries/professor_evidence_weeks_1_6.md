# Professor Evidence Packet: Weeks 1-6

This packet maps the Summer 2026 research plan to the repository evidence for Weeks 1 through 6. It is intended as a quick guide for what to show a professor or reviewer.

Project root: `C:\Users\Ricardo\Documents\Math-Ontology-Research`

Research plan source: `C:\Users\Ricardo\Downloads\Research Plan_Ricardo_NK (2).pdf`

## Executive Summary

The repository contains evidence for the full Week 1-6 research arc:

- Week 1: seed resources, tooling, ROBOT reports, 50-concept validation set, and Section 4.1 draft.
- Week 2: IRI rules, cross-ontology mapping table, seed merge, provenance, hierarchy, and 50-concept validation coverage.
- Week 3: 500-concept kind/role and annotation layer, HermiT reasoning, SPARQL benchmarks, 500 gloss records, corpus evidence, and Sections 4.2-4.4.
- Week 4: four-surface-form TTS rendering, LaTeX-to-audio pipeline, RDF/TTL/JSON-LD exports, W3C/local validation, FastAPI endpoints, and Sections 4.5-4.6.
- Week 5: study package, stimuli, MCQ/NASA-TLX/interview instruments, counterbalancing, notation-only audio, semantic TTS audio, and rapid-pilot response collection.
- Week 6: statistical analysis, system evaluation table, paper figures, Sections 5-6, and a reproducible Week 6 evaluation package.

## Week 1: Seed Ontologies, Tooling, and Data Sources

Research-plan goal: collect seed ontologies, install core tools, run ROBOT reports, build a 50-concept validation set, and draft Section 4.1.

Evidence to show:

- Source/tooling status: `reports/summaries/week1_completion_checklist.md`
- Data source notes: `notes/data_sources_notes.md`
- OntoMathPRO ROBOT output: `reports/summaries/ontomathpro_measure.tsv`, `reports/robot_reports/ontomathpro_report.tsv`
- MathModDB ROBOT output: `reports/summaries/mathmoddb_measure.tsv`, `reports/robot_reports/mathmoddb_report.tsv`
- OntoMathEdu repaired ROBOT output: `reports/summaries/ontomathedu_measure.tsv`, `reports/robot_reports/ontomathedu_report.tsv`
- 50-concept validation set: `validation/50_concept_validation_set.csv`
- Validation status: `validation/validation_set_status.md`
- Paper Section 4.1 draft: `paper/section_4_1_data_sources.md`
- Raw/converted ontology folders: `ontologies/raw/`, `ontologies/converted/`

Count proof:

- `validation/50_concept_validation_set.csv`: 50 rows

## Week 2: Merge Rules, Provenance, and Seed Ontology

Research-plan goal: define IRI canonicalization, map cross-ontology synonyms, create the merged seed ontology, add provenance, log merge decisions, build the hierarchy, and validate against the 50-concept set.

Evidence to show:

- Week 2 checklist: `reports/summaries/week2_completion_checklist.md`
- IRI canonicalization rules: `reports/summaries/week2_iri_canonicalization_rules.md`
- Cross-ontology mapping table: `validation/week2_cross_ontology_mapping_table.csv`
- Mapping status: `reports/summaries/week2_mapping_status.md`
- Merge decision/conflict log: `reports/conflicts/week2_merge_decision_log.csv`
- Provenance mapping summary: `reports/summaries/week2_provenance_mapping_summary.md`
- Seed ontology Turtle: `ontologies/merged/math_accessibility_kg_seed.ttl`
- Seed ontology OWL: `ontologies/merged/math_accessibility_kg_seed.owl`
- ROBOT seed report: `reports/robot_reports/week2_seed_report.tsv`
- Final Week 2 closeout: `reports/summaries/week2_final_closeout.md`

Count proof:

- `validation/week2_cross_ontology_mapping_table.csv`: 50 rows

## Week 3: 500 Concepts, Reasoning, SPARQL, Gloss Dictionary

Research-plan goal: apply kind/role distinction to 500 target concepts, add the full annotation layer, run HermiT, build SPARQL benchmark queries, generate gloss records, run corpus extraction, and draft Sections 4.2-4.4.

Evidence to show:

- Week 3 checklist: `reports/summaries/week3_completion_checklist.md`
- 500-concept metadata: `validation/week3_500_concept_metadata.csv`
- Clean Week 3 TTL: `reports/reasoning/math_accessibility_kg_week3_clean.ttl`
- Merged Week 3 TTL: `ontologies/merged/math_accessibility_kg_week3.ttl`
- HermiT report: `reports/reasoning/week3_reasoner_report.md`
- HermiT classified outputs: `reports/reasoning/week3_500_clean_hermit_classified.owl`, `reports/reasoning/week3_merged_gloss_hermit_classified.owl`
- SPARQL benchmark query suite: `reports/sparql/week3_benchmark_queries.rq`
- Fuseki benchmark outputs: `reports/sparql/week3_fuseki_query_results.csv`, `reports/sparql/week3_fuseki_query_results_mathkg500.csv`
- SPARQL benchmark status: `reports/sparql/week3_fuseki_benchmark_status.md`
- Rewrite templates: `gloss/week3_rewrite_templates.json`
- 500-record gloss dictionary: `gloss/week3_gloss_dictionary.json`, `gloss/week3_gloss_dictionary.csv`
- Corpus metadata and usage contexts: `reports/corpus/week3_arxiv_math_corpus_metadata.csv`, `reports/corpus/week3_usage_context_glosses.csv`, `reports/corpus/week3_top_100_symbols.csv`
- Corpus pipeline status: `reports/corpus/week3_corpus_pipeline_status.md`
- Paper Sections 4.2-4.4: `paper/section_4_2_ontology_design.md`, `paper/section_4_3_kind_role_classification.md`, `paper/section_4_4_semantic_gloss_dictionary.md`

Count/result proof:

- `validation/week3_500_concept_metadata.csv`: 500 rows
- Kind concepts: 487
- Role concepts: 13
- `gloss/week3_gloss_dictionary.json`: 500 records
- `reports/sparql/week3_fuseki_query_results_mathkg500.csv`: 10 benchmark rows
- HermiT unsatisfiable classes: 0, documented in `reports/reasoning/week3_reasoner_report.md`

## Week 4: TTS Rendering, RDF Exports, APIs

Research-plan goal: implement four-surface-form rendering, LaTeX-to-audio, serialize the ontology/gloss dictionary, validate RDF, deploy/query with Fuseki/FastAPI, and draft Sections 4.5-4.6.

Evidence to show:

- Week 4 TTS status: `reports/summaries/week4_tts_rendering_status.md`
- TTS/API report: `reports/week4_tts_api_report.md`
- Week 4 setup: `docs/week4_setup.md`
- TTS pipeline script: `scripts/week4_tts_rendering.py`
- TTS source modules: `src/mathontospeak/`
- 20-equation fixture: `validation/week4_20_arxiv_equation_fixture.csv`
- Mock TTS outputs: `reports/audio/week4_tts/`
- gTTS outputs: `reports/audio/week4_tts_gtts/`
- Azure live sample outputs: `reports/audio/week4_tts_azure/`
- RDF/Turtle/JSON-LD exports: `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`, `ontologies/merged/math_accessibility_kg_merged_gloss.rdf`, `ontologies/merged/math_accessibility_kg_merged_gloss.jsonld`
- W3C/local RDF validation: `reports/w3c/w3c_rdf_validator_status_2026-07-10.md`
- FastAPI app: `api/main.py`, `api/services.py`
- API schema examples: `reports/api_schema_examples.md`
- Fuseki setup: `docs/fuseki_setup.md`
- Paper Sections 4.5-4.6: `paper/section_4_5_tts_rendering_engine.md`, `paper/section_4_6_lod_publication_and_apis.md`

Count/result proof:

- `validation/week4_20_arxiv_equation_fixture.csv`: 20 rows
- Week 4 gTTS equation MP3 files: 20
- RDF full exports validated locally: 13,986 triples in RDF/XML, Turtle, and JSON-LD
- W3C reduced sample validated successfully: 500 triples

## Week 5: Study Materials and Rapid Pilot Collection

Research-plan goal: prepare study stimuli, generate condition audio, build comprehension/NASA-TLX/interview instruments, counterbalance conditions, and collect/enter study data.

Evidence to show:

- Study package README: `study/README.md`
- Study stimuli: `study/stimuli/study_stimuli.csv`, `study/stimuli/study_stimuli_equations.csv`
- MCQ comprehension test: `study/instruments/mcq_comprehension_test.csv`
- NASA-TLX form: `study/instruments/nasa_tlx_form.md`
- Interview guide: `study/instruments/post_study_interview_guide.md`
- Study protocol: `study/protocol/study_protocol.md`
- Manual runbook: `study/protocol/manual_study_runbook.md`
- Counterbalance schedule: `study/protocol/counterbalance_schedule.csv`
- Notation-only study audio: `study/audio/notation_only/`
- MathOntoSpeak semantic study audio: `study/audio/mathontospeak_semantic/`
- Rapid-pilot collector: `scripts/run_rapid_pilot.py`
- Rapid-pilot finalizer: `scripts/finalize_rapid_pilot.py`
- Captured rapid-pilot responses: `study/rapid_pilot/responses.jsonl`
- Rapid-pilot workbook: `study/rapid_pilot/rapid_pilot_results.xlsx`
- Rapid-pilot CSV exports: `study/rapid_pilot/rapid_pilot_comprehension_scores.csv`, `study/rapid_pilot/rapid_pilot_nasa_tlx.csv`, `study/rapid_pilot/rapid_pilot_interview_coding.csv`

Count proof:

- `study/stimuli/study_stimuli.csv`: 10 expressions
- `study/instruments/mcq_comprehension_test.csv`: 40 MCQ rows
- `study/audio/notation_only/mp3/`: 10 MP3 files
- `study/audio/mathontospeak_semantic/equation_gtts/`: 10 MP3 files
- `study/rapid_pilot/rapid_pilot_comprehension_scores.csv`: 240 rows
- `study/rapid_pilot/rapid_pilot_nasa_tlx.csv`: 20 rows
- `study/rapid_pilot/rapid_pilot_interview_coding.csv`: 10 rows

## Week 6: Evaluation, Figures, and Paper Sections

Research-plan goal: run statistical analysis, compile the full system evaluation table, produce all figures, and write Sections 5-6 around the multi-perspective KG contribution.

Evidence to show:

- Week 6 evidence status: `reports/evaluation/week6_evidence_package_status.md`
- Statistical summary: `reports/evaluation/week6_statistical_analysis_summary.md`
- Statistical tests CSV: `reports/evaluation/week6_statistical_tests.csv`
- Thematic analysis: `reports/evaluation/week6_thematic_analysis.csv`
- System evaluation table: `reports/evaluation/week6_system_evaluation_table.md`, `reports/evaluation/week6_system_evaluation_table.csv`
- TTS audio quality/artifact QC: `reports/evaluation/week6_tts_audio_quality_qc.csv`
- Paper Section 5: `paper/section_5_evaluation.md`
- Paper Section 6: `paper/section_6_discussion.md`
- Week 6 generation script: `scripts/week6_evaluation_package.py`
- Figure 1: `figures/week6_figure_1_five_layer_architecture.png`, `.svg`
- Figure 2: `figures/week6_figure_2_concept_graph_T_surface_forms.png`, `.svg`
- Figure 3: `figures/week6_figure_3_sparql_benchmark_response_times.png`, `.svg`
- Figure 4: `figures/week6_figure_4_user_study_comprehension_bar.png`, `.svg`
- Optional Figure 5: `figures/week6_figure_5_tools_software_flow.png`, `.svg`

Count/result proof:

- Week 6 figure PNG files: 5
- Week 6 figure SVG files: 5
- System evaluation: 504 ontology classes, 13 declared properties, 13,986 RDF statements, 500 provenance-tagged classes
- SPARQL benchmark: 10 completed queries, mean response time 52.359 ms, max response time 170.884 ms
- Gloss agreement: overall Cohen kappa 0.93
- TTS artifact QC: 4/4 audio sets passed
- Comprehension rapid-pilot analysis: semantic TTS 43.3% vs notation-only TTS 35.0%; paired t-test `t = 1.627`, `p = 0.138`, Cohen's dz `0.514`
- NASA-TLX rapid-pilot analysis: semantic TTS 64.2 vs notation-only TTS 61.7; Wilcoxon `W = 19.000`, `p = 0.734`
- Thematic analysis: 3 themes: semantic role clarity, notation-only cognitive load, pacing and domain familiarity

## Repository and Reproducibility Proof

Evidence to show:

- Reviewer-facing README: `README.md`
- Code license: `LICENSE`
- Data/documentation license: `DATA_LICENSE.md`
- GitHub remote: `https://github.com/RicardoUrbaez/Math-Ontology-Research.git`
- Published package commit: `e3109b5 Publish MathOntoSpeak research package`
- Latest local commit at time of this evidence packet: `3b1e60c Add grouped Protege ontology view`
- Reproduction commands are documented in `README.md`, including:
  - `python -m pytest`
  - `python scripts/serialize_merged_ontology_gloss.py`
  - `python scripts/week6_evaluation_package.py --workbook study/rapid_pilot/rapid_pilot_results.xlsx`
  - `python scripts/finalize_rapid_pilot.py`
  - `python -m uvicorn api.main:app --reload`

## Best Files to Open During a Professor Meeting

Open these first:

1. `README.md`
2. `reports/summaries/professor_evidence_weeks_1_6.md`
3. `reports/evaluation/week6_system_evaluation_table.md`
4. `reports/evaluation/week6_statistical_analysis_summary.md`
5. `paper/section_5_evaluation.md`
6. `paper/section_6_discussion.md`
7. `figures/week6_figure_1_five_layer_architecture.png`
8. `figures/week6_figure_2_concept_graph_T_surface_forms.png`
9. `figures/week6_figure_3_sparql_benchmark_response_times.png`
10. `figures/week6_figure_4_user_study_comprehension_bar.png`

## Short Verbal Summary

The project now has a complete evidence trail from ontology acquisition and merging through a 500-concept accessibility knowledge graph, HermiT reasoning, SPARQL benchmarks, a four-surface-form gloss dictionary, LaTeX-to-speech rendering, APIs, study materials, rapid-pilot data, Week 6 statistics, figures, and paper sections. The key contribution is that a single mathematical concept node can support multiple speech-facing perspectives - concise, pedagogical, expert, and document-role - while remaining tied to provenance-tagged KG metadata.
