# 4.2 Ontology Design

The Week 3 ontology layer extends the Week 2 seed merge from a 50-concept validation checkpoint to a 500-concept enrichment layer for math accessibility. The design keeps the Week 2 three-branch structure: mathematical objects and operations are represented as OWL classes, while relation-like links remain compatible with the object-property hierarchy used by the seed ontology.

The Week 3 layer is serialized at `ontologies/merged/math_accessibility_kg_week3.ttl`. Each target concept receives a stable local class, a canonical label, a definition, alternate labels, a usage example, source provenance, semantic type, and kind/role classification. The annotation layer is intentionally redundant because the downstream speech pipeline needs fast lookup for canonical names, learner-oriented explanations, expert formulations, and document-role descriptions.

The ontology avoids aggressive equivalence assertions for concepts whose identity is not yet fully confirmed across sources. Instead, source matches are recorded with `skos:exactMatch` where a source IRI is available and with provenance notes when a concept is retained because it belongs to the Week 2 validation set. This keeps the enrichment usable for retrieval while reducing the risk of unsafe cross-source merging.

A full HermiT run was not possible in this local workspace because HermiT and ROBOT were not installed. The local structural validation still confirms that the generated layer contains 500 target classes and does not introduce disjointness axioms that would make kind/role assignments unsatisfiable.
