# MathOntoSpeak: Math Accessibility Knowledge Graph

MathOntoSpeak is a research prototype for making mathematical notation more accessible through a provenance-tagged knowledge graph and a speech-oriented rendering pipeline. The project merges mathematical ontology resources, enriches concepts with accessibility glosses, exposes the graph through SPARQL and FastAPI, and renders LaTeX expressions into multiple speech-ready perspectives.

The central modeling idea is that one mathematical concept node can support several formally distinct surface forms: concise, pedagogical, expert, and document-role. These are treated as different perspectives over the same knowledge graph node, rather than as unrelated text rewrites.

## Repository Contents

| Area | Key files |
|---|---|
| Merged ontology | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`, `.jsonld`, `.rdf` |
| Seed and Week 3 ontology files | `ontologies/merged/math_accessibility_kg_seed.owl`, `math_accessibility_kg_seed.ttl`, `math_accessibility_kg_week3.ttl`, `math_accessibility_kg_week3_clean_500.owl` |
| Gloss dictionary | `gloss/week3_gloss_dictionary.json`, `gloss/week3_gloss_dictionary.csv`, `gloss/week3_rewrite_templates.json` |
| TTS and LaTeX pipeline | `src/mathontospeak/`, `scripts/week4_tts_rendering.py`, `scripts/generate_study_audio.py` |
| SPARQL query library | `queries/01_list_all_concepts.rq` through `queries/10_hierarchy_traversal.rq`; additional API-oriented examples in `queries/11_*.rq` through `queries/15_*.rq` |
| FastAPI server | `api/main.py`, `api/services.py` |
| Evaluation package | `scripts/week6_evaluation_package.py`, `reports/evaluation/`, `figures/`, `paper/section_5_evaluation.md`, `paper/section_6_discussion.md` |
| Rapid pilot study | `scripts/run_rapid_pilot.py`, `scripts/finalize_rapid_pilot.py`, `study/rapid_pilot/rapid_pilot_results.xlsx` |

## Installation

Requirements:

- Python 3.11 or newer
- Java 17 or newer for Apache Jena Fuseki
- Optional: Apache Jena Fuseki 6.1.0 for live SPARQL benchmarking
- Optional: Azure Speech credentials for Azure TTS output

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the test suite:

```powershell
python -m pytest
```

## Core Artifacts

The publication-ready merged graph is available in three RDF serializations:

```text
ontologies/merged/math_accessibility_kg_merged_gloss.ttl
ontologies/merged/math_accessibility_kg_merged_gloss.jsonld
ontologies/merged/math_accessibility_kg_merged_gloss.rdf
```

The graph currently contains:

- 504 ontology classes
- 13 declared properties
- 13,986 RDF statements
- 500 provenance-tagged classes

The semantic gloss dictionary is available as:

```text
gloss/week3_gloss_dictionary.json
gloss/week3_gloss_dictionary.csv
```

Each gloss record includes a canonical gloss and four surface forms:

- `concise_form`
- `pedagogical_form`
- `expert_form`
- `document_role_form`

## Reproducing the Paper Results

### 1. Rebuild the merged ontology serializations

```powershell
python scripts/serialize_merged_ontology_gloss.py
```

Expected outputs:

```text
ontologies/merged/math_accessibility_kg_merged_gloss.ttl
ontologies/merged/math_accessibility_kg_merged_gloss.jsonld
```

### 2. Regenerate Week 6 evaluation tables, figures, and paper sections

If using the completed rapid-pilot workbook:

```powershell
python scripts/week6_evaluation_package.py --workbook study/rapid_pilot/rapid_pilot_results.xlsx
```

Expected outputs:

```text
reports/evaluation/week6_statistical_analysis_summary.md
reports/evaluation/week6_statistical_tests.csv
reports/evaluation/week6_thematic_analysis.csv
reports/evaluation/week6_system_evaluation_table.csv
reports/evaluation/week6_system_evaluation_table.md
figures/week6_figure_1_five_layer_architecture.png
figures/week6_figure_2_concept_graph_T_surface_forms.png
figures/week6_figure_3_sparql_benchmark_response_times.png
figures/week6_figure_4_user_study_comprehension_bar.png
paper/section_5_evaluation.md
paper/section_6_discussion.md
```

Current rapid-pilot results:

- Paired participants: 10
- Comprehension: MathOntoSpeak semantic TTS 43.3% vs notation-only TTS 35.0%
- Paired t-test: `t = 1.627`, `p = 0.138`
- Cohen's dz for comprehension: `0.514`
- NASA-TLX: MathOntoSpeak semantic TTS 64.2 vs notation-only TTS 61.7
- Wilcoxon signed-rank: `W = 19.000`, `p = 0.734`
- Main interview themes: semantic role clarity, notation-only cognitive load, pacing and domain familiarity

### 3. Regenerate the rapid-pilot workbook from captured sessions

The rapid-pilot runner saves responses to `study/rapid_pilot/responses.jsonl`. To rebuild the workbook and regenerate Week 6 results from those responses:

```powershell
python scripts/finalize_rapid_pilot.py
```

Expected outputs:

```text
study/rapid_pilot/rapid_pilot_results.xlsx
study/rapid_pilot/rapid_pilot_comprehension_scores.csv
study/rapid_pilot/rapid_pilot_nasa_tlx.csv
study/rapid_pilot/rapid_pilot_interview_coding.csv
```

### 4. Reproduce the SPARQL benchmark evidence

Start Fuseki:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_fuseki_mathkg.ps1
```

Load the cleaned graph if the dataset is empty:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\load_fuseki_mathkg.ps1
```

The benchmark query outputs used in the paper are stored at:

```text
reports/sparql/week3_fuseki_query_results_mathkg500.csv
```

The paper currently reports:

- 10 completed benchmark queries
- Mean response time: 52.359 ms
- Maximum response time: 170.884 ms

## Running the FastAPI Server

Start the API:

```powershell
python -m uvicorn api.main:app --reload
```

Default local URL:

```text
http://127.0.0.1:8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Semantic search:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/search?q=matrix&limit=5"
```

Cross-disciplinary discovery:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri "http://127.0.0.1:8000/api/discover" `
  -Body '{"seed_concept":"Matrix","target_domains":["calculus"],"limit":3}'
```

Concept recommendation:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri "http://127.0.0.1:8000/api/recommend" `
  -Body '{"latex":"S=\\sum_k a_k X_k","limit":3}'
```

LaTeX accessibility gloss:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri "http://127.0.0.1:8000/api/accessibility/latex-gloss" `
  -Body '{"latex":"x \\in \\mathbb{R}","audience":"concise"}'
```

If Fuseki is unavailable, the API still serves deterministic concept and gloss results from the local gloss dictionary.

## Running the LaTeX to Audio Pipeline

Mock backend, no credentials required:

```powershell
python scripts/week4_tts_rendering.py `
  --equations validation/week4_20_arxiv_equation_fixture.csv `
  --backend mock `
  --limit 20 `
  --out reports/audio/week4_tts
```

gTTS backend, requires network access:

```powershell
python scripts/week4_tts_rendering.py `
  --equations validation/week4_20_arxiv_equation_fixture.csv `
  --backend gtts `
  --limit 20 `
  --out reports/audio/week4_tts_gtts
```

Azure backend, requires environment variables:

```powershell
$env:AZURE_SPEECH_KEY = "YOUR_AZURE_SPEECH_KEY"
$env:AZURE_SPEECH_REGION = "YOUR_AZURE_REGION"
python scripts/week4_tts_rendering.py `
  --equations validation/week4_20_arxiv_equation_fixture.csv `
  --backend azure `
  --limit 3 `
  --out reports/audio/week4_tts_azure
```

Main generated audio evidence:

```text
reports/audio/week4_tts_gtts/
reports/audio/week4_tts_azure/
study/audio/notation_only/
study/audio/mathontospeak_semantic/
```

## Running the Rapid Pilot Collector

Start the local collector:

```powershell
python scripts/run_rapid_pilot.py
```

Open:

```text
http://127.0.0.1:8765
```

Each participant link collects:

- comprehension responses
- NASA-TLX ratings
- short interview responses
- counterbalanced notation-only and semantic TTS condition order

After sessions, finalize:

```powershell
python scripts/finalize_rapid_pilot.py
```

## SPARQL Query Library

The benchmark library is in `queries/`:

```text
01_list_all_concepts.rq
02_concepts_missing_definitions.rq
03_concepts_by_type.rq
04_kind_role_lookup.rq
05_provenance_trace.rq
06_relation_properties.rq
07_alt_labels_synonyms.rq
08_accessibility_notes.rq
09_provisional_mappings.rq
10_hierarchy_traversal.rq
```

Additional query examples support semantic search, cross-domain symbol discovery, gloss lookup, provenance lookup, and surface-form retrieval.

## Paper Figures

The paper figures are generated by `scripts/week6_evaluation_package.py`:

| Figure | File stem |
|---|---|
| Figure 1: five-layer architecture | `figures/week6_figure_1_five_layer_architecture` |
| Figure 2: `T` concept graph with four surface forms | `figures/week6_figure_2_concept_graph_T_surface_forms` |
| Figure 3: SPARQL benchmark response times | `figures/week6_figure_3_sparql_benchmark_response_times` |
| Figure 4: user study comprehension chart with error bars | `figures/week6_figure_4_user_study_comprehension_bar` |

PNG and SVG versions are included for each figure.

## Validation and Tests

Run all Python tests:

```powershell
python -m pytest
```

Useful validation artifacts:

```text
validation/week3_codex_two_pass_review_summary.md
validation/week3_codex_two_pass_gloss_review.csv
reports/reasoning/week3_reasoner_report.md
reports/w3c/w3c_rdf_validator_status_2026-07-10.md
reports/evaluation/week6_system_evaluation_table.md
```

## Licensing

Code in this repository is licensed under the Apache License 2.0. See `LICENSE`.

Project-generated ontology data, gloss dictionaries, validation tables, evaluation tables, paper figures, and documentation are licensed under Creative Commons Attribution 4.0 International. See `DATA_LICENSE.md`.

Third-party source ontologies and resources retain their original upstream licenses and attribution requirements. The repository notes source provenance in `notes/data_sources_notes.md`, `paper/section_4_1_data_sources.md`, and the ontology metadata.

## Citation and Attribution

If you use this repository, cite it as:

```text
Ricardo Urbaez. MathOntoSpeak: Math Accessibility Knowledge Graph. 2026.
```

For derived ontology data, attribute the MathOntoSpeak project and preserve attribution to the upstream mathematical ontology resources described in the project notes.
