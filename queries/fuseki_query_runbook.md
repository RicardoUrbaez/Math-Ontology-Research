# Fuseki SPARQL Query Runbook

This guide records how to start Apache Jena Fuseki, load the Math Accessibility Knowledge Graph ontology, and run the Week 3 SPARQL evidence queries.

## Start Fuseki

1. Open the Fuseki folder:

   `C:\Users\Ricardo\Downloads\apache-jena-fuseki-6.1.0`

2. Run:

   `fuseki-server.bat`

3. Keep the command window open.

4. Open the Fuseki web interface in a browser:

   `http://localhost:3030`

## Dataset

Use the polished seed dataset:

`mathkg`

If the dataset does not exist:

1. Click **add one**.
2. Name the dataset `mathkg`.
3. Choose **Persistent** if asked.
4. Click **Create dataset**.

## Load The Ontology

In Fuseki:

1. Open dataset `/mathkg`.
2. Click **add data**.
3. Upload:

   `C:\Users\Ricardo\Documents\Math-Ontology-Research\ontologies\merged\math_accessibility_kg_seed.owl`

4. If Fuseki asks for a graph name and does not accept a blank value, use:

   `http://example.org/mathkg`

5. Confirm the upload reports more than 0 triples. The Week 3 upload showed 1033 triples.

## Optional 500-Concept Expansion Dataset

For the 500-concept expansion evidence, use a separate dataset so the polished 50-concept seed evidence stays clean.

Dataset name:

`mathkg500`

Load this cleaned file:

`C:\Users\Ricardo\Documents\Math-Ontology-Research\reports\reasoning\math_accessibility_kg_week3_clean.ttl`

If Fuseki asks for a graph name, use:

`http://example.org/mathkg500`

The cleaned 500-concept expansion upload used in the Week 3 closeout contained 6952 triples. The 10 query response-time results were recorded at:

`C:\Users\Ricardo\Documents\Math-Ontology-Research\reports\sparql\week3_fuseki_query_results_mathkg500.csv`

## Queries To Run

Open the **query** tab for `/mathkg`, then copy/paste queries from:

`C:\Users\Ricardo\Documents\Math-Ontology-Research\queries`

Recommended evidence queries:

1. `01_list_all_concepts.rq`
   - Shows local concepts, labels, and definitions.
   - Expected evidence: concept rows such as Addition, Equation, Matrix, Set.

2. `04_kind_role_lookup.rq`
   - Shows kind/role classification.
   - Expected evidence: `kindRole` values such as `kind` and role values where applicable.

3. `05_provenance_trace.rq`
   - Shows source ontology, source IRI, and mapping quality.
   - Expected evidence: sources such as OntoMathPRO, MathModDB, OpenMath Content Dictionaries, plus `canonical_match` or provisional mapping values.

4. `06_relation_properties.rq`
   - Shows the MathRelation object-property hierarchy.
   - Expected evidence: properties such as `has element`, `is element of`, `is subset of`, `has operand`, and `has result`.

Optional audit queries:

- `02_concepts_missing_definitions.rq`
- `03_concepts_by_type.rq`
- `07_alt_labels_synonyms.rq`
- `08_accessibility_notes.rq`
- `09_provisional_mappings.rq`
- `10_hierarchy_traversal.rq`

## Evidence To Save

Save screenshots showing:

- Fuseki dataset `/mathkg`.
- Ontology upload with triples uploaded.
- Query 1 results.
- Query 4 kind/role results.
- Query 5 provenance trace results.
- Optional: Query 6 relation-property results.

Suggested evidence folder:

`C:\Users\Ricardo\Documents\Math-Ontology-Research\reports\protege_screenshots`

## Week 3 Status Note

The SPARQL/Fuseki requirement is satisfied for the polished seed ontology when `/mathkg` is loaded and the starter queries return results. The 500-concept expansion was also tested separately in `/mathkg500`; keep that evidence separate from the seed ontology screenshots.
