# Week 3 NER Corpus Pipeline Status

- Downloaded 200 arXiv math.* metadata records from https://export.arxiv.org/api/query?search_query=cat%3Amath%2A&start=0&max_results=200&sortBy=submittedDate&sortOrder=descending
- The local Python environment does not include spaCy, so this run used a deterministic MathEntRuler-compatible lexical rule set.
- The corpus artifact stores arXiv paper metadata, abstracts, categories, and PDF URLs for 200 open-access math.* records when the arXiv API is reachable.
- Usage-context glosses are extracted from titles and abstracts in this local run; full-PDF text extraction can be added by downloading the recorded PDF URLs.
- Extracted usage-context rows: 1031.
- Top-symbol rows: 100.
