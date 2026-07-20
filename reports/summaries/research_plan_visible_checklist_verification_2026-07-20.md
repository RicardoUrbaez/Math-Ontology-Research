# Research Plan Visible Checklist Verification

Date checked: 2026-07-20

Scope: verifies the visible June 9-July 22 research-plan bullets shown in the meeting screenshot. The final two bullets, LOV/BioPortal registration and the 5-slide Scholars Academy presentation, were intentionally excluded from this verification and were not completed in this pass.

## Verified Complete

| Research-plan item | Status | Evidence |
| --- | --- | --- |
| Implement four-surface-form generator from gloss metadata record | Complete | `src/mathontospeak/surface_forms.py`; `gloss/week3_gloss_dictionary.json`; `paper/section_4_5_tts_rendering_engine.md` |
| Add SSML prosodic markup for math content | Complete | `src/mathontospeak/ssml_builder.py`; SSML outputs under `reports/audio/week4_tts*/equation_ssml/` |
| Integrate Azure TTS and gTTS backends | Complete | `src/mathontospeak/tts_backends.py`; 20 gTTS MP3 files under `reports/audio/week4_tts_gtts/equation_gtts/`; 3 Azure WAV files under `reports/audio/week4_tts_azure/equation_azure/` |
| Build LaTeX-to-audio pipeline and test on 20 real arXiv equations | Complete | `scripts/week4_tts_rendering.py`; `validation/week4_20_arxiv_equation_fixture.csv` has 20 rows; `reports/tts_pipeline_test_results.md` |
| Serialize merged ontology and gloss dictionary as Turtle and JSON-LD | Complete | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`; `ontologies/merged/math_accessibility_kg_merged_gloss.jsonld` |
| Validate RDF and publish to GitHub | Complete locally and ready for push in this pass | `reports/w3c/w3c_rdf_validator_status_2026-07-10.md`; repository remote is `https://github.com/RicardoUrbaez/Math-Ontology-Research.git` |
| Deploy/query SPARQL endpoint on Apache Jena Fuseki | Complete as local Fuseki evidence | `docs/fuseki_setup.md`; `reports/sparql/week3_fuseki_benchmark_status.md`; `reports/sparql/week3_fuseki_query_results_mathkg500.csv` |
| Implement four FastAPI endpoints | Complete | `api/main.py`; `api/services.py`; `reports/api_schema_examples.md` |
| Draft Sections 4.5 and 4.6 | Complete | `paper/section_4_5_tts_rendering_engine.md`; `paper/section_4_6_lod_publication_and_apis.md` |
| Prepare 10 study stimuli across three difficulty levels | Complete | `study/stimuli/study_stimuli.csv` has 10 expressions |
| Generate notation-only and MathOntoSpeak semantic TTS condition audio | Complete | 10 notation-only MP3 files under `study/audio/notation_only/mp3/`; 10 semantic MP3 files under `study/audio/mathontospeak_semantic/equation_gtts/` |
| Administer within-subjects study and enter data | Complete as rapid-pilot evidence package | `study/rapid_pilot/rapid_pilot_results.xlsx`; `study/rapid_pilot/responses.jsonl`; exported CSVs under `study/rapid_pilot/` |
| Transcribe/code interview responses and enter comprehension/NASA-TLX ratings | Complete as rapid-pilot evidence package | `study/rapid_pilot/rapid_pilot_interview_coding.csv`; `study/rapid_pilot/rapid_pilot_comprehension_scores.csv`; `study/rapid_pilot/rapid_pilot_nasa_tlx.csv` |
| Run statistical analysis | Complete | `reports/evaluation/week6_statistical_analysis_summary.md`; `reports/evaluation/week6_statistical_tests.csv` |
| Compile full system evaluation table | Complete | `reports/evaluation/week6_system_evaluation_table.md`; `reports/evaluation/week6_system_evaluation_table.csv` |
| Produce paper figures 1-4 | Complete | Week 6 figure PNG/SVG files under `figures/`; 5 PNG and 5 SVG files are present, including the optional tools/software flow figure |
| Write Sections 5 and 6 | Complete | `paper/section_5_evaluation.md`; `paper/section_6_discussion.md` |
| Push complete codebase to GitHub | Ready for this pass | Current push will include ontology grouping, overview, Whisper ASR evidence, and verification notes |
| Write comprehensive README with installation, replication, API calls, and license | Complete | `README.md`; `LICENSE`; `DATA_LICENSE.md` |

## Added Post-Meeting Evidence

- Grouped Protege ontology view: `ontologies/merged/math_accessibility_kg_week3_grouped_for_protege.owl`
- Clean overview figure: `figures/protege_grouped_ontology_overview.png`
- Whole-ontology interactive overview: `reports/ontology_whole_view/math_accessibility_kg_whole_overview.html`
- Whisper ASR audio intelligibility check: `scripts/week6_whisper_asr_audio_qc.py`
- Whisper ASR report: `reports/evaluation/week6_whisper_asr_audio_qc.md`
- Whisper ASR CSV: `reports/evaluation/week6_whisper_asr_audio_qc.csv`

## Verification Counts

- Week 4 arXiv equation fixture rows: 20
- Week 4 gTTS equation MP3 files: 20
- Week 4 Azure WAV files: 3
- Study stimuli rows: 10
- MCQ rows: 40
- Notation-only study MP3 files: 10
- MathOntoSpeak semantic study MP3 files: 10
- Statistical-test rows: 2
- System-evaluation rows: 13
- Week 6 PNG figures: 5
- Week 6 SVG figures: 5
- Whisper ASR rows: 20
- SPARQL query files: 15

## Intentionally Not Done

- Register ontology in Linked Open Vocabularies and BioPortal.
- Prepare 5-slide Scholars Academy presentation.
