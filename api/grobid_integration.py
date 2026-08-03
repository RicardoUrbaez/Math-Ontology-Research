from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

import requests

from api.external_integrations import grobid_runtime_status


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ElementTree.Element) -> str:
    return re.sub(r"\s+", " ", " ".join(element.itertext())).strip()


def grobid_tei_context_chunks(tei_xml: str) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(tei_xml)
    chunks: list[dict[str, Any]] = []
    current_heading = ""
    reading_order = 0
    for element in root.iter():
        name = _local_name(element.tag)
        parent_text = _text(element)
        if not parent_text:
            continue
        kind = ""
        if name == "head":
            kind = "section_heading"
            current_heading = parent_text
        elif name == "p":
            kind = "paragraph"
        elif name == "formula":
            kind = "equation"
        elif name == "abstract":
            kind = "abstract"
        if not kind:
            continue
        if kind == "abstract" and any(_local_name(child.tag) == "p" for child in element.iter() if child is not element):
            continue
        source_label = ""
        latex = parent_text
        if kind == "equation":
            label_element = next((child for child in element if _local_name(child.tag) == "label"), None)
            if label_element is not None:
                source_label = _text(label_element).strip("()[] ")
                label_text = _text(label_element)
                if label_text:
                    latex = latex.replace(label_text, "", 1).strip()
        coords = str(element.attrib.get("coords") or "")
        page = None
        bbox: list[float] = []
        if coords:
            first = coords.split(";", 1)[0].split(",")
            try:
                page = int(first[0])
                if len(first) >= 5:
                    x, y, width, height = (float(value) for value in first[1:5])
                    bbox = [x, y, x + width, y + height]
            except (TypeError, ValueError):
                page = None
                bbox = []
        chunk: dict[str, Any] = {
            "source": "grobid",
            "kind": kind,
            "text": parent_text,
            "page": page,
            "bbox": bbox,
            "reading_order": reading_order,
            "section_heading": current_heading,
            "block_id": f"grobid-{reading_order}",
        }
        if kind == "equation":
            chunk.update({"latex": latex, "source_label": source_label})
            chunk["text"] = f"$${latex}$$" + (f" ({source_label})" if source_label else "")
        chunks.append(chunk)
        reading_order += 1
    return chunks


def extract_pdf_context_with_grobid(
    raw_pdf: bytes,
    *,
    pdf_filename: str = "paper.pdf",
    timeout_seconds: int = 180,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    runtime = grobid_runtime_status()
    if not runtime.get("enabled"):
        return "", [], {
            "status": "not_configured",
            "extractor": "grobid",
            "detail": runtime.get("detail", "GROBID is not running."),
        }
    endpoint = str(runtime["endpoint"]).rstrip("/")
    try:
        response = requests.post(
            f"{endpoint}/api/processFulltextDocument",
            files={"input": (pdf_filename or "paper.pdf", raw_pdf, "application/pdf")},
            data=[("teiCoordinates", "formula"), ("segmentSentences", "1")],
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        chunks = grobid_tei_context_chunks(response.text)
    except (requests.RequestException, ElementTree.ParseError, ValueError) as exc:
        return "", [], {
            "status": "failed",
            "extractor": "grobid",
            "detail": f"GROBID structure extraction failed: {type(exc).__name__}: {exc}",
        }
    text = "\n\n".join(str(chunk.get("text") or "") for chunk in chunks).strip()
    return text, chunks, {
        "status": "ok",
        "extractor": "grobid",
        "detail": f"GROBID returned {len(chunks)} TEI structure blocks.",
        "context_chunk_count": len(chunks),
        "equation_candidate_count": sum(1 for chunk in chunks if chunk.get("kind") == "equation"),
        "version": runtime.get("version", ""),
    }


def enrich_with_grobid(
    raw_pdf: bytes,
    *,
    pdf_filename: str,
    text: str,
    chunks: list[dict[str, Any]],
    status: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    runtime = grobid_runtime_status()
    enriched_status = dict(status)
    if not runtime.get("enabled"):
        enriched_status["structure_enrichment"] = {
            "engine": "grobid",
            "status": "not_active",
            "detail": runtime.get("detail", "GROBID service is not running."),
        }
        return text, chunks, enriched_status
    grobid_text, grobid_chunks, grobid_status = extract_pdf_context_with_grobid(
        raw_pdf,
        pdf_filename=pdf_filename,
    )
    enriched_status["structure_enrichment"] = grobid_status
    if grobid_status.get("status") != "ok":
        return text, chunks, enriched_status
    existing = {re.sub(r"\s+", " ", str(chunk.get("text") or "")).strip().lower() for chunk in chunks}
    merged = list(chunks)
    for chunk in grobid_chunks:
        normalized = re.sub(r"\s+", " ", str(chunk.get("text") or "")).strip().lower()
        if normalized and normalized not in existing:
            merged.append(chunk)
            existing.add(normalized)
    for index, chunk in enumerate(merged):
        chunk["reading_order"] = index
    return "\n\n".join(part for part in (text, grobid_text) if part), merged, enriched_status
