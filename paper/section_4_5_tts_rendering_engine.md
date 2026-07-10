# 4.5 TTS Rendering Engine

The MathOntoSpeak rendering engine converts ontology-backed mathematical concepts and LaTeX expressions into speech-oriented output. Its purpose is not only to pronounce notation, but also to expose the semantic role of mathematical symbols for blind and low-vision learners. The engine is implemented as a modular pipeline so that the same gloss metadata can support multiple audiences, output formats, and synthesis backends.

## 4.5.1 Four Surface Forms

Each gloss metadata record is rendered into four surface forms: concise, pedagogical, expert, and document-role. These forms are stored in the project gloss dictionary and are generated from the concept label, semantic type, canonical gloss, domain tags, kind/role classification, and source provenance. The concise form gives a short semantic description, the pedagogical form introduces the concept in learner-facing language, the expert form preserves more formal terminology, and the document-role form describes how the concept usually functions inside mathematical prose.

This design lets the system adapt speech output to context. For example, a quick lookup can use the concise form, while a study condition or accessibility endpoint can request a pedagogical form. The current implementation uses the records in `gloss/week3_gloss_dictionary.json` and the rendering code in `scripts/week4_tts_rendering.py`, `src/mathontospeak/surface_forms.py`, and `src/mathontospeak/gloss_record.py`.

## 4.5.2 SSML Prosody Layer

The speech layer wraps rendered glosses in Speech Synthesis Markup Language (SSML). The SSML profile is tuned for mathematical content using conservative prosodic settings:

| Parameter | Current value | Purpose |
|---|---:|---|
| Rate | `-8%` | Slows dense symbolic language slightly. |
| Pitch | `+1st` | Adds mild clarity without sounding unnatural. |
| Concept pause | `320ms` | Separates named concepts and semantic glosses. |
| Clause pause | `180ms` | Marks short internal phrase boundaries. |
| Sentence pause | `420ms` | Gives listeners time to process complete mathematical statements. |

These values were chosen to make symbol-to-concept transitions easier to follow while avoiding exaggerated pauses. The SSML layer is implemented in `src/mathontospeak/ssml_builder.py` and reused by the equation pipeline in `scripts/week4_tts_rendering.py`.

## 4.5.3 LaTeX-to-Audio Pipeline

The LaTeX-to-audio pipeline follows five steps:

1. Parse the LaTeX expression into mathematical tokens.
2. Map symbols, operators, identifiers, and macros to concept labels and concept IRIs.
3. Retrieve the matching gloss metadata record from the ontology-backed dictionary.
4. Assemble a spoken semantic sentence and SSML document.
5. Send the plain text or SSML to the selected synthesis backend.

The parser recognizes common mathematical constructs such as `\sum`, `\int`, `\mathbb{R}`, set membership, arrows, inequalities, identifiers, and Greek-letter macros. The lookup layer maps these tokens to canonical concept records such as Addition, Integral, Real Number, Element, Map, Inequality, Variable, and Function. The output preserves both the original LaTeX expression and the resolved semantic concepts, so the same run can support audio rendering, debugging, and later analysis.

The pipeline was tested on 20 real arXiv equations stored in `validation/week4_20_arxiv_equation_fixture.csv`. The test fixture includes expressions from algebra, analysis, probability, geometry, and related math categories. The reproducible mock run writes JSON and SSML artifacts, while the live gTTS run writes MP3 files and matching SSML files. The main evidence files are:

- `reports/tts_pipeline_test_results.md`
- `outputs/pipeline_tests/week4_pipeline_test_manifest.json`
- `reports/audio/week4_tts/week4_latex_audio_mock_manifest.json`
- `reports/audio/week4_tts_gtts/week4_latex_audio_gtts_manifest.json`

## 4.5.4 TTS Backends

The rendering engine supports three backend modes. The mock backend writes local transcript or JSON artifacts without network access, which makes regression testing deterministic. The gTTS backend synthesizes MP3 files from the plain-text surface form; gTTS does not consume SSML directly, so the pipeline still writes SSML separately for inspection and Azure compatibility. The Azure backend uses `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` from the local environment and performs SSML-based synthesis to WAV audio.

This separation lets the project distinguish reproducible local evidence from credential-dependent cloud synthesis. The mock and gTTS paths have been run locally. Azure Speech was also live-tested on three arXiv equation examples, producing WAV artifacts and matching SSML files under `reports/audio/week4_tts_azure/`.

## 4.5.5 Verification

The rendering engine was verified with local syntax checks, unit tests, mock synthesis, and gTTS synthesis. The current validation evidence includes:

```text
python -m compileall src scripts api
python -m pytest -q
python scripts\run_week4_pipeline_tests.py
```

The latest full test run passed with 22 tests. The 20-equation pipeline completed successfully, the gTTS run produced MP3 artifacts for the arXiv equation fixture, and the Azure run produced WAV artifacts for three equation examples. Together, these results support the claim that MathOntoSpeak can convert LaTeX expressions into structured semantic gloss output, SSML, and audio-ready artifacts across local, gTTS, and Azure synthesis backends.
