# Week 4 TTS Rendering Engine Status

## Implemented

- Added `scripts/week4_tts_rendering.py` for generating four surface forms from a gloss metadata record.
- Added LaTeX-to-audio equation rendering:
  - `pylatexenc` parses LaTeX equations into macro/operator/identifier tokens.
  - `SymbolConceptLookup` maps parsed symbols to canonical concept labels and IRIs from `gloss/week3_gloss_dictionary.json`.
  - `GlossRepository` retrieves metadata used to build spoken semantic summaries.
  - Equation SSML and backend artifacts are written alongside the existing concept-gloss artifacts.
- Added math-aware SSML assembly with conservative prosody defaults:
  - rate: `-8%`
  - pitch: `+1st`
  - concept pause: `320ms`
  - clause pause: `180ms`
  - sentence pause: `420ms`
- Added three synthesis backends:
  - `mock`: writes inspectable JSON artifacts without credentials or network.
  - `gtts`: writes MP3 from plain surface text when `gTTS` is installed.
  - `azure`: writes WAV from SSML when Azure Speech credentials and SDK are available.
- Added focused tests in `tests/test_week4_tts_rendering.py`.
- Added `validation/week4_20_arxiv_equation_fixture.csv` with 20 arXiv math expressions for end-to-end pipeline testing.
- Added `requirements-week4.txt` for live Week 4 runtime dependencies.

## Verification

- `python -m unittest tests.test_week4_tts_rendering`
- `python scripts\week4_tts_rendering.py --backend mock --limit 5 --out reports\audio\week4_tts`
- `python scripts\week4_tts_rendering.py --equations validation\week4_20_arxiv_equation_fixture.csv --backend mock --limit 20 --out reports\audio\week4_tts`
- `python scripts\week4_tts_rendering.py --equations validation\week4_20_arxiv_equation_fixture.csv --backend gtts --limit 20 --out reports\audio\week4_tts_gtts`

The smoke run generated 20 artifacts: 5 concepts times 4 surface forms. The manifest is:

`reports/audio/week4_tts/week4_tts_mock_manifest.json`

The LaTeX equation smoke run generated 20 equation artifacts and matching SSML files. The manifest is:

`reports/audio/week4_tts/week4_latex_audio_mock_manifest.json`

The live gTTS equation run generated 20 MP3 artifacts and matching SSML files. The manifest is:

`reports/audio/week4_tts_gtts/week4_latex_audio_gtts_manifest.json`

## Manual Items

- Install live backend dependencies when ready:
  `python -m pip install -r requirements-week4.txt`
- For Azure Speech, set:
  - `AZURE_SPEECH_KEY`
  - `AZURE_SPEECH_REGION`
- gTTS and Azure both require internet access during live synthesis. The gTTS verification above was run with network access.
- gTTS does not support SSML directly, so the gTTS backend synthesizes the plain surface text while the pipeline still writes the matching SSML files for inspection and Azure use.
