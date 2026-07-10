# 4.6 LOD Publication and APIs

The MathOntoSpeak knowledge graph is published in linked-data-oriented formats and exposed through both SPARQL and REST-style API interfaces. This dual publication strategy supports two audiences: ontology and semantic-web users can query the graph directly through RDF tooling, while accessibility applications can use a simpler JSON API for search, recommendation, and LaTeX-to-gloss conversion.

## 4.6.1 RDF Serialization

The merged ontology and gloss dictionary are serialized as Turtle, RDF/XML, and JSON-LD. The primary publication files are:

- `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`
- `ontologies/merged/math_accessibility_kg_merged_gloss.rdf`
- `ontologies/merged/math_accessibility_kg_merged_gloss.jsonld`

The serialization script is `scripts/serialize_merged_ontology_gloss.py`. It combines the ontology layer with the 500-record gloss dictionary so that each concept can be queried together with its label, definition, semantic type, kind/role classification, domain tags, four surface forms, and provenance. The full exported graph contains 13,986 RDF triples in each serialization format.

The W3C RDF Validator was used for external validation on a reduced RDF/XML sample because the full graph exceeded the validator's direct-input form limit. The sample validation returned:

```text
Validation Results
Your RDF document validated successfully.
```

The full RDF/XML, Turtle, and JSON-LD files were also parsed locally with `rdflib`, each returning 13,986 triples. The W3C evidence is stored in `reports/w3c/w3c_rdf_validator_status_2026-07-10.md` and `reports/w3c/w3c_rdf_validator_tiny_sample_success_2026-07-10.txt`.

## 4.6.2 SPARQL Endpoint

The RDF graph is deployable through Apache Jena Fuseki. The local deployment uses two datasets:

- `/mathkg`
- `/mathkg500`

The 500-concept dataset is loaded through `scripts/start_fuseki_mathkg.ps1` and `scripts/load_fuseki_mathkg.ps1`. The working local endpoint is:

```text
http://localhost:3030/mathkg500/query
```

The Fuseki UI was manually checked at `http://localhost:3030/#/`. A hierarchy query over the current `KindConcept` and `RoleConcept` branches returned 500 concepts, with 487 kind concepts and 13 role concepts. This confirms that the cleaned 500-concept layer is visible through SPARQL after loading.

The project includes reusable SPARQL examples for semantic lookup, cross-domain symbol discovery, accessibility gloss retrieval, provenance lookup, and surface-form extraction. Example query files include:

- `queries/11_semantic_search_example.rq`
- `queries/12_cross_domain_symbol_discovery.rq`
- `queries/13_accessibility_gloss_lookup.rq`
- `queries/14_concept_provenance_for_api.rq`
- `queries/15_surface_forms_by_concept.rq`

## 4.6.3 FastAPI Service

The REST API is implemented with FastAPI in `api/main.py` and `api/services.py`. It is started locally with:

```powershell
python -m uvicorn api.main:app --reload
```

The interactive OpenAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

The API exposes four assignment-facing endpoints plus a health endpoint:

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | `GET` | Reports API, gloss dictionary, and Fuseki readiness. |
| `/api/search` | `GET` | Searches concepts, labels, glosses, domains, semantic types, and provenance. |
| `/api/discover` | `POST` | Finds related concepts for cross-disciplinary discovery. |
| `/api/recommend` | `POST` | Recommends concepts from context text, LaTeX, seed concepts, and domains. |
| `/api/accessibility/latex-gloss` | `POST` | Converts LaTeX into JSON gloss output, resolved concepts, speech text, and SSML. |

The health endpoint checks whether the gloss dictionary is available and whether the configured Fuseki endpoint can answer a SPARQL query. When Fuseki is unavailable, the API still returns deterministic local results from the gloss dictionary so that accessibility testing can continue.

## 4.6.4 API Schema and Example Calls

The search endpoint accepts a required query string and optional filters:

```text
GET /api/search?q=matrix&limit=5
```

Optional filters include `domain`, `semantic_type`, and `kind_role`. A typical response includes the original query and a ranked list of concept records with labels, IRIs, glosses, surface forms, domain tags, and provenance.

The cross-disciplinary discovery endpoint accepts a seed concept, optional source domain, target domains, semantic type, and result limit:

```json
{
  "seed_concept": "Matrix",
  "source_domain": null,
  "target_domains": [],
  "semantic_type": "matrix",
  "limit": 5
}
```

The recommender endpoint accepts a natural-language context, a LaTeX expression, optional seed concepts, optional domain tags, and a limit:

```json
{
  "context": "series and random variables",
  "latex": "S=\\sum_k a_k X_k",
  "seed_concepts": [],
  "domain_tags": [],
  "limit": 5
}
```

The accessibility endpoint accepts LaTeX and an audience setting:

```json
{
  "latex": "x \\in \\mathbb{R}",
  "audience": "pedagogical",
  "arxiv_id": "manual_test",
  "title": "Manual accessibility gloss test"
}
```

For this example, the endpoint resolved Variable, Element, and Real Number, then returned plain text, speech text, SSML, token-level evidence, and output artifact paths. The saved output evidence includes:

- `outputs/json_glosses/api_73b30d4d1c.json`
- `outputs/ssml/api_73b30d4d1c.ssml`
- `outputs/audio/api_73b30d4d1c.txt`

## 4.6.5 Publication Status

The repository has been pushed to the public GitHub repository:

```text
https://github.com/RicardoUrbaez/Math-Ontology-Research
```

The pushed repository includes the RDF serializations, W3C validation evidence, Fuseki setup scripts, SPARQL examples, FastAPI implementation, API schema examples, and test files. This completes the Week 4 publication layer for local reproducibility and public inspection. A later production deployment could move Fuseki and FastAPI from local services to hosted infrastructure, but the current project satisfies the research-plan requirement for public repository publication, local SPARQL deployment, and implemented API access.

