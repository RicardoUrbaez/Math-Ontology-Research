# MathOntoSpeak Tools and Software Flow

This document summarizes the software pipeline behind the evaluation and poster figures.

```mermaid
flowchart LR
    A["Source ontologies<br/>OntoMathPRO, OpenMath,<br/>MathModDB, OntoMathEdu"] --> B["RDF/OWL processing<br/>rdflib + ROBOT/HermiT"]
    B --> C["Merged Math Accessibility KG<br/>TTL, RDF/XML, JSON-LD"]
    C --> D["SPARQL benchmark<br/>Apache Jena Fuseki"]
    C --> E["Gloss dictionary<br/>JSON + CSV metadata"]
    E --> F["Rendering pipeline<br/>Python, pylatexenc, SSML"]
    F --> G["TTS audio generation<br/>gTTS + Azure Speech"]
    C --> H["FastAPI service<br/>semantic search + accessibility endpoints"]
    D --> I["Evaluation outputs<br/>CSV tables + figures"]
    G --> I
    E --> I
    I --> J["Paper and poster<br/>Sections 5-6 + figures"]
```

## Tool Roles

| Stage | Main tools/software | Project artifacts |
|---|---|---|
| Ontology integration | RDF/OWL, rdflib, ROBOT, HermiT | `ontologies/merged/math_accessibility_kg_merged_gloss.ttl` |
| Knowledge graph query | Apache Jena Fuseki, SPARQL | `reports/sparql/week3_fuseki_query_results_mathkg500.csv` |
| Gloss and perspective metadata | Python, JSON, CSV | `gloss/week3_gloss_dictionary.json` |
| Speech rendering | Python, pylatexenc, SSML | `src/mathontospeak/`, `outputs/ssml/` |
| Audio generation | gTTS, Azure Speech | `reports/audio/`, `study/audio/` |
| API layer | FastAPI, Uvicorn | `api/main.py`, `api/services.py` |
| Evaluation analysis | Python, SciPy, openpyxl, Matplotlib | `reports/evaluation/`, `figures/` |
| Paper/poster writing | Markdown, PNG/SVG figures | `paper/section_5_evaluation.md`, `paper/section_6_discussion.md` |

## Poster Takeaway

The system is not only a TTS script. It is a linked-data workflow: source ontologies are merged into a provenance-tagged knowledge graph, the graph supports SPARQL/API lookup, and each concept can be rendered through multiple surface-form perspectives for accessible speech.
