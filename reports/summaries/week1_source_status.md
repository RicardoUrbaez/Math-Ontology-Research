# Week 1 Source Status Summary

## Completed setup

- Java JDK installed and verified.
- Protégé installed and verified.
- ROBOT installed and verified.
- Apache Jena Fuseki installed and tested locally.
- VS Code project structure created.

## Seed ontology/resource status

| Source | Local File/Folder | Format | ROBOT Measure | ROBOT Report | Status |
|---|---|---|---|---|---|
| OntoMathPRO | `ontologies/raw/OntoMathPro.omn` | OMN / Manchester OWL Syntax | `reports/summaries/ontomathpro_measure.tsv` | `reports/robot_reports/ontomathpro_report.tsv` | Usable for first-pass analysis |
| MaRDI MathModDB | `ontologies/raw/MathModDB.owl` | OWL | `reports/summaries/mathmoddb_measure.tsv` | `reports/robot_reports/mathmoddb_report.tsv` | Usable for first-pass analysis |
| OpenMath Content Dictionaries | `ontologies/raw/openmath-cds/` | XML Content Dictionaries | Not generated yet | Not generated yet | Requires XML-to-RDF conversion |
| OntoMathEdu | `ontologies/raw/OntoMathEdu.omn` | OMN / Manchester OWL Syntax | `reports/summaries/ontomathedu_measure.tsv` | `reports/robot_reports/ontomathedu_report.tsv` | Usable through repaired working copy |

## OntoMathEdu preprocessing note

The official OntoMathEdu source file is preserved unchanged at `ontologies/raw/OntoMathEdu.omn`. ROBOT and Protégé initially failed to parse the official `.omn` file directly because of Manchester syntax compatibility issues involving `DisjointUnionOf:` blocks. A cleaned copy was created at `ontologies/converted/OntoMathEdu_clean.omn`, and a repaired working copy was created at `ontologies/converted/OntoMathEdu_repaired_v2.omn` by removing the `DisjointUnionOf:` blocks that prevented automated parsing. The repaired copy successfully generated ROBOT measure and report outputs. The original raw file remains preserved for provenance.

## Current status

The first-pass source setup is complete for OntoMathPRO, MathModDB, and OntoMathEdu. OpenMath Content Dictionaries are downloaded and preserved, but they require XML-to-RDF conversion before ROBOT-style ontology analysis or Fuseki loading.
