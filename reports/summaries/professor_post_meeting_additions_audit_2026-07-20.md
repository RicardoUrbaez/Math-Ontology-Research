# Professor Post-Meeting Additions Audit

Date checked: 2026-07-20

Project root: `C:\Users\Ricardo\Documents\Math-Ontology-Research`

Research plan source: `C:\Users\Ricardo\Downloads\Research Materials 2026\Research Plan_Ricardo_NK (2).pdf`

## Short Answer

Weeks 1 through 6 are completed as a project evidence package, based on the current repository artifacts and local verification checks. The post-meeting additions are now represented in the repository: NER evidence, grouped Protege visualization, TTS/audio evidence, and Whisper ASR validation. The TTS/audio work is the generation layer, while Whisper/ASR is an evaluation layer that checks whether generated audio can be transcribed back into recognizable text.

## Where the Three Items Fit

| Professor item | Where it appears in the plan | Current status | Evidence |
| --- | --- | --- | --- |
| NER corpus pipeline | Page 3, June 1-June 8: "Implement NER corpus pipeline..." | Complete with spaCy + custom MathEntRuler evidence | `src/mathontospeak/corpus_ner.py`, `scripts/run_corpus_ner.py`, `reports/corpus/week3_spacy_corpus_pipeline_status.md`, `reports/corpus/week3_top_100_symbol_contexts.csv` |
| Grouped Protege view / IRI grouping | Not a separate PDF bullet; it supports Week 1 Protege setup and Week 3 kind/role inspection | Complete as a professor-facing visualization add-on | `docs/protege_grouped_view_instructions.md`, `scripts/build_protege_grouped_ontology.py`, `ontologies/merged/math_accessibility_kg_week3_grouped_for_protege.owl`, `figures/protege_grouped_ontology_overview.png` |
| TTS / text-to-speech | Page 3-4, June 9-June 15: four-surface-form generator, SSML, Azure TTS, gTTS, LaTeX-to-audio | Complete | `paper/section_4_5_tts_rendering_engine.md`, `scripts/week4_tts_rendering.py`, `src/mathontospeak/tts_backends.py`, `reports/audio/week4_tts_gtts/`, `reports/audio/week4_tts_azure/`, `study/audio/` |
| Whisper / ASR | Not in the original research plan PDF | Complete as a post-meeting Week 6 evaluation add-on | `scripts/week6_whisper_asr_audio_qc.py`, `reports/evaluation/week6_whisper_asr_audio_qc.csv`, `reports/evaluation/week6_whisper_asr_audio_qc.md`, `paper/section_5_evaluation.md` |

## Important Clarification

Whisper is ASR, meaning automatic speech recognition or speech-to-text. It is not text-to-speech. In this project, Whisper would fit best as an evaluation tool:

1. Generate MathOntoSpeak semantic TTS audio.
2. Run Whisper or another ASR model on that audio.
3. Compare the ASR transcript against the intended semantic gloss.
4. Report word error rate, key-concept recall, or semantic keyword coverage.

This strengthens the claim that the generated audio is not only present, but also intelligible and recoverable by a speech-recognition system. The current ASR report reviewed 20 audio files, produced transcripts for 20/20, measured mean word error rate of 0.220, and measured semantic concept-keyword recall of 0.883.

If "IRB groups" means Institutional Review Board approval for human participants, that is different from Protege grouping. IRB approval is not represented as completed in this repository and should be handled manually with the professor/university before making formal human-subjects claims.

## Week 1-6 Completion Check

| Week | Status | Evidence summary |
| --- | --- | --- |
| Week 1 | Complete | 4 seed resources/tooling notes, ROBOT reports, 50-concept validation set, Section 4.1 |
| Week 2 | Complete | IRI canonicalization, 50-row mapping table, merge/conflict logs, seed ontology, provenance |
| Week 3 | Complete | 500 metadata rows, 487 kind and 13 role concepts, HermiT report, SPARQL benchmark, 500 gloss records, NER corpus outputs |
| Week 4 | Complete | Four surface forms, SSML, LaTeX-to-audio, mock/gTTS/Azure backends, RDF exports, FastAPI endpoints |
| Week 5 | Complete | 10 stimuli, 40 MCQ rows, study protocol, counterbalancing, notation-only audio, semantic TTS audio, rapid-pilot workbook |
| Week 6 | Complete | Statistical summary, system evaluation table, 5 PNG and 5 SVG figures, Sections 5 and 6, reproducible evaluation package |

## Local Verification Run

Commands run on 2026-07-20:

```powershell
python -m compileall src scripts
python -m pytest -q
```

Results:

- Python compile check passed.
- Test suite passed: 22 tests passed, 1 warning from FastAPI/Starlette test client.
- Count checks found:
  - 50 validation concepts
  - 50 Week 2 mapping rows
  - 500 Week 3 metadata rows
  - 500 Week 3 gloss records
  - 1,095 Week 3 spaCy symbol-context rows
  - 100 Week 3 top-symbol rows
  - 20 Week 4 arXiv equation fixture rows
  - 20 Week 4 gTTS MP3 files
  - 3 Week 4 Azure WAV files
  - 10 Week 5 stimuli
  - 40 Week 5 MCQ rows
  - 10 notation-only study MP3 files
  - 10 MathOntoSpeak semantic study MP3 files
  - 5 Week 6 PNG figures
  - 5 Week 6 SVG figures

## Completed ASR Add-On

Whisper/ASR is now implemented through:

- `scripts/week6_whisper_asr_audio_qc.py`
- `reports/evaluation/week6_whisper_asr_audio_qc.csv`
- `reports/evaluation/week6_whisper_asr_audio_qc.md`
- short paragraph in `paper/section_5_evaluation.md` under audio quality

Current claim:

"To further evaluate speech intelligibility, generated audio was transcribed with a Whisper-style ASR model and compared against the intended semantic glosses using transcript-level and concept-keyword coverage metrics."
