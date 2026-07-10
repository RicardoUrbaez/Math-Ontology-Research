# Week 4 API Schema Examples

The assignment-shaped Week 4 API is exposed by `api.main`.

Run locally:

```powershell
python -m uvicorn api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

The mock backend is the default for reproducible local testing. It writes transcript files instead of requiring network access or cloud credentials.

## Endpoint List

- `GET /health`
- `GET /api/search?q={query}&limit={limit}`
- `POST /api/discover`
- `POST /api/recommend`
- `POST /api/accessibility/latex-gloss`

## Sample GET URLs

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/search?q=matrix%20linear%20algebra&limit=5
```

## Sample POST Body

```json
{
  "latex": "S=\\sum_k a_k X_k",
  "context": "series and random variables",
  "surface_form": "pedagogical",
  "backend": "mock"
}
```

Allowed `surface_form` values:

- `concise`
- `pedagogical`
- `expert`
- `document_role`

Allowed `backend` values:

- `mock`
- `gtts`
- `azure`

## Sample Curl Commands

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe "http://127.0.0.1:8000/api/search?q=matrix%20linear%20algebra&limit=3"
curl.exe -X POST "http://127.0.0.1:8000/api/discover" -H "Content-Type: application/json" -d "{\"seed_concept\":\"Matrix\",\"target_domains\":[\"calculus\"],\"limit\":3}"
curl.exe -X POST "http://127.0.0.1:8000/api/recommend" -H "Content-Type: application/json" -d "{\"latex\":\"S=\\\\sum_k a_k X_k\",\"limit\":5}"
curl.exe -X POST "http://127.0.0.1:8000/api/accessibility/latex-gloss" -H "Content-Type: application/json" -d "{\"latex\":\"x \\\\in \\\\mathbb{R}\",\"audience\":\"pedagogical\"}"
```

## Example Responses

`GET /health` returns backend readiness:

```json
{
  "status": "ok",
  "version": "0.1.0-week4-api",
  "backend_readiness": {
    "gloss_dictionary": {
      "status": "ready",
      "path": "C:\\Users\\Ricardo\\Documents\\Math-Ontology-Research\\data\\gloss_dictionary\\gloss_records_50.json",
      "record_count": 50
    },
    "mock_tts": {
      "status": "ready",
      "detail": "writes local transcript files; default for reproducible tests"
    },
    "azure": {
      "status": "not_configured",
      "detail": "set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION to use Azure synthesis"
    },
    "fuseki": {
      "status": "not_running_or_empty",
      "endpoint": "http://127.0.0.1:3030/mathkg/query"
    }
  }
}
```

`GET /api/search?q=matrix&limit=1` returns ranked results:

```json
{
  "query": "matrix",
  "results": [
    {
      "concept_iri": "http://example.org/mathkg/Matrix",
      "canonical_label": "Matrix",
      "score": 15.5,
      "reasons": ["exact concept-name match", "gloss/definition matched: matrix"]
    }
  ]
}
```

`POST /api/discover` returns cross-domain discovery results:

```json
{
  "seed": {"canonical_label": "Matrix"},
  "target_domains": ["calculus"],
  "results": []
}
```

`POST /api/accessibility/latex-gloss` returns parser, concept, gloss, and SSML data:

```json
{
  "latex": "S=\\sum_k a_k X_k",
  "plain_text": "S equals sum k a k X k",
  "audience": "pedagogical",
  "speech_text": "...",
  "ssml": "<speak version=\"1.0\" ...>...</speak>",
  "resolved_count": 3,
  "tokens": []
}
```
