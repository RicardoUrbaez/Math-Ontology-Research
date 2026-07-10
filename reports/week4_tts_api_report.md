# Week 4 TTS API Report

## What Was Implemented

Implemented `src/mathontospeak/api.py`, a local FastAPI app for the June 9-June 15 research plan. The API exposes the 50-record gloss dictionary, semantic search, symbol ambiguity discovery, LaTeX concept recommendation, and a LaTeX-to-JSON accessibility gloss endpoint that uses the existing Week 4 parser, concept lookup, surface-form generator, SSML builder, and TTS backends.

## Folder Structure

- `src/mathontospeak/api.py` - FastAPI app and response models.
- `data/gloss_dictionary/gloss_records_50.json` - source glossary for API concept records.
- `data/gloss_dictionary/gloss_records_50.jsonld` - JSON-LD gloss dictionary for RDF/Fuseki workflows.
- `queries/11_*.rq` through `queries/15_*.rq` - Fuseki-ready SPARQL examples.
- `outputs/json_glosses/`, `outputs/ssml/`, `outputs/audio/` - API output locations for accessibility endpoint runs.
- `docs/fuseki_setup.md` - local Fuseki setup steps.
- `reports/api_schema_examples.md` - endpoint examples and sample payloads.

## FastAPI Endpoints

- `GET /health` reports app status, version, glossary readiness, mock/gTTS/Azure backend readiness, and Fuseki status.
- `GET /concepts` returns all available gloss records from `data/gloss_dictionary/gloss_records_50.json`.
- `GET /concepts/{local_name}` returns one concept by case-insensitive local name.
- `GET /semantic-search` ranks records across labels, glosses/definitions, surface forms, provenance, domain tags, mapping metadata, and accessibility notes.
- `GET /cross-disciplinary-discovery` returns possible symbol meanings across domains, including ambiguity notes for symbols such as `T`.
- `GET /concept-recommender` parses LaTeX and returns likely concept IRIs with rule-based confidence values.
- `POST /accessibility/latex-to-json-gloss` returns parsed symbols, concept candidates, selected glosses, all four surface forms, selected surface form, SSML, provenance, accessibility notes, output file paths, and backend status.

## SPARQL/Fuseki Readiness

The repo is Fuseki-ready. The new query files use the required MathKG, RDF, RDFS, OWL, SKOS, DC, and DCTERMS prefixes and can be copied into the Fuseki UI or posted with curl after a local `mathkg` dataset is created.

The API health check attempts a short SPARQL `ASK` against `MATHKG_SPARQL_ENDPOINT` or `http://127.0.0.1:3030/mathkg/query`. It reports Fuseki as ready only if that query succeeds.

## JSON-LD Gloss Dictionary

`data/gloss_dictionary/gloss_records_50.jsonld` is documented as the JSON-LD upload option for Fuseki/Jena versions that support JSON-LD. If local JSON-LD upload is not supported, `ontologies/merged/math_accessibility_kg_merged_gloss.ttl` can be used as a Turtle fallback for gloss metadata.

## LaTeX-to-JSON Gloss Accessibility Endpoint

The endpoint accepts:

```json
{
  "latex": "S=\\sum_k a_k X_k",
  "context": "series and random variables",
  "surface_form": "pedagogical",
  "backend": "mock"
}
```

The endpoint writes:

- JSON payloads to `outputs/json_glosses/`
- SSML to `outputs/ssml/`
- mock transcripts or audio files to `outputs/audio/`

## Mock Backend Status

The mock backend is implemented and used by default. It writes local `.txt` transcript files, which keeps local testing reproducible and independent of cloud credentials.

## Azure/gTTS Readiness

Azure requires `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` for live synthesis. After credentials were supplied through local PowerShell environment variables, the Week 4 pipeline produced live Azure WAV evidence for three arXiv equation examples under `reports/audio/week4_tts_azure/`. If credentials are missing or synthesis fails, the backend falls back to mock output and reports a warning.

gTTS is gTTS-ready when the package is installed and network synthesis succeeds. If gTTS fails, it falls back to the mock backend and reports a warning.

## Limitations

- Semantic search uses local weighted keyword scoring, not embeddings.
- Concept recommender confidence values are rule-based MVP scores.
- Symbol ambiguity is seeded for common symbols and should be expanded with corpus evidence.
- Fuseki is not started by the API; it must be run separately.
- JSON-LD upload support depends on the local Fuseki/Jena version.

## Next Steps

- Add automated API route tests for `src.mathontospeak.api`.
- Expand symbol ambiguity tables using the Week 3 corpus and validation notes.
- Record Fuseki benchmark response times under `reports/sparql/`.
- Add optional SPARQL-backed search once local Fuseki is confirmed running.
- Configure Azure credentials only in the local environment, never in source files.
