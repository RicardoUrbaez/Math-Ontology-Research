# 4.1 Data Sources

This project begins with four seed mathematical ontology and knowledge resources: OntoMathPRO, MaRDI MathModDB, OpenMath Content Dictionaries, and OntoMathEdu. These resources were selected because they cover complementary parts of mathematical knowledge, including formal mathematical concepts, mathematical models, symbolic content dictionaries, and educational mathematical terminology.

## OntoMathPRO

OntoMathPRO is used as a broad mathematical ontology seed resource. The local source file is preserved at `ontologies/raw/OntoMathPro.omn`. The file was downloaded from the CLLKazan/OntoMathPro GitHub repository and is stored in OMN / Manchester OWL Syntax form. Provenance for the local copy is therefore clear at the repository level, and the project notes record the source repository as the acquisition point. The repository notes also indicate an Apache-2.0 license for this resource. ROBOT was used to generate a first-pass ontology measure file at `reports/summaries/ontomathpro_measure.tsv` and a report file at `reports/robot_reports/ontomathpro_report.tsv`.

OntoMathPRO is useful because it contains many mathematical concepts across areas such as algebra, analysis, geometry, probability, and applied mathematics. It also provides many English `rdfs:label` annotations that are useful for concept matching and accessibility-oriented labels. A known limitation is that the ontology contains many report warnings and duplicate or multilingual labels, so later merge work must be careful about exact concept identity and label normalization.

## MaRDI MathModDB

MaRDI MathModDB is used as a seed resource for mathematical models, mathematical formulations, quantities, variables, and modeling-related concepts. The local source file is preserved at `ontologies/raw/MathModDB.owl` in OWL format. The local copy was obtained from the MaRDI4NFDI/MathModDB GitHub repository, which provides clear provenance for the Week 1 source audit. Project notes record the license as CC-BY-4.0. ROBOT was used to generate a measure file at `reports/summaries/mathmoddb_measure.tsv` and a report file at `reports/robot_reports/mathmoddb_report.tsv`.

MathModDB is especially useful for connecting mathematical concepts to modeling contexts, such as equations, variables, constants, coefficients, matrices, vectors, and scientific model components. A known limitation is that many entries are model-specific individuals rather than general mathematical classes, so merge decisions must distinguish broad mathematical concepts from application-specific model terms.

## OpenMath Content Dictionaries

The OpenMath Content Dictionaries are used as a seed resource for symbolic mathematical content. The local downloaded folder is preserved at `ontologies/raw/openmath-cds/`. The source provenance is the OpenMath/CDs repository, which was downloaded and retained locally as a directory tree of XML content dictionaries. The files are organized as XML CDs rather than normal OWL ontology files. Because of this structural difference, standard ROBOT measure and report commands were not generated for OpenMath during the first pass. License details were not fully recorded during Week 1 and should be confirmed from the repository metadata in a later documentation pass.

OpenMath is still important because it provides formal symbolic vocabulary for arithmetic, relations, sets, linear algebra, calculus, trigonometry, and other mathematical areas. For example, OpenMath CDs include entries for arithmetic operations, equality and inequality relations, set membership, matrices, vectors, integers, and calculus-related concepts. A known limitation is that XML-to-RDF conversion is required before OpenMath can be loaded and queried in the same way as the OWL/OMN resources.

## OntoMathEdu

OntoMathEdu is used as a seed resource for educational mathematical terminology. The official raw source file is preserved at `ontologies/raw/OntoMathEdu.omn` and was downloaded from the CLLKazan/OntoMathEdu GitHub repository. This preserves clear provenance for the authoritative source file. The resource is stored in OMN / Manchester OWL Syntax form. License details were not fully recorded during Week 1 and should be confirmed from the repository metadata in a later documentation pass. ROBOT and Protégé initially failed to parse the official `.omn` file directly because of Manchester syntax compatibility issues involving `DisjointUnionOf:` blocks. To preserve provenance, the original raw file was left unchanged. A cleaned copy was created at `ontologies/converted/OntoMathEdu_clean.omn`, and a repaired working copy was created at `ontologies/converted/OntoMathEdu_repaired_v2.omn` by removing the `DisjointUnionOf:` blocks that prevented automated parsing.

The repaired working copy successfully generated ROBOT outputs at `reports/summaries/ontomathedu_measure.tsv` and `reports/robot_reports/ontomathedu_report.tsv`. OntoMathEdu is useful because it contains education-oriented concepts and theorem/axiom labels that support accessibility and student-facing mathematical explanations. A known limitation is that the repaired copy is used only for automated first-pass analysis, while the original raw source remains the authoritative provenance file.

## Summary of source status

| Source | Local path | Format | ROBOT output status | Provenance / license notes | Known limitations |
|---|---|---|---|---|
| OntoMathPRO | `ontologies/raw/OntoMathPro.omn` | OMN / Manchester OWL Syntax | Measure and report generated | Downloaded from CLLKazan/OntoMathPro; Apache-2.0 noted in project source notes | Duplicate or multilingual labels and report warnings require careful normalization |
| MaRDI MathModDB | `ontologies/raw/MathModDB.owl` | OWL | Measure and report generated | Downloaded from MaRDI4NFDI/MathModDB; CC-BY-4.0 noted in project source notes | Many entries are model-specific individuals rather than general math classes |
| OpenMath Content Dictionaries | `ontologies/raw/openmath-cds/` | XML CDs | Not generated yet | Downloaded from OpenMath/CDs; exact license record still needs confirmation in project notes | Requires XML-to-RDF conversion before ROBOT-style analysis or Fuseki loading |
| OntoMathEdu | `ontologies/raw/OntoMathEdu.omn` and `ontologies/converted/OntoMathEdu_repaired_v2.omn` | OMN / Manchester OWL Syntax | Measure and report generated from repaired copy | Downloaded from CLLKazan/OntoMathEdu; exact license record still needs confirmation in project notes | Official raw OMN file failed ROBOT/Protégé parsing until a repaired working copy was created |

These four sources form the first layer of the project’s math accessibility knowledge graph. The Week 1 source audit established local provenance, first-pass quality reports, and a 50-concept validation set for testing merge decisions in later stages.
