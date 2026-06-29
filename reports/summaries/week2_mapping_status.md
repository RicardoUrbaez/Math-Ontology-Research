# Week 2 Mapping Status

This note summarizes the current Week 2 cross-ontology mapping progress recorded in `validation/week2_cross_ontology_mapping_table.csv`.

- Mapping table file: `validation/week2_cross_ontology_mapping_table.csv`
- Total mapped concept rows reviewed: 18
- Current `merge_status` counts: 17 `mapped`, 1 `needs_review`

OntoMathPRO IRIs were used as canonical IRIs when exact or defensible matches were found in the Week 2 review process. This follows the canonicalization rule that prioritizes OntoMathPRO as the preferred source when a matching concept can be justified semantically.

The only concept still marked `needs_review` is `concept_019` (`Variable`). No exact, general `Variable` class was found in OntoMathPRO, OntoMathEdu, MathModDB, or OpenMath. The search results returned only narrower or contextual variable concepts, including Random Variable, Decision Variable, Spatial Variable, State Variable, `variable_of_integration`, and `indexed_variable`, so no canonical IRI has been assigned yet.

Several mappings still require later enrichment with OpenMath or MathModDB identifiers, especially for Integer, Polynomial, Integral, and other operation-oriented concepts where cross-source alignment has not yet been completed.

Integral was mapped to `mathematics:E1307` as the closest operation-level match because OntoMathPRO labels that class `Integrating@en` rather than `Integral@en`. This was treated as a defensible operation-level mapping rather than an exact label match.

Polynomial was mapped to `mathematics:E2920` using the Russian labels `Полином` and `Многочлен`, because no English `Polynomial@en` label was found in the current OntoMathPRO search results.