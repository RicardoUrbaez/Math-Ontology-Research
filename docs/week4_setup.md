# Week 4 MVP Setup

This Week 4 layer adds the local MathOntoSpeak MVP pipeline:

- gloss metadata records
- four-surface-form generation
- SSML building
- LaTeX symbol parsing
- symbol-to-concept lookup
- mock, gTTS-ready, and Azure-ready TTS backends
- LaTeX to gloss to SSML to audio/transcript pipeline
- 20 arXiv-style test equations

The mock backend is the default and writes transcript `.txt` files, so it works without cloud credentials.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_week4_pipeline_tests.py
python -m compileall src scripts
```

Outputs are written to:

- `outputs/json_glosses/`
- `outputs/ssml/`
- `outputs/audio/`
- `outputs/pipeline_tests/`
- `reports/tts_pipeline_test_results.md`

Azure is Azure-ready only after `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are configured. gTTS is gTTS-ready when the package and network path are available. The included runner tests the local mock backend.
