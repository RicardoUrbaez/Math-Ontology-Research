# Azure TTS Live Test Status

Date: 2026-07-10

## Result

Azure Speech synthesis was live-tested with the Week 4 LaTeX-to-audio pipeline.

Command pattern:

```powershell
python scripts\week4_tts_rendering.py --equations validation\week4_20_arxiv_equation_fixture.csv --backend azure --limit 3 --out reports\audio\week4_tts_azure
```

Do not store Azure credentials in the repository. The run used local PowerShell environment variables:

```text
AZURE_SPEECH_KEY
AZURE_SPEECH_REGION
```

## Evidence

Manifest:

```text
reports/audio/week4_tts_azure/week4_latex_audio_azure_manifest.json
```

Generated Azure WAV files:

```text
reports/audio/week4_tts_azure/equation_azure/eq_001_2606_19323v1.wav
reports/audio/week4_tts_azure/equation_azure/eq_002_2606_19322v1.wav
reports/audio/week4_tts_azure/equation_azure/eq_003_2606_19313v1.wav
```

Generated SSML files:

```text
reports/audio/week4_tts_azure/equation_ssml/eq_001_2606_19323v1.ssml
reports/audio/week4_tts_azure/equation_ssml/eq_002_2606_19322v1.ssml
reports/audio/week4_tts_azure/equation_ssml/eq_003_2606_19313v1.ssml
```

Manifest status:

```text
3 equation synthesis artifacts
backend: azure
status: ok
detail: Azure WAV written
```

## Security Note

The Azure key should be treated as sensitive. If a key is exposed in a screenshot, chat, terminal capture, or repository file, regenerate that key in Azure Portal before continuing future runs.
