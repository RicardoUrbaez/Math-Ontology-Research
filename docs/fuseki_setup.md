# Fuseki Setup for MathKG

These steps make the project Fuseki-ready for local SPARQL testing. They do not require the API to run Fuseki automatically.

## 1. Start Apache Jena Fuseki

Download and unpack Apache Jena Fuseki if it is not already installed.

From the Fuseki folder:

```powershell
.\fuseki-server.bat
```

Default web UI:

```text
http://127.0.0.1:3030/
```

If you use a different port, set the API endpoint before starting Uvicorn:

```powershell
$env:MATHKG_SPARQL_ENDPOINT="http://127.0.0.1:3030/mathkg/query"
```

## 2. Create a Dataset Named `mathkg`

In the Fuseki web UI:

1. Open `http://127.0.0.1:3030/`.
2. Select `manage datasets`.
3. Select `add new dataset`.
4. Name the dataset `mathkg`.
5. Choose a persistent dataset for repeatable local testing, or in-memory for a temporary benchmark run.
6. Create the dataset.

The query endpoint should be:

```text
http://127.0.0.1:3030/mathkg/query
```

## 3. Upload the Seed Ontology

Upload:

```text
ontologies/merged/math_accessibility_kg_seed.ttl
```

In the Fuseki web UI:

1. Open the `mathkg` dataset.
2. Go to the upload/data page.
3. Choose the Turtle file above.
4. Upload it into the default graph unless a benchmark requires named graphs.

## 4. Upload the JSON-LD Gloss Dictionary if Supported

Upload:

```text
data/gloss_dictionary/gloss_records_50.jsonld
```

If your Fuseki/Jena version accepts JSON-LD directly, upload it as JSON-LD into the same dataset.

If JSON-LD upload is not supported in your local UI, use the RDF/Turtle gloss serialization instead when available:

```text
ontologies/merged/math_accessibility_kg_merged_gloss.ttl
```

## 5. Run SPARQL Queries from `queries/`

Open the `mathkg` query page:

```text
http://127.0.0.1:3030/#/dataset/mathkg/query
```

Copy and run the query files:

- `queries/11_semantic_search_example.rq`
- `queries/12_cross_domain_symbol_discovery.rq`
- `queries/13_accessibility_gloss_lookup.rq`
- `queries/14_concept_provenance_for_api.rq`
- `queries/15_surface_forms_by_concept.rq`

Command-line example with curl:

```powershell
curl.exe -X POST "http://127.0.0.1:3030/mathkg/query" -H "Accept: application/sparql-results+json" --data-urlencode "query@queries/11_semantic_search_example.rq"
```

## 6. Record Response Times Manually

For benchmark reporting:

1. Run each query at least three times after the dataset is loaded.
2. Record the elapsed time shown by the Fuseki UI or by your command-line timing wrapper.
3. Note whether the dataset contains only `math_accessibility_kg_seed.ttl`, seed plus JSON-LD gloss records, or the merged gloss TTL.
4. Record the machine, date, Fuseki version, dataset mode, query file, and response time.
5. Save benchmark notes under `reports/sparql/`.

Use the wording `Fuseki-ready` until Fuseki is actually running and the queries have been executed.
