# Week 3 SPARQL Benchmark Status

The 10-query benchmark suite has been written to `reports/sparql/week3_benchmark_queries.rq`, and the professor-facing starter query set has been written to `queries/`.

The ontology was loaded into Apache Jena Fuseki under dataset `/mathkg`, and all 10 starter queries in `queries/` were run against:

`http://localhost:3030/mathkg/query`

The Fuseki response-time results were saved at:

`reports/sparql/week3_fuseki_query_results.csv`

The same starter query suite was also run against the cleaned 500-concept expansion dataset:

`http://localhost:3030/mathkg500/query`

That dataset was loaded from:

`reports/reasoning/math_accessibility_kg_week3_clean.ttl`

The 500-concept Fuseki response-time results were saved at:

`reports/sparql/week3_fuseki_query_results_mathkg500.csv`

The earlier local static TTL timing sanity check remains available at:

`reports/sparql/week3_benchmark_results.csv`
