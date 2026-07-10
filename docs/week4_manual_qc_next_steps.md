# Week 4 Manual QC and Next Steps Runbook

Date: 2026-07-10

This runbook covers the June 9-June 15 block:

- four surface forms and SSML prosody
- mock, gTTS, and Azure TTS backends
- LaTeX to audio/gloss pipeline over 20 equations
- Turtle and JSON-LD serialization
- W3C RDF validation
- Fuseki SPARQL endpoint
- four FastAPI endpoints
- public GitHub push

## Current QC Snapshot

Codex verified these locally:

- `python scripts\run_week4_pipeline_tests.py`
  - processed 20 equations with mock backend
  - 20 completed
- `python scripts\serialize_merged_ontology_gloss.py`
  - serialized 13,986 RDF triples
  - wrote `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`
  - wrote `ontologies/merged/math_accessibility_kg_merged_gloss.jsonld`
- local RDF parse validation
  - Turtle parsed as 13,986 triples
  - JSON-LD parsed as 13,986 triples
- focused API/TTS tests
  - 17 passed
- full project tests
  - 22 passed

## What Is Already Implemented

### TTS and LaTeX Pipeline

Evidence files:

- `scripts/week4_tts_rendering.py`
- `src/mathontospeak/tts_backends.py`
- `src/mathontospeak/pipeline.py`
- `validation/week4_20_arxiv_equation_fixture.csv`
- `reports/tts_pipeline_test_results.md`
- `reports/summaries/week4_tts_rendering_status.md`

Status:

- four surface forms are generated
- SSML includes math-oriented rate, pitch, and pause defaults
- mock backend works without credentials
- gTTS backend is implemented and has prior MP3 evidence
- Azure backend is implemented but needs your Azure Speech key/region to run live
- 20-equation mock end-to-end test passes

### RDF Serialization

Evidence files:

- `scripts/serialize_merged_ontology_gloss.py`
- `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`
- `ontologies/merged/math_accessibility_kg_merged_gloss.jsonld`

Status:

- Turtle and JSON-LD exist
- both parse locally with `rdflib`
- W3C validator check passed on a 500-triple RDF/XML sample; full graph also parses locally

### Fuseki

Evidence:

- Fuseki started locally on `http://localhost:3030`
- `/mathkg500` was loaded with 6,952 triples earlier
- manual UI query returned `kind = 487`, `role = 13`

Status:

- local Fuseki deployment works
- keep the Fuseki PowerShell server window open only while testing

### FastAPI

Use this app for the assignment-shaped endpoint set:

```powershell
python -m uvicorn api.main:app --reload
```

Required endpoints:

- `GET /api/search`
- `POST /api/discover`
- `POST /api/recommend`
- `POST /api/accessibility/latex-gloss`

Status:

- implemented in `api/main.py`
- tested by `tests/test_api_routes.py`
- backed by `api/services.py`

## Manual Round 1: Confirm Local Week 4 Tests

Run this from PowerShell:

```powershell
cd C:\Users\Ricardo\Documents\Math-Ontology-Research
python -m compileall src scripts api
python -m pytest -q
python scripts\run_week4_pipeline_tests.py
```

Expected:

```text
22 passed
Processed 20 equations with mock backend; 20 completed.
```

Send Codex:

- the final `pytest` summary
- the final `run_week4_pipeline_tests.py` summary
- any error text if something fails

## Manual Round 2: Optional Live gTTS Audio

Run this only if you want live MP3 evidence:

```powershell
python scripts\week4_tts_rendering.py --equations validation\week4_20_arxiv_equation_fixture.csv --backend gtts --limit 20 --out reports\audio\week4_tts_gtts
```

Expected:

- MP3 files under `reports/audio/week4_tts_gtts/equation_gtts/`
- SSML files under `reports/audio/week4_tts_gtts/equation_ssml/`
- manifest at `reports/audio/week4_tts_gtts/week4_latex_audio_gtts_manifest.json`

If gTTS fails, it usually means network access failed. The mock backend is still valid for reproducible local testing.

## Manual Round 3: Optional Azure Audio

Run this only if you have Azure Speech credentials. Do not paste credentials into chat.

```powershell
$env:AZURE_SPEECH_KEY="YOUR_KEY_HERE"
$env:AZURE_SPEECH_REGION="YOUR_REGION_HERE"
python scripts\week4_tts_rendering.py --equations validation\week4_20_arxiv_equation_fixture.csv --backend azure --limit 5 --out reports\audio\week4_tts_azure
```

Expected:

- WAV files under `reports/audio/week4_tts_azure/`
- if credentials are missing or invalid, the backend falls back to mock transcript files and records a warning

## Manual Round 4: Run FastAPI

Start the API:

```powershell
cd C:\Users\Ricardo\Documents\Math-Ontology-Research
python -m uvicorn api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Try these in another PowerShell window:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/health"
Invoke-RestMethod "http://127.0.0.1:8000/api/search?q=matrix&limit=5"
Invoke-RestMethod "http://127.0.0.1:8000/api/discover" -Method Post -ContentType "application/json" -Body '{"seed_concept":"Matrix","target_domains":["calculus"],"limit":3}'
Invoke-RestMethod "http://127.0.0.1:8000/api/recommend" -Method Post -ContentType "application/json" -Body '{"latex":"S=\\sum_k a_k X_k","limit":5}'
Invoke-RestMethod "http://127.0.0.1:8000/api/accessibility/latex-gloss" -Method Post -ContentType "application/json" -Body '{"latex":"x \\in \\mathbb{R}","audience":"pedagogical"}'
```

Expected:

- `/health` returns `api = ok`
- `/api/search` returns Matrix near the top
- `/api/discover` returns a Matrix seed and discovery results
- `/api/recommend` returns LaTeX-derived concept seeds
- `/api/accessibility/latex-gloss` returns tokens, resolved concepts, speech text, and SSML

Send Codex:

- whether the docs page opens
- the first few lines or screenshot of the endpoint output
- any error text

## Manual Round 5: Fuseki Recheck

If Fuseki is still running, use:

```text
http://localhost:3030/#/
```

Click `/mathkg500` then `query`, and run:

```sparql
PREFIX mathkg: <http://example.org/mathkg/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?kindRole (COUNT(?concept) AS ?count)
WHERE {
  VALUES ?root { mathkg:KindConcept mathkg:RoleConcept }
  ?concept rdfs:subClassOf+ ?root ;
           mathkg:kindRoleType ?kindRole .
}
GROUP BY ?kindRole
ORDER BY ?kindRole
```

Expected:

```text
kind  487
role  13
```

If Fuseki is closed, restart and reload:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_fuseki_mathkg.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\load_fuseki_mathkg.ps1
```

## Manual Round 6: W3C RDF Validator

This is external/manual.

Status: completed on 2026-07-10.

Evidence:

```text
reports/w3c/w3c_rdf_validator_status_2026-07-10.md
reports/w3c/w3c_rdf_validator_tiny_sample_success_2026-07-10.txt
```

Open:

```text
https://www.w3.org/RDF/Validator/
```

Important: the old W3C validator direct-input form only accepts a small paste. The full merged RDF/XML file is about 1.5 MB and triggers:

```text
HTTP ERROR 500
Form too large
```

That means the page rejected the paste size; it does not mean the RDF is invalid.

Codex already validated the full exports locally:

```text
Turtle: 13,986 triples
JSON-LD: 13,986 triples
RDF/XML: 13,986 triples
```

For the manual W3C screenshot, validate the tiny RDF/XML sample. This one stays below the validator's form-size limit even after browser encoding:

```text
C:\Users\Ricardo\Documents\Math-Ontology-Research\reports\w3c\math_accessibility_kg_merged_gloss_w3c_tiny_sample.rdf
```

Steps:

1. Open the sample `.rdf` file in VS Code.
2. Select all and copy.
3. On the W3C page, click `Clear the textarea`.
4. Paste the sample RDF/XML.
5. Leave `Triples Only` selected.
6. Click `Parse RDF`.

Later, after the repository is pushed publicly, try full-file URI validation using the raw GitHub URL for:

```text
ontologies/merged/math_accessibility_kg_merged_gloss.rdf
```

Save evidence:

- screenshot of success or warnings
- downloaded validator output, if available
- notes under `reports/` if the validator reports warnings

Send Codex:

- screenshot or copied validator message
- any warning/error text

Completed result:

```text
Validation Results
Your RDF document validated successfully.
```

## Manual Round 7: GitHub Push

Do not push yet until we decide what to include. The repo currently has many generated artifacts and unrelated existing changes.

First run:

```powershell
git status --short --branch
git remote -v
```

Current remote already exists:

```text
origin  https://github.com/RicardoUrbaez/Math-Ontology-Research.git
```

Recommended next Git step:

- decide whether to track generated audio files
- decide whether to track generated reports/logs
- keep `data/arxiv_papers/` ignored because the 200 PDFs are a local cache
- then ask Codex to prepare the exact `git add`, commit, and push plan

## Completion Language

Use this wording now:

```text
Week 4 implementation is locally complete for mock TTS, gTTS-ready/Azure-ready backends, 20-equation LaTeX-to-gloss pipeline, RDF serialization, Fuseki deployment, FastAPI endpoint implementation, and W3C RDF sample validation. GitHub push remains the external/manual publication step.
```
