# Data Sources Notes

Placeholder notes for documenting ontology data sources, provenance, licensing, and acquisition details for the math ontology accessibility study.

## OntoMathPRO

Source: CLLKazan/OntoMathPro GitHub repository  
File downloaded: OntoMathPro.omn  
Local path: ontologies/raw/OntoMathPro.omn  
Format: OMN / OWL Manchester Syntax  
License: Apache-2.0  
Purpose: Mathematical ontology / Linked Data Hub for mathematics  
Notes: Used as one of the seed ontology resources for the math accessibility knowledge graph project.
Source URL: https://github.com/CLLKazan/OntoMathPro


ROBOT measure output: reports/summaries/ontomathpro_measure.tsv  

ROBOT report output: reports/robot_reports/ontomathpro_report.tsv 


Initial ROBOT findings: The ontology was readable by ROBOT. The report identified many quality-control violations, especially duplicate rdfs:label entries and a deprecated boolean datatype issue. These issues should be documented as known limitations for the seed ontology.



## MaRDI MathModDB

Source: MaRDI4NFDI/MathModDB GitHub repository  
Source URL: https://github.com/MaRDI4NFDI/MathModDB  
File downloaded: MathModDB.owl  
Local path: ontologies/raw/MathModDB.owl  
Format: OWL  
License: CC-BY-4.0  
Purpose: Model ontology and knowledge graph for mathematical modelling  
Notes: Used as one of the seed ontology resources for the math accessibility knowledge graph project.





ROBOT measure output: reports/summaries/mathmoddb_measure.tsv  
Initial ROBOT measure findings: ROBOT successfully read the ontology. The ontology contains 18,035 axioms, 8 classes, 51 object properties, 11 data properties, 31 annotation properties, and 1,418 individuals. The ontology IRI is https://mardi4nfdi.de/mathmoddb with version IRI https://mardi4nfdi.de/mathmoddb/1.0.0. ROBOT reports that this file is not OWL 2 DL, with profile violations involving defined datatypes, reserved vocabulary use, and an unknown datatype.


ROBOT measure output: reports/summaries/mathmoddb_measure.tsv  
ROBOT report output: reports/robot_reports/mathmoddb_report.tsv  
Initial ROBOT findings: ROBOT successfully read the ontology and generated both measure and report files. The measure output shows 18,035 axioms, 8 classes, 51 object properties, 11 data properties, 31 annotation properties, and 1,418 individuals. The report identified 218 total violations: 134 errors, 77 warnings, and 7 informational issues. Major findings include multiple rdfs:label values caused by multilingual labels, missing definitions using IAO:0000115, and missing superclass relationships for several top-level classes. The ontology is useful as a seed resource but should be documented as not fully OWL 2 DL according to ROBOT profile checks.


## OpenMath Content Dictionaries

Source: OpenMath/CDs GitHub repository  
Source URL: https://github.com/OpenMath/CDs  
File downloaded: OpenMath CDs repository ZIP, extracted as openmath-cds  
Local path: ontologies/raw/openmath-cds  
Format: XML Content Dictionaries  
License: To be confirmed from repository files  
Purpose: Collection of OpenMath Content Dictionaries defining mathematical symbols, names, descriptions, and rules  
Notes: Used as one of the seed resources for the math accessibility knowledge graph project. Unlike OntoMathPRO and MathModDB, this resource is not directly an OWL ontology file. It is a collection of XML content dictionary files, so it will require XML-to-RDF conversion before loading into Fuseki or running ontology-style ROBOT checks.

## OntoMathEdu

Source: CLLKazan/OntoMathEdu GitHub repository  
Source URL: https://github.com/CLLKazan/OntoMathEdu  
File downloaded: OntoMathEdu.omn  
Local path: ontologies/raw/OntoMathEdu.omn  
Format: OMN / OWL Manchester Syntax  
License: To be confirmed from repository files  
Purpose: Educational mathematical ontology focused on linguistically grounded math concepts  
Notes: Used as one of the seed ontology resources for the math accessibility knowledge graph project.

ROBOT measure output: Not generated  
ROBOT report output: Not generated  
Initial ROBOT/Protégé findings: The OntoMathEdu.omn file was downloaded successfully and appears to contain ontology-style Manchester syntax text, but ROBOT could not load it as a valid ontology file. Protégé also failed to parse the file when opened directly, reporting that the ontology could not be parsed. This seed resource should be documented as requiring further format cleanup, re-download verification, or manual conversion before it can be measured, converted, or loaded into Fuseki.

## OntoMathEdu

Source: CLLKazan/OntoMathEdu GitHub repository  
Source URL: https://github.com/CLLKazan/OntoMathEdu  
File downloaded: OntoMathEdu.omn  
Local path: ontologies/raw/OntoMathEdu.omn  
Format: OMN / OWL Manchester Syntax  
License: To be confirmed from repository files  
Purpose: Educational mathematical ontology focused on linguistically grounded math concepts  
Notes: Used as one of the seed ontology resources for the math accessibility knowledge graph project.

ROBOT measure output: Not generated from official OMN file  
ROBOT report output: Not generated from official OMN file  
Initial findings: The official OntoMathEdu file was downloaded from the CLLKazan/OntoMathEdu GitHub repository and saved as `ontologies/raw/OntoMathEdu.omn`. The file was also re-downloaded directly from GitHub using `curl.exe` to confirm that the issue was not caused by a browser download problem. The file appears to contain ontology-style Manchester syntax text, but both ROBOT and Protégé failed to parse the official `.omn` file directly. ROBOT verbose output identified a Manchester syntax parsing issue involving `DisjointUnionOf:`. The original raw file will remain preserved, and an official alternate serialization or controlled preprocessing step should be explored before using this source for automated ROBOT/Fuseki analysis.


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
| OntoMathPRO | ontologies/raw/OntoMathPro.omn | OMN / Manchester OWL Syntax | Generated | Generated | Usable for first-pass analysis |
| MaRDI MathModDB | ontologies/raw/MathModDB.owl | OWL | Generated | Generated | Usable for first-pass analysis |
| OpenMath Content Dictionaries | ontologies/raw/openmath-cds | XML Content Dictionaries | Not applicable yet | Not applicable yet | Requires XML-to-RDF conversion |
| OntoMathEdu | ontologies/raw/OntoMathEdu.omn | OMN / Manchester OWL Syntax | Not generated | Not generated | Official file downloaded, but ROBOT/Protégé parsing failed |

## Notes

OntoMathEdu was downloaded from the official CLLKazan/OntoMathEdu GitHub repository. The file was also re-downloaded directly from GitHub using curl to verify that the issue was not caused by browser download corruption. ROBOT verbose output identified a Manchester syntax parsing issue involving `DisjointUnionOf:`. The original raw file is preserved, and an official alternate serialization or controlled preprocessing step should be explored before automated analysis.

ROBOT measure output: reports/summaries/ontomathedu_measure.tsv  
ROBOT report output: reports/robot_reports/ontomathedu_report.tsv  
Initial findings: The official OntoMathEdu file was downloaded from the CLLKazan/OntoMathEdu GitHub repository and preserved unchanged at `ontologies/raw/OntoMathEdu.omn`. ROBOT and Protégé initially failed to parse the official `.omn` file directly. ROBOT verbose output identified Manchester syntax parsing issues involving `DisjointUnionOf:` blocks. To support first-pass automated analysis, a cleaned copy was created at `ontologies/converted/OntoMathEdu_clean.omn`, then a repaired working copy was created at `ontologies/converted/OntoMathEdu_repaired_v2.omn` by removing `DisjointUnionOf:` blocks that prevented ROBOT parsing. The repaired working copy successfully generated ROBOT measure and report outputs. The ROBOT report identified 4,017 total violations: 3,076 errors, 937 warnings, and 4 informational issues. The original raw source remains preserved for provenance.





