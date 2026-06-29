# W3C RDF Validator Report

Date: 2026-06-29

## Artifacts

- Turtle: `ontologies/merged/math_accessibility_kg_merged_gloss.ttl`
- JSON-LD: `ontologies/merged/math_accessibility_kg_merged_gloss.jsonld`
- RDF/XML validator copy: `ontologies/merged/math_accessibility_kg_merged_gloss.rdf`
- Serializer: `scripts/serialize_merged_ontology_gloss.py`

## Local RDF Parse Validation

The generated Turtle, JSON-LD, and RDF/XML files were parsed with `rdflib 7.6.0`.

| Format | Triples | Gloss records | Concept-to-gloss links |
|---|---:|---:|---:|
| Turtle | 13,986 | 500 | 500 |
| JSON-LD | 13,986 | 500 | 500 |
| RDF/XML | 13,986 | 500 | 500 |

## W3C RDF Validator

The W3C RDF Validation Service is a legacy RDF/XML validator, so the generated RDF/XML copy of the same merged graph was validated by public URI after publication to GitHub.

Validator input URI:

`https://raw.githubusercontent.com/RicardoUrbaez/Math-Ontology-Research/main/ontologies/merged/math_accessibility_kg_merged_gloss.rdf`

Result:

`Your RDF document validated successfully.`

Notes:

- The Turtle and JSON-LD deliverables are the requested publication serializations.
- The RDF/XML file is included only to support the W3C validator's accepted input format.
- The first direct-input POST attempt returned a W3C server-side 500 response for the large RDF/XML payload, so the successful validation was performed through the validator's URI endpoint.
