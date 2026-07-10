# Math Ontology Research

This project organizes resources for math ontology accessibility research using OWL/RDF ontologies, ROBOT reports, Apache Jena Fuseki, Protege, FastAPI, and LaTeX-to-gloss accessibility tooling.

## Run Fuseki

Start the 500-concept SPARQL endpoint from this repo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_fuseki_mathkg.ps1
```

Default endpoint:

```text
http://localhost:3030/mathkg500/query
```

The script uses the local Fuseki install at `C:\Users\Ricardo\Downloads\apache-jena-fuseki-6.1.0` and starts the configured `/mathkg` and `/mathkg500` datasets.

If `/mathkg500` exists but has no triples, load the cleaned ontology:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\load_fuseki_mathkg.ps1
```

## Run FastAPI

```powershell
python -m uvicorn api.main:app --reload
```

Set `MATHKG_SPARQL_ENDPOINT` to point the API at a different Fuseki dataset. If Fuseki is not running, the API still serves deterministic results from `gloss\week3_gloss_dictionary.json`.

## API Endpoints

- `GET /api/search?q=matrix&limit=5` - semantic search over concepts, glosses, domains, and provenance.
- `POST /api/discover` - cross-disciplinary discovery from a seed concept or source domain.
- `POST /api/recommend` - concept recommendations from context text, LaTeX, seed concepts, and domains.
- `POST /api/accessibility/latex-gloss` - LaTeX to JSON gloss tokens, surface forms, speech text, and SSML.

Example:

```powershell
Invoke-RestMethod http://localhost:8000/api/search?q=matrix
```
