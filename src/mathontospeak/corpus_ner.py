from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .gloss_record import GlossRecord, load_gloss_records


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA_PATH = ROOT / "reports" / "corpus" / "week3_arxiv_math_corpus_metadata.csv"
DEFAULT_TOP_SYMBOLS_PATH = ROOT / "reports" / "corpus" / "week3_top_100_symbols.csv"
DEFAULT_GLOSS_PATH = ROOT / "gloss" / "week3_gloss_dictionary.json"
DEFAULT_OUTPUT_PATH = ROOT / "reports" / "corpus" / "week3_top_100_symbol_contexts.csv"
DEFAULT_STATUS_PATH = ROOT / "reports" / "corpus" / "week3_spacy_corpus_pipeline_status.md"
DEFAULT_PDF_DIR = ROOT / "data" / "arxiv_papers"


DIRECT_SYMBOL_LABELS = {
    "=": "Equality",
    "+": "Addition",
    "-": "Subtraction",
    r"\times": "Multiplication",
    r"\cdot": "Multiplication",
    r"\sum": "Addition",
    r"\prod": "Multiplication",
    r"\frac": "Division",
    r"\int": "Integral",
    r"\lim": "Limit",
    r"\det": "Determinant",
    r"\partial": "Derivative",
    r"\sin": "Sine",
    r"\cos": "Cosine",
    r"\tan": "Tangent",
    r"\log": "Logarithm",
    r"\exp": "Exponential Function",
    r"\sqrt": "Function",
    r"\in": "Element",
    r"\le": "Inequality",
    r"\leq": "Inequality",
    r"\leqslant": "Inequality",
    r"\ge": "Inequality",
    r"\geq": "Inequality",
    r"\geqslant": "Inequality",
    r"\lesssim": "Inequality",
    r"\to": "Map",
    r"\mapsto": "Map",
    r"\cong": "Isomorphism",
    r"\cup": "Union",
    r"\forall": "Relation",
    r"\mathbb": "Set",
    r"\mathcal": "Set",
    "x": "Variable",
    "X": "Variable",
    "y": "Variable",
    "Y": "Variable",
    "z": "Variable",
    "Z": "Variable",
    "n": "Variable",
    "t": "Variable",
    "s": "Variable",
    "p": "Variable",
    "q": "Variable",
    "a": "Variable",
    "A": "Variable",
    "M": "Matrix",
}


@dataclass(frozen=True, slots=True)
class ArxivPaper:
    arxiv_id: str
    title: str
    categories: str
    abstract: str
    pdf_url: str


@dataclass(frozen=True, slots=True)
class SymbolFrequency:
    rank: int
    symbol: str
    frequency: int


@dataclass(frozen=True, slots=True)
class SymbolMention:
    symbol: str
    matched_text: str
    start_char: int
    end_char: int
    usage_context: str
    extraction_rule: str


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def load_arxiv_metadata(path: str | Path = DEFAULT_METADATA_PATH, max_papers: int | None = None) -> list[ArxivPaper]:
    rows: list[ArxivPaper] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                ArxivPaper(
                    arxiv_id=row["arxiv_id"],
                    title=clean_text(row["title"]),
                    categories=clean_text(row["categories"]),
                    abstract=clean_text(row["abstract"]),
                    pdf_url=clean_text(row["pdf_url"]),
                )
            )
            if max_papers and len(rows) >= max_papers:
                break
    return rows


def load_top_symbols(path: str | Path = DEFAULT_TOP_SYMBOLS_PATH, limit: int = 100) -> list[SymbolFrequency]:
    rows: list[SymbolFrequency] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                SymbolFrequency(
                    rank=int(row["rank"]),
                    symbol=row["symbol"],
                    frequency=int(row["frequency"]),
                )
            )
            if len(rows) >= limit:
                break
    return rows


def _formula_spans(text: str) -> list[tuple[int, int]]:
    patterns = [
        r"\$\$.*?\$\$",
        r"\$.*?\$",
        r"\\\(.*?\\\)",
        r"\\\[.*?\\\]",
    ]
    spans: list[tuple[int, int]] = []
    for pattern in patterns:
        spans.extend((match.start(), match.end()) for match in re.finditer(pattern, text, flags=re.DOTALL))
    return sorted(spans)


def _pattern_for_symbol(symbol: str, formula_only: bool) -> re.Pattern[str]:
    escaped = re.escape(symbol)
    if symbol.startswith("\\"):
        return re.compile(escaped + r"(?![A-Za-z])")
    if len(symbol) == 1 and symbol.isalnum():
        if formula_only:
            return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])")
        return re.compile(rf"(?<![A-Za-z]){escaped}(?![A-Za-z])")
    return re.compile(rf"(?<![A-Za-z0-9\\]){escaped}(?![A-Za-z0-9])", flags=re.IGNORECASE)


def _context_window(text: str, start: int, end: int, window: int = 220) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    while left > 0 and text[left] not in ".!?;\n":
        left -= 1
    if left < start and left < len(text):
        left += 1
    while right < len(text) and text[right - 1] not in ".!?;\n":
        right += 1
    return clean_text(text[left:right])


def find_symbol_mentions(text: str, symbols: Iterable[SymbolFrequency]) -> list[SymbolMention]:
    """Find conservative symbol mentions before spaCy converts them to entities."""

    text = text or ""
    math_spans = _formula_spans(text)
    mentions: list[SymbolMention] = []
    seen: set[tuple[int, int, str]] = set()

    for item in symbols:
        symbol = item.symbol
        formula_only = len(symbol) == 1 and symbol.isalnum()
        pattern = _pattern_for_symbol(symbol, formula_only=formula_only)
        search_regions = math_spans if formula_only else [(0, len(text))]
        for region_start, region_end in search_regions:
            region = text[region_start:region_end]
            for match in pattern.finditer(region):
                start = region_start + match.start()
                end = region_start + match.end()
                key = (start, end, symbol)
                if key in seen:
                    continue
                seen.add(key)
                mentions.append(
                    SymbolMention(
                        symbol=symbol,
                        matched_text=text[start:end],
                        start_char=start,
                        end_char=end,
                        usage_context=_context_window(text, start, end),
                        extraction_rule="spaCy MathEntRuler symbol pattern",
                    )
                )
    return sorted(mentions, key=lambda item: (item.start_char, -(item.end_char - item.start_char), item.symbol))


def load_spacy_model(model_name: str = "en_core_web_sm") -> Any:
    try:
        import spacy
    except ImportError as exc:
        raise RuntimeError(
            "spaCy is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    try:
        return spacy.load(model_name, disable=["ner"])
    except OSError:
        return spacy.blank("en")


def add_math_ent_ruler(nlp: Any, symbols: list[SymbolFrequency]) -> Any:
    from spacy.language import Language
    from spacy.tokens import Span
    from spacy.util import filter_spans

    if not Span.has_extension("math_symbol"):
        Span.set_extension("math_symbol", default="")
    if not Span.has_extension("math_matched_text"):
        Span.set_extension("math_matched_text", default="")
    if not Span.has_extension("math_start_char"):
        Span.set_extension("math_start_char", default=-1)
    if not Span.has_extension("math_end_char"):
        Span.set_extension("math_end_char", default=-1)

    symbol_payload = tuple(symbols)

    if not Language.has_factory("math_ent_ruler"):

        @Language.factory("math_ent_ruler")
        def create_math_ent_ruler(nlp: Any, name: str) -> Any:
            def math_ent_ruler(doc: Any) -> Any:
                spans = []
                for mention in find_symbol_mentions(doc.text, symbol_payload):
                    span = doc.char_span(mention.start_char, mention.end_char, label="MATH_SYMBOL", alignment_mode="expand")
                    if span is not None:
                        span._.math_symbol = mention.symbol
                        span._.math_matched_text = mention.matched_text
                        span._.math_start_char = mention.start_char
                        span._.math_end_char = mention.end_char
                        spans.append(span)
                doc.ents = filter_spans([*doc.ents, *spans])
                return doc

            return math_ent_ruler

    if "math_ent_ruler" not in nlp.pipe_names:
        nlp.add_pipe("math_ent_ruler", last=True)
    return nlp


def _safe_arxiv_pdf_name(arxiv_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", arxiv_id) + ".pdf"


def download_pdf(paper: ArxivPaper, pdf_dir: str | Path = DEFAULT_PDF_DIR, timeout: int = 45) -> tuple[Path | None, str]:
    if not paper.pdf_url:
        return None, "missing_pdf_url"

    import requests

    destination_dir = Path(pdf_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / _safe_arxiv_pdf_name(paper.arxiv_id)
    if destination.exists() and destination.stat().st_size > 0:
        return destination, "cached"

    try:
        response = requests.get(paper.pdf_url, timeout=timeout)
        response.raise_for_status()
        destination.write_bytes(response.content)
        return destination, "downloaded"
    except Exception as exc:  # noqa: BLE001 - recorded as pipeline provenance.
        return None, f"download_failed:{type(exc).__name__}"


def extract_pdf_text(pdf_path: str | Path, max_pages: int = 12) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is not installed. Run: python -m pip install -r requirements.txt") from exc

    try:
        reader = PdfReader(str(pdf_path))
        chunks = []
        for page in reader.pages[:max_pages]:
            chunks.append(page.extract_text() or "")
        return clean_text("\n".join(chunks)), "pdf_text_extracted"
    except Exception as exc:  # noqa: BLE001 - recorded as pipeline provenance.
        return "", f"pdf_extract_failed:{type(exc).__name__}"


def _gloss_index(records: list[GlossRecord]) -> dict[str, GlossRecord]:
    return {re.sub(r"[^a-z0-9]+", "", record.canonical_label.lower()): record for record in records}


def concept_for_symbol(symbol: str, records: list[GlossRecord]) -> GlossRecord | None:
    label = DIRECT_SYMBOL_LABELS.get(symbol)
    if label is None and len(symbol) == 1 and symbol.isalpha():
        label = "Variable"
    if not label:
        return None
    return _gloss_index(records).get(re.sub(r"[^a-z0-9]+", "", label.lower()))


def extract_symbol_context_rows(
    papers: list[ArxivPaper],
    symbols: list[SymbolFrequency],
    gloss_records: list[GlossRecord],
    *,
    download_pdfs: bool = False,
    pdf_dir: str | Path = DEFAULT_PDF_DIR,
    pdf_max_pages: int = 12,
    model_name: str = "en_core_web_sm",
) -> tuple[list[dict[str, str]], dict[str, int]]:
    nlp = add_math_ent_ruler(load_spacy_model(model_name), symbols)
    symbol_by_value = {item.symbol: item for item in symbols}
    rows: list[dict[str, str]] = []
    stats = {
        "papers_seen": 0,
        "pdfs_downloaded_or_cached": 0,
        "pdfs_failed": 0,
        "documents_processed": 0,
        "mentions_extracted": 0,
    }

    for paper in papers:
        stats["papers_seen"] += 1
        documents = [("title_abstract", f"{paper.title} {paper.abstract}", "metadata_abstract")]

        if download_pdfs:
            pdf_path, download_status = download_pdf(paper, pdf_dir=pdf_dir)
            if pdf_path:
                stats["pdfs_downloaded_or_cached"] += 1
                pdf_text, extraction_status = extract_pdf_text(pdf_path, max_pages=pdf_max_pages)
                if pdf_text:
                    documents.append(("pdf_text", pdf_text, f"{download_status};{extraction_status}"))
            else:
                stats["pdfs_failed"] += 1

        for text_source, text, source_status in documents:
            if not text:
                continue
            doc = nlp(text)
            stats["documents_processed"] += 1
            for ent in doc.ents:
                if ent.label_ != "MATH_SYMBOL":
                    continue
                symbol = ent._.math_symbol or ent.text
                symbol_row = symbol_by_value.get(symbol)
                if not symbol_row:
                    continue
                start_char = ent._.math_start_char if ent._.math_start_char >= 0 else ent.start_char
                end_char = ent._.math_end_char if ent._.math_end_char >= 0 else ent.end_char
                matched_text = ent._.math_matched_text or ent.text
                mention = SymbolMention(
                    symbol=symbol,
                    matched_text=matched_text,
                    start_char=start_char,
                    end_char=end_char,
                    usage_context=_context_window(text, start_char, end_char),
                    extraction_rule="spaCy MathEntRuler entity",
                )
                concept = concept_for_symbol(symbol, gloss_records)
                rows.append(
                    {
                        "symbol_rank": str(symbol_row.rank),
                        "symbol": symbol,
                        "symbol_frequency": str(symbol_row.frequency),
                        "arxiv_id": paper.arxiv_id,
                        "categories": paper.categories,
                        "text_source": text_source,
                        "matched_text": mention.matched_text,
                        "usage_context": mention.usage_context,
                        "extraction_rule": mention.extraction_rule,
                        "concept_IRI": concept.concept_iri if concept else "",
                        "canonical_label": concept.canonical_label if concept else "",
                        "domain_tags": "; ".join(concept.domain_tags) if concept else "",
                        "source_provenance": paper.pdf_url or "arXiv metadata",
                        "source_status": source_status,
                        "start_char": str(mention.start_char),
                        "end_char": str(mention.end_char),
                    }
                )
                stats["mentions_extracted"] += 1
    return rows, stats


def write_symbol_context_rows(rows: list[dict[str, str]], output_path: str | Path = DEFAULT_OUTPUT_PATH) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "symbol_rank",
        "symbol",
        "symbol_frequency",
        "arxiv_id",
        "categories",
        "text_source",
        "matched_text",
        "usage_context",
        "extraction_rule",
        "concept_IRI",
        "canonical_label",
        "domain_tags",
        "source_provenance",
        "source_status",
        "start_char",
        "end_char",
    ]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_status_report(
    status_path: str | Path,
    *,
    papers: int,
    symbols: int,
    rows: int,
    stats: dict[str, int],
    output_path: str | Path,
    download_pdfs: bool,
    elapsed_seconds: float,
) -> None:
    destination = Path(status_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "\n".join(
            [
                "# Week 3 spaCy MathEntRuler Corpus Pipeline Status",
                "",
                f"- Papers requested: {papers}",
                f"- Top symbols requested: {symbols}",
                f"- PDF download enabled: {download_pdfs}",
                f"- Papers seen: {stats['papers_seen']}",
                f"- PDFs downloaded or cached: {stats['pdfs_downloaded_or_cached']}",
                f"- PDF failures: {stats['pdfs_failed']}",
                f"- Documents processed: {stats['documents_processed']}",
                f"- Symbol-context rows extracted: {rows}",
                f"- Output: `{Path(output_path).as_posix()}`",
                f"- Elapsed seconds: {elapsed_seconds:.2f}",
                "",
                "This pipeline uses spaCy with a custom `MathEntRuler` component. Single-letter symbols are matched only in math-looking spans to avoid counting ordinary prose as notation.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_corpus_pipeline(
    *,
    metadata_path: str | Path = DEFAULT_METADATA_PATH,
    top_symbols_path: str | Path = DEFAULT_TOP_SYMBOLS_PATH,
    gloss_path: str | Path = DEFAULT_GLOSS_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    status_path: str | Path = DEFAULT_STATUS_PATH,
    pdf_dir: str | Path = DEFAULT_PDF_DIR,
    max_papers: int = 200,
    limit_symbols: int = 100,
    download_pdfs: bool = False,
    pdf_max_pages: int = 12,
    model_name: str = "en_core_web_sm",
) -> tuple[list[dict[str, str]], dict[str, int]]:
    start = time.perf_counter()
    papers = load_arxiv_metadata(metadata_path, max_papers=max_papers)
    symbols = load_top_symbols(top_symbols_path, limit=limit_symbols)
    gloss_records = load_gloss_records(gloss_path)
    rows, stats = extract_symbol_context_rows(
        papers,
        symbols,
        gloss_records,
        download_pdfs=download_pdfs,
        pdf_dir=pdf_dir,
        pdf_max_pages=pdf_max_pages,
        model_name=model_name,
    )
    write_symbol_context_rows(rows, output_path=output_path)
    write_status_report(
        status_path,
        papers=len(papers),
        symbols=len(symbols),
        rows=len(rows),
        stats=stats,
        output_path=output_path,
        download_pdfs=download_pdfs,
        elapsed_seconds=time.perf_counter() - start,
    )
    return rows, stats
