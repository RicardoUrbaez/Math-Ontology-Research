# Week 6 System Evaluation Table

| Evaluation area | Metric | Result | Evidence source | Notes |
|---|---:|---:|---|---|
| Ontology coverage | Classes | 504 | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl` | OWL class count in merged gloss TTL. |
| Ontology coverage | Properties | 13 | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl` | Declared RDF/OWL property count. |
| Ontology coverage | Axioms/statements | 13,986 | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl` | RDF triples used as axiom-like statements. |
| Ontology coverage | Provenance-tagged classes | 500 | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl` | Classes with source/provenance annotation. |
| SPARQL benchmark | Completed benchmark queries | 10 | `reports/sparql/week3_fuseki_query_results_mathkg500.csv` | Local Fuseki `/mathkg500` benchmark. |
| SPARQL benchmark | Mean response time | 52.359 ms | `reports/sparql/week3_fuseki_query_results_mathkg500.csv` | Average across benchmark queries. |
| SPARQL benchmark | Max response time | 170.884 ms | `reports/sparql/week3_fuseki_query_results_mathkg500.csv` | Slowest benchmark query. |
| Gloss agreement | Overall Cohen's kappa | 0.93 | `validation/week3_codex_two_pass_review_summary.md` | 50-record Codex two-pass QC agreement; not labeled as human mentor review. |
| Gloss agreement | Accuracy Cohen's kappa | 0.97 | `validation/week3_codex_two_pass_review_summary.md` | Agreement on gloss accuracy labels. |
| Gloss agreement | Naturalness Cohen's kappa | 0.90 | `validation/week3_codex_two_pass_review_summary.md` | Agreement on naturalness labels. |
| Gloss agreement | Cross-domain Cohen's kappa | 0.91 | `validation/week3_codex_two_pass_review_summary.md` | Agreement on cross-domain correctness labels. |
| TTS audio quality | Audio artifact sets passed | 4/4 | `reports/evaluation/week6_tts_audio_quality_qc.csv` | All expected audio artifact sets were present. |
| TTS audio quality | Mean TTS audio quality rating | 5.00 / 5 | `reports/evaluation/week6_tts_audio_quality_qc.csv` | 0-5 rating over expected audio files. |

## Paper/Poster Summary

The system evaluation shows that MathOntoSpeak integrates a 504-class, provenance-tagged mathematical knowledge graph with low-latency SPARQL access, high internal gloss-review agreement, and complete generated TTS audio artifacts. Together, these results support the claim that the system is an end-to-end multi-perspective KG pipeline rather than only a notation-to-speech script.
