# Manual QC and Next Steps Runbook

Date: 2026-07-10

This runbook is for a step-by-step workflow where Codex checks the project, you run the manual/local pieces, then Codex reviews the output and updates the next step.

## Current QC Snapshot

Already present in the project:

- 8 rewrite templates: `gloss/week3_rewrite_templates.json`
- 500 structured gloss records: `gloss/week3_gloss_dictionary.json`
- 4 surface forms for all 500 records: `concise_form`, `pedagogical_form`, `expert_form`, `document_role_form`
- 500 concept metadata rows: `validation/week3_500_concept_metadata.csv`
- 200 arXiv math.* metadata rows: `reports/corpus/week3_arxiv_math_corpus_metadata.csv`
- 100 top-symbol rows: `reports/corpus/week3_top_100_symbols.csv`
- 1,031 title/abstract usage-context rows: `reports/corpus/week3_usage_context_glosses.csv`
- 50-record mentor review sample: `validation/week3_gloss_mentor_review_sample.csv`
- HermiT/ROBOT reasoning report with 0 unsatisfiable classes: `reports/reasoning/week3_reasoner_report.md`
- Passing local test suite: 17 tests passed in the current QC run

Not fully present yet:

- A real spaCy dependency in `requirements.txt`
- A full `MathEntRuler` spaCy component as its own reusable module
- Full PDF download and text extraction for the 200 arXiv papers
- A joined top-100 symbol usage-context table keyed by symbol, paper, and discipline
- Filled mentor review scores from two reviewers
- Computed inter-rater agreement from real paired reviewer scores
- Live Fuseki verification of the updated Week 3 hierarchy query after you start `/mathkg500`

## Round 1: You Verify the Local Project

Run these from PowerShell:

```powershell
cd C:\Users\Ricardo\Documents\Math-Ontology-Research
git status --short --branch
python -m compileall src scripts api
python -m pytest -q
```

Expected result:

- `compileall` finishes without syntax errors.
- `pytest` reports `17 passed`.
- `git status` will show existing modified and untracked files. That is expected right now; do not clean them unless we decide what should be kept.

Send Codex:

- the `pytest` summary line
- any error text if a command fails
- whether you want generated audio/log/report files kept or ignored before Git cleanup

## Round 2: Codex Checks Counts and Schema

Codex should run the project count/schema check and confirm:

- `gloss/week3_gloss_dictionary.json` has 500 records
- all 500 records have the required schema fields
- semantic types cover operator, relation, set, function, scalar, vector, matrix, and transformation
- `gloss/week3_rewrite_templates.json` has 8 templates
- corpus metadata has 200 rows
- top-symbol file has 100 rows
- usage-context file has 1,031 rows
- mentor sample has 50 rows and 0 scored rows

If any count changes after you rerun a generator, stop and let Codex inspect the diff before moving on.

## Round 3: You Run Fuseki Manually

This is external because it depends on a local Java/Fuseki process.

First check that Fuseki exists here:

```powershell
Test-Path C:\Users\Ricardo\Downloads\apache-jena-fuseki-6.1.0
```

If it returns `True`, start Fuseki:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_fuseki_mathkg.ps1
```

Then, in another PowerShell window, check the endpoint:

```powershell
Invoke-RestMethod http://localhost:3030/$/ping
```

If `/mathkg500` exists but has no data, load the cleaned ontology:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\load_fuseki_mathkg.ps1
```

Then run at least one query manually:

```powershell
curl.exe -X POST "http://localhost:3030/mathkg500/query" -H "Accept: application/sparql-results+json" --data-urlencode "query@queries/15_surface_forms_by_concept.rq"
```

Send Codex:

- whether Fuseki started
- whether `/mathkg500/query` returns results
- any error text from loading or querying

## Round 4: Codex Verifies the Updated Hierarchy Query

Codex has updated `queries/10_hierarchy_traversal.rq` for the current 500-concept ontology.

Target behavior:

- query `mathkg:KindConcept`
- query `mathkg:RoleConcept`
- return concept, label, kind-role type, and semantic type
- verify it against the running `/mathkg500` endpoint after Fuseki is available

Do not rerun all benchmarks until this query has been verified against Fuseki.

## Round 5: Codex Implements the Real Corpus Pipeline

This is the biggest not-yet-implemented piece.

Files likely to change:

- `requirements.txt`
- `scripts/week3_build_artifacts.py` or a new `src/mathontospeak/corpus_ner.py`
- maybe a new `scripts/run_corpus_ner.py`
- new output: `reports/corpus/week3_top_100_symbol_contexts.csv`

Implementation target:

- install/use spaCy
- create a custom `MathEntRuler`
- use the existing 200 arXiv metadata rows
- optionally download PDF files from recorded PDF URLs
- extract text from PDFs when available
- produce usage-context gloss records for the 100 highest-frequency symbols
- preserve source provenance: arXiv id, category, PDF URL, extraction rule, and text source

Codex has added the real spaCy runner at `scripts/run_corpus_ner.py`. Use Python 3.12 for this step because the repo's current default Python is 3.14 and spaCy is more reliable on the installed 3.12 runtime.

Create and activate a separate corpus environment:

```powershell
py -3.12 -m venv .venv-corpus
.\.venv-corpus\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

For a fast smoke test, run:

```powershell
python scripts\run_corpus_ner.py --max-papers 10 --limit-symbols 25
```

For the full 200-paper PDF-backed run, keep Fuseki separate and run:

```powershell
python scripts\run_corpus_ner.py --download-pdfs --max-papers 200 --limit-symbols 100 --pdf-max-pages 12
```

Expected outputs:

- `reports/corpus/week3_top_100_symbol_contexts.csv`
- `reports/corpus/week3_spacy_corpus_pipeline_status.md`
- cached PDFs under `data/arxiv_papers/`

## Round 6: You Run the Human Mentor Review

This cannot be automated honestly because it needs real human ratings.

Open:

```text
validation/week3_gloss_mentor_review_sample.csv
validation/week3_teams_mentor_review_record.md
```

For each of the 50 records, collect two reviewer scores for:

- accuracy
- naturalness
- cross-domain correctness

Use a simple 1 to 5 scale unless your mentor requires a different scale. Keep Reviewer A and Reviewer B separate.

Then fill:

```text
validation/week3_teams_mentor_review_record.md
```

Send Codex:

- the filled CSV
- the review notes
- the scoring scale used

## Round 7: Codex Computes Inter-Rater Agreement

After the human scores exist, Codex should compute agreement and update:

```text
validation/week3_inter_rater_agreement_status.md
```

Likely outputs:

- per-criterion exact agreement
- average absolute score difference
- Cohen's kappa if scores are categorical and the scale is consistent
- a short explanation of disagreements and follow-up edits

Do not claim this requirement is complete until two real reviewer score columns are filled.

## Round 8: Optional External Checks

Run these only if you need stronger professor-facing evidence.

ROBOT/HermiT rerun:

```powershell
java -jar C:\Robot\robot.jar convert --input reports\reasoning\math_accessibility_kg_week3_clean.ttl --input-format ttl --output reports\reasoning\math_accessibility_kg_week3_clean.owl
java -jar C:\Robot\robot.jar reason --reasoner HermiT --input reports\reasoning\math_accessibility_kg_week3_clean.owl --output reports\reasoning\week3_500_clean_hermit_classified.owl
java -jar C:\Robot\robot.jar report --input reports\reasoning\week3_500_clean_hermit_classified.owl --output reports\reasoning\week3_500_clean_metadata_report.tsv
```

FastAPI local check:

```powershell
python -m uvicorn api.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

Basic API check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/search?q=matrix&limit=5"
```

## Recommended Order From Here

1. You run Round 1 and send the output.
2. Codex verifies the updated Week 3 hierarchy query after Fuseki is running.
3. You start Fuseki and confirm `/mathkg500/query` works.
4. Codex verifies the updated query against Fuseki.
5. Codex implements the real spaCy/MathEntRuler corpus pipeline.
6. You install the new dependency and run the corpus pipeline.
7. You complete the mentor review with real scores.
8. Codex computes agreement and updates the status/report files.
9. Codex does final Git cleanup guidance after we decide which generated artifacts should be tracked.
