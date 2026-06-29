# 50-Concept Validation Set Status

## Purpose

This validation set is used to evaluate cross-ontology merge decisions for the math accessibility knowledge graph. The goal is to identify 50 important mathematical concepts that appear in at least two seed resources whenever possible.

## Current file

`validation/50_concept_validation_set.csv`

## Current status counts

| Status | Count | Meaning |
|---|---:|---|
| verified | 18 | Concept has clear evidence from at least two seed resources or strong cross-source support |
| needs_review | 10 | Concept has partial evidence but exact source mapping or IRI verification is still needed |
| candidate | 22 | Concept is included as a likely important concept but still requires verification |

Total concepts: 50

## Notes

The validation set is intentionally conservative. Concepts are marked as `verified` only when source evidence is strong. Concepts marked `needs_review` have partial support and are suitable for Week 2 merge testing, but they still require exact IRI confirmation. Concepts marked `candidate` remain part of the draft validation pool because they are likely important concepts that still need verification.

This Week 1 validation set is a valid draft deliverable. The Week 1 task is to build the 50-concept validation set, not to fully resolve every exact source IRI at this stage. Exact IRI mapping will continue in Week 2 during merge and alignment work.

## Current verified concepts

The verified group currently includes foundational mathematical objects, operations, number types, linear algebra concepts, and calculus/modeling concepts such as Set, Operation, Function, Number, Matrix, Vector, Equation, Integral, Variable, and Polynomial.

## Remaining work

Future validation work should record exact source IRIs for each verified concept, review partially supported concepts, and continue checking candidate concepts against OntoMathPRO, MathModDB, OntoMathEdu, and OpenMath Content Dictionaries.
