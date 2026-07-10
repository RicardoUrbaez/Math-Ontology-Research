# Week 4 and Study Bullet QC Status

Date: 2026-07-10

## Verification Commands

Manual confirmation run:

```text
python -m compileall src scripts api
python -m pytest -q
22 passed, 1 warning
```

Codex repository checks:

```text
mock manifest: 20 rows, status ok, backend mock
gTTS manifest: 20 rows, status ok, backend gtts
Azure manifest: 3 rows, status ok, backend azure
gTTS MP3 files: 20
Azure WAV files: 3
RDF/XML triples: 13,986
Turtle triples: 13,986
JSON-LD triples: 13,986
Week 4 arXiv equation fixture rows: 20
FastAPI routes present: /api/search, /api/discover, /api/recommend, /api/accessibility/latex-gloss
GitHub branch: main matches origin/main
```

## Bullet-by-Bullet Status

| Requirement | Status | Evidence | Manual action needed |
|---|---|---|---|
| Implement four-surface-form generator from gloss metadata record | Complete | `gloss/week3_gloss_dictionary.json`; `src/mathontospeak/surface_forms.py`; `scripts/week4_tts_rendering.py`; `paper/section_4_5_tts_rendering_engine.md` | None |
| Add SSML prosodic markup layer tuned for mathematical content | Complete | `src/mathontospeak/ssml_builder.py`; `reports/summaries/week4_tts_rendering_status.md`; SSML files under `reports/audio/week4_tts*/equation_ssml/` | None |
| Integrate gTTS backend | Complete and live-tested | 20 MP3 files under `reports/audio/week4_tts_gtts/equation_gtts/`; manifest `reports/audio/week4_tts_gtts/week4_latex_audio_gtts_manifest.json` | None |
| Integrate Azure TTS backend | Complete and live-tested | 3 WAV files under `reports/audio/week4_tts_azure/equation_azure/`; manifest `reports/audio/week4_tts_azure/week4_latex_audio_azure_manifest.json`; status file `reports/audio/week4_tts_azure/azure_tts_live_test_status_2026-07-10.md` | Key 1 was regenerated after exposure; no further action unless running Azure again |
| Build LaTeX to audio pipeline | Complete | `scripts/week4_tts_rendering.py`; `src/mathontospeak/latex_parser.py`; `src/mathontospeak/concept_lookup.py`; `src/mathontospeak/pipeline.py` | None |
| Use pylatexenc token parser | Complete / implemented with MVP token stream | `pylatexenc` is in requirements; output JSON records note parsing availability; parser code in `src/mathontospeak/latex_parser.py` and `scripts/week4_tts_rendering.py` | None for current MVP; parser quality can be improved later |
| Symbol-to-concept IRI lookup | Complete | `src/mathontospeak/concept_lookup.py`; resolved concept data in output JSON and manifests | None |
| Gloss metadata retrieval | Complete | `src/mathontospeak/gloss_record.py`; `gloss/week3_gloss_dictionary.json` | None |
| SSML assembly | Complete | `src/mathontospeak/ssml_builder.py`; generated SSML files | None |
| Audio synthesis | Complete | mock JSON/text, gTTS MP3, Azure WAV evidence | None |
| Test on 20 real arXiv equations end-to-end | Complete | `validation/week4_20_arxiv_equation_fixture.csv`; 20-row mock and gTTS manifests; 20 gTTS MP3 files | None |
| Serialize merged ontology + gloss dictionary as Turtle | Complete | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`; local parse count 13,986 triples | None |
| Serialize as JSON-LD | Complete | `ontologies/merged/math_accessibility_kg_merged_gloss.jsonld`; local parse count 13,986 triples | None |
| Validate with W3C RDF Validator | Complete | `reports/w3c/w3c_rdf_validator_status_2026-07-10.md`; W3C returned "Your RDF document validated successfully" on 500-triple sample; full graph parses locally | None |
| Push to public GitHub repository | Complete | `https://github.com/RicardoUrbaez/Math-Ontology-Research`; latest pushed commit `2968602` | None |
| Deploy SPARQL endpoint on Apache Jena Fuseki | Complete locally | `scripts/start_fuseki_mathkg.ps1`; `scripts/load_fuseki_mathkg.ps1`; Fuseki manual UI check returned 487 kind and 13 role concepts on `/mathkg500` | Manual only if demonstrating live: start Fuseki window and keep it open |
| Implement FastAPI semantic search endpoint | Complete | `api/main.py`; route `/api/search`; tests in `tests/test_api_routes.py` | Manual only if demonstrating live: start Uvicorn |
| Implement cross-disciplinary discovery endpoint | Complete | `api/main.py`; route `/api/discover`; tests and Swagger/manual evidence | Manual only if demonstrating live |
| Implement concept recommender endpoint | Complete | `api/main.py`; route `/api/recommend`; tests and Swagger/manual evidence | Manual only if demonstrating live |
| Implement accessibility endpoint, LaTeX to JSON gloss | Complete | `api/main.py`; route `/api/accessibility/latex-gloss`; output evidence under `outputs/json_glosses/`, `outputs/ssml/`, and `outputs/audio/` | Manual only if demonstrating live |
| Draft paper Section 4.5 | Complete draft | `paper/section_4_5_tts_rendering_engine.md` | Human edit/polish if desired before final submission |
| Draft paper Section 4.6 | Complete draft | `paper/section_4_6_lod_publication_and_apis.md` | Human edit/polish if desired before final submission |
| API schema documentation and example queries | Complete | `reports/api_schema_examples.md`; `queries/11_semantic_search_example.rq` through `queries/15_surface_forms_by_concept.rq`; `paper/section_4_6_lod_publication_and_apis.md` | None |

## Study Block Status

| Requirement | Status | Evidence | Manual action needed |
|---|---|---|---|
| Prepare 10 mathematical expressions across algebra, calculus, and linear algebra | Complete | `study/stimuli/study_stimuli.csv`; counts: algebra 4, calculus 3, linear_algebra 3 | Professor review/edit if desired |
| Generate notation-only TTS audio condition | Complete | 10 MP3 files under `study/audio/notation_only/mp3/`; manifest `study/audio/notation_only/notation_only_manifest.json` status `ok` | None before demo |
| Generate MathOntoSpeak semantic TTS audio condition | Complete | 10 MP3 files under `study/audio/mathontospeak_semantic/equation_gtts/`; 10 SSML files under `study/audio/mathontospeak_semantic/equation_ssml/`; manifest status `ok` | None before demo |
| Create 4-question MCQ comprehension test per expression | Complete | `study/instruments/mcq_comprehension_test.csv`; 40 items, 4 per expression | Professor review/edit if desired |
| NASA-TLX after each condition | Complete template | `study/instruments/nasa_tlx_form.md`; workbook sheet `NASA TLX` in `study/analysis/mathontospeak_study_analysis_template.xlsx` | Fill after each condition during real sessions |
| Counterbalance condition order | Complete template | `study/protocol/counterbalance_schedule.csv`; AB/BA schedule for 10 planned participants | Assign actual participant IDs when recruiting |
| 5-minute post-study interview | Complete guide | `study/instruments/post_study_interview_guide.md`; workbook sheet `Interview Coding` | Conduct after each participant session |
| Administer within-subjects study | Manual / not run | Protocol: `study/protocol/study_protocol.md`; materials ready | Run participants only after professor/approval/consent decision |
| Transcribe and code interviews | Manual / not run | Coding sheet ready in `study/analysis/mathontospeak_study_analysis_template.xlsx` | Transcribe and code after sessions |
| Enter comprehension and NASA-TLX scores into analysis spreadsheet | Ready for manual data entry | `study/analysis/mathontospeak_study_analysis_template.xlsx`; formulas export with zero formula errors | Enter real participant scores after sessions |

## Study Package Verification

```text
stimuli_total: 10
algebra_stimuli: 4
calculus_stimuli: 3
linear_algebra_stimuli: 3
mcq_items: 40
min_questions_per_stimulus: 4
max_questions_per_stimulus: 4
notation_manifest_items: 10
notation_statuses: ['ok']
semantic_manifest_items: 10
semantic_statuses: ['ok']
notation_mp3_files: 10
semantic_mp3_files: 10
semantic_ssml_files: 10
analysis_workbook_exists: True
workbook_formula_error_scan: 0 matches
python -m compileall src scripts api: passed
python -m pytest -q: 22 passed, 1 warning
```

## Manual Checklist From Here

1. If demonstrating Week 4 live, start Fuseki and Uvicorn, then open Swagger/Fuseki UI.
2. Do not paste or store Azure keys in project files. Regenerate keys if exposed.
3. Before collecting participant data, confirm with the professor whether this is class demonstration work or human-subjects research requiring approval/consent language.
4. For the study block, the remaining work is human-only: professor review/approval, participant sessions, score entry, NASA-TLX entry, interview transcription, and coding.
