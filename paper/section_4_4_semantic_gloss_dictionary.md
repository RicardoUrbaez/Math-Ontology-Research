# 4.4 Semantic Gloss Dictionary

The semantic gloss dictionary is built as a three-pipeline architecture. First, the ontology annotation pipeline supplies canonical labels, definitions, kind/role status, semantic type, domain tags, and provenance. Second, a template pipeline rewrites each concept into four surface forms: concise, pedagogical, expert, and document-role. Third, a corpus pipeline collects usage contexts from arXiv math.* records so the project can later refine glosses using real mathematical prose.

The current dictionary is stored in `gloss/week3_gloss_dictionary.json` and `gloss/week3_gloss_dictionary.csv`. Each record follows the planned schema: `concept_IRI`, `canonical_gloss`, `concise_form`, `pedagogical_form`, `expert_form`, `document_role_form`, `domain_tags`, and `source_provenance`. The rewrite templates are stored separately at `gloss/week3_rewrite_templates.json` so the speech layer can update templates without rewriting the ontology.

The local environment did not include spaCy, so the corpus run used a deterministic MathEntRuler-compatible lexical matcher over arXiv titles and abstracts. The corpus status file records the exact extraction mode and the number of usage-context rows produced.

The mentor review for 50 sampled gloss records is handled through a Teams meeting. The project records the review criteria and meeting outcome in `validation/week3_teams_mentor_review_record.md`, with the current agreement status summarized in `validation/week3_inter_rater_agreement_status.md`. Inter-rater agreement should be reported from the Teams meeting notes or mentor-provided scoring summary rather than fabricated from project artifacts.
