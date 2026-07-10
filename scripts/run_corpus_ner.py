from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mathontospeak.corpus_ner import (
    DEFAULT_GLOSS_PATH,
    DEFAULT_METADATA_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_PDF_DIR,
    DEFAULT_STATUS_PATH,
    DEFAULT_TOP_SYMBOLS_PATH,
    run_corpus_pipeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the spaCy MathEntRuler corpus extraction pipeline.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA_PATH))
    parser.add_argument("--top-symbols", default=str(DEFAULT_TOP_SYMBOLS_PATH))
    parser.add_argument("--gloss", default=str(DEFAULT_GLOSS_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--status", default=str(DEFAULT_STATUS_PATH))
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--max-papers", type=int, default=200)
    parser.add_argument("--limit-symbols", type=int, default=100)
    parser.add_argument("--pdf-max-pages", type=int, default=12)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--download-pdfs", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, stats = run_corpus_pipeline(
        metadata_path=Path(args.metadata),
        top_symbols_path=Path(args.top_symbols),
        gloss_path=Path(args.gloss),
        output_path=Path(args.output),
        status_path=Path(args.status),
        pdf_dir=Path(args.pdf_dir),
        max_papers=args.max_papers,
        limit_symbols=args.limit_symbols,
        download_pdfs=args.download_pdfs,
        pdf_max_pages=args.pdf_max_pages,
        model_name=args.model,
    )
    print(f"Wrote {len(rows)} symbol-context rows.")
    print(f"Documents processed: {stats['documents_processed']}")
    print(f"PDFs downloaded or cached: {stats['pdfs_downloaded_or_cached']}")
    print(f"PDF failures: {stats['pdfs_failed']}")


if __name__ == "__main__":
    main()
