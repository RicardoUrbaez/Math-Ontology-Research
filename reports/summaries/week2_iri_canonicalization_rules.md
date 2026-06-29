# Week 2 IRI Canonicalization Rules

## Purpose

This document defines the IRI canonicalization rules for the Week 2 merge/alignment stage of the Math Accessibility Knowledge Graph project. The goal is to merge duplicate or overlapping mathematical concepts from four seed resources while preserving provenance and keeping the merged ontology organized under an OWL 2 DL-compatible hierarchy.

## Seed resources

The four seed resources are:

1. OntoMathPRO
2. MaRDI MathModDB
3. OpenMath Content Dictionaries
4. OntoMathEdu

## Canonical IRI rule

OntoMathPRO IRIs are treated as canonical when a matching OntoMathPRO concept exists. This means that if the same concept appears in OntoMathPRO and another source, the OntoMathPRO IRI becomes the preferred canonical identifier for the merged concept.

Example:

If `Vector` appears in OntoMathPRO, MathModDB, OntoMathEdu, and OpenMath, the OntoMathPRO IRI should be used as the canonical IRI when the OntoMathPRO concept is semantically equivalent to the other source concepts.

## Fallback canonical IRI rules

If no OntoMathPRO IRI exists for a concept, use the following priority order:

1. MathModDB IRI
2. OntoMathEdu IRI
3. OpenMath identifier converted into a project-local IRI

For OpenMath concepts, use a project-local IRI pattern such as:

`http://example.org/mathkg/openmath/{cd_name}/{symbol_name}`

This is temporary and may be replaced later with a final project namespace.

## Equivalence decision rules

Use `owl:equivalentClass` only when two source concepts are semantically the same mathematical concept.

Use `skos:closeMatch` or a review note instead of `owl:equivalentClass` when concepts are related but not exactly identical.

Examples:

- `Vector` in OntoMathPRO and `Vector` in OntoMathEdu may be equivalent if both describe the same mathematical object.
- `Formula` and `MathematicalFormulation` should not automatically be marked equivalent because the meanings may differ.
- `Element` should be reviewed carefully because it may mean set membership in one source and finite element/model element in another.

## Provenance rule

Every merge decision must record where the concept came from. Use provenance notes in the mapping table and later add `dc:source` annotations in the merged ontology.

Each mapping should record:

- canonical source
- contributing source or sources
- source labels
- source IRIs or identifiers
- merge decision
- review notes

## Three-branch class hierarchy

The merged ontology will use three top-level branches:

1. `MathObject`
   - Rigid mathematical objects and concepts
   - Examples: Set, Number, Matrix, Vector, Equation, Polynomial

2. `MathRelation`
   - Mathematical relations and predicates
   - Examples: Equality, Inequality, Subset

3. `MathOperation`
   - Mathematical operations or processes
   - Examples: Addition, Multiplication, Integral, Derivative

## Validation rule

The merged ontology must be checked against the 50-concept validation set stored at:

`validation/50_concept_validation_set.csv`

Each of the 50 validation concepts should eventually be:

- present in the merged ontology
- assigned to one of the three top-level branches
- connected to source provenance
- mapped to equivalent or related source concepts when appropriate

## Conflict logging rule

Any uncertain mapping must be logged instead of forced.

Examples of mappings that should be logged for review:

- Formula vs MathematicalFormulation
- Element as set membership vs finite/model element
- Tangent as trigonometric function vs tangent line
- Graph as graph-theory object vs plotted graph

## Current Week 2 starting point

The Week 1 validation set contains 50 concepts:

- 18 verified
- 10 needs_review
- 22 candidate

Week 2 will use this file as the starting point for canonical IRI mapping, merge decisions, and validation.