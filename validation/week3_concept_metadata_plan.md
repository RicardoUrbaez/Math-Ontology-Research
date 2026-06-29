# Week 3 Concept Metadata Plan

## Purpose

Week 3 enriches the current seed ontology with human-readable and machine-queryable metadata. Labels, definitions, examples, provenance, mapping quality, concept type, kind/role classification, and accessibility notes make the ontology easier to inspect in Protege, easier to query with SPARQL, and easier to reuse later for semantic speech and gloss generation.

## Pilot Set and Expansion Target

The current 50 concepts are the pilot and validation subset. Week 2 already validated that these 50 concepts are present, mapped, classified, and provenance-tagged. Week 3 and the next phase enrich those same 50 concepts first, then extend the same metadata pattern toward the future 500-concept target.

## Visualization and Querying

Protege is the primary manual inspection and visualization tool. The Classes tab should show MathObject and MathOperation, the Object properties tab should show MathRelation, and OntoGraf or OWLViz can be used to visualize selected concept neighborhoods. SPARQL queries will be used in Apache Jena Fuseki to audit metadata, retrieve definitions, inspect hierarchy branches, trace provenance, and support future accessibility endpoints.

## Metadata Layer

Each concept should include:

- `rdfs:label`
- `skos:definition`
- `skos:altLabel`
- `skos:example`
- `dc:source` or `dcterms:source`
- `skos:exactMatch` when a canonical source IRI is confirmed
- concept type
- kind/role classification
- mapping quality
- provenance notes
- accessibility notes
- review status

The seed ontology declares local annotation properties for project-specific fields: `mathkg:conceptType`, `mathkg:kindRoleClassification`, `mathkg:mappingQuality`, `mathkg:provenanceNote`, `mathkg:accessibilityNote`, and `mathkg:reviewStatus`.
