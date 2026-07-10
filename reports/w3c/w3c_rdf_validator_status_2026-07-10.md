# W3C RDF Validator Status

Date: 2026-07-10

## Result

The W3C RDF Validator accepted the reduced RDF/XML validation sample and returned:

```text
Validation Results
Your RDF document validated successfully.
```

Raw validator output was saved at:

```text
reports/w3c/w3c_rdf_validator_tiny_sample_success_2026-07-10.txt
```

## Validated Sample

Validated sample file:

```text
reports/w3c/math_accessibility_kg_merged_gloss_w3c_tiny_sample.rdf
```

Sample size:

```text
500 RDF triples
93,127 bytes
```

## Full Export Validation

The full merged ontology/gloss export is larger than the W3C direct-input form limit, so the validator rejected full-file paste attempts with `Form too large`.

This was a validator form-size limitation, not an RDF syntax failure.

The full exports were validated locally with `rdflib`:

```text
RDF/XML: 13,986 triples
Turtle: 13,986 triples
JSON-LD: 13,986 triples
```

Full export files:

```text
ontologies/merged/math_accessibility_kg_merged_gloss.rdf
ontologies/merged/math_accessibility_kg_merged_gloss.ttl
ontologies/merged/math_accessibility_kg_merged_gloss.jsonld
```

## Publication Note

After the repository is pushed publicly, the full RDF/XML export can be checked again using the validator's `Check by URI` option with the raw GitHub URL. The current manual evidence is sufficient to document W3C parser compatibility on a representative RDF/XML sample while local validation covers the full graph.
