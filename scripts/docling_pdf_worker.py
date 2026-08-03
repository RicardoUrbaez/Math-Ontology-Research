from __future__ import annotations

import json
import os
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def _value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().lower()


def _provenance(item: Any) -> tuple[int | None, list[float]]:
    provenance = list(getattr(item, "prov", None) or [])
    if not provenance:
        return None, []
    first = provenance[0]
    page = getattr(first, "page_no", None)
    bbox = getattr(first, "bbox", None)
    if bbox is None:
        return int(page) if page is not None else None, []
    coordinates = [
        getattr(bbox, "l", None),
        getattr(bbox, "t", None),
        getattr(bbox, "r", None),
        getattr(bbox, "b", None),
    ]
    return (
        int(page) if page is not None else None,
        [float(value) for value in coordinates] if all(value is not None for value in coordinates) else [],
    )


def _formula_payload(text: str) -> tuple[str, str]:
    clean = text.strip()
    label = ""
    label_match = re.search(r"(?:\\tag\{([^{}]+)\}|\(([A-Za-z]?\d+(?:\.\d+)*)\))\s*$", clean)
    if label_match:
        label = next((group for group in label_match.groups() if group), "")
        clean = clean[: label_match.start()].strip()
    clean = re.sub(r"^\$\$?|\$\$?$", "", clean).strip()
    return clean, label


def extract(input_path: Path) -> dict[str, Any]:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.settings import settings
    from docling.document_converter import DocumentConverter, PdfFormatOption

    settings.inference.compile_torch_models = False
    requested_device = os.getenv("MATHONTOSPEAK_DOCLING_DEVICE", "cpu").strip().lower()
    device = {
        "auto": AcceleratorDevice.AUTO,
        "cuda": AcceleratorDevice.CUDA,
        "cpu": AcceleratorDevice.CPU,
    }.get(requested_device, AcceleratorDevice.CPU)
    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=4, device=device)
    pipeline_options.do_ocr = os.getenv("MATHONTOSPEAK_DOCLING_OCR", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    pipeline_options.do_table_structure = False
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    result = converter.convert(input_path)
    document = result.document
    chunks: list[dict[str, Any]] = []
    current_heading = ""
    for reading_order, entry in enumerate(document.iterate_items()):
        item = entry[0] if isinstance(entry, tuple) else entry
        label = _value(getattr(item, "label", ""))
        text = str(getattr(item, "text", "") or "").strip()
        if not text:
            continue
        page, bbox = _provenance(item)
        kind = "paragraph"
        if label in {"title", "section_header", "heading"}:
            kind = "title" if label == "title" else "section_heading"
            current_heading = text
        elif label in {"formula", "equation"}:
            kind = "equation"
        elif label in {"caption"}:
            kind = "caption"
        chunk: dict[str, Any] = {
            "source": "docling",
            "kind": kind,
            "text": text,
            "page": page,
            "bbox": bbox,
            "reading_order": reading_order,
            "section_heading": current_heading,
            "block_id": f"docling-{reading_order}",
        }
        if kind == "equation":
            latex, source_label = _formula_payload(text)
            chunk["latex"] = latex
            chunk["source_label"] = source_label
            chunk["text"] = f"$${latex}$$" + (f" ({source_label})" if source_label else "")
        chunks.append(chunk)

    markdown = document.export_to_markdown()
    text = "\n\n".join(str(chunk.get("text") or "") for chunk in chunks).strip() or markdown.strip()
    try:
        engine_version = version("docling-slim")
    except PackageNotFoundError:
        engine_version = "source-checkout"
    return {
        "text": text,
        "chunks": chunks,
        "markdown": markdown,
        "engine_version": engine_version,
        "device": requested_device,
        "ocr_enabled": pipeline_options.do_ocr,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: docling_pdf_worker.py INPUT.pdf OUTPUT.json", file=sys.stderr)
        return 2
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    payload = extract(input_path)
    output_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
