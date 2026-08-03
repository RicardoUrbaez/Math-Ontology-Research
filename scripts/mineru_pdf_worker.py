from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


EQUATION_ID_PATTERN = r"(?:[A-Za-z]+\.?)?\d+(?:\.\d+)*"
EQUATION_LABEL_RE = re.compile(rf"\$\$\s*\(({EQUATION_ID_PATTERN})\)\s*$")
EQUATION_TAG_RE = re.compile(rf"\\tag\s*\{{\s*({EQUATION_ID_PATTERN})\s*\}}")


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return [float(coordinate) for coordinate in value]
    except (TypeError, ValueError):
        return None


def _equation_parts(text: str, source_label: str = "") -> tuple[str, str]:
    display = text.strip()
    label = source_label.strip().strip("()")
    tag_match = EQUATION_TAG_RE.search(display)
    if tag_match:
        label = label or tag_match.group(1)
        display = display[: tag_match.start()] + display[tag_match.end() :]
    match = EQUATION_LABEL_RE.search(display)
    if match:
        label = label or match.group(1)
        display = display[: match.start()] + "$$"
    if display.startswith("$$") and display.endswith("$$"):
        display = display[2:-2].strip()
    return display, label


def _content_text(item: dict[str, Any]) -> str:
    kind = str(item.get("type") or "").lower()
    if kind in {"text", "equation", "list"}:
        return str(item.get("text") or "").strip()
    if kind == "code":
        return str(item.get("code_body") or item.get("text") or "").strip()
    values: list[str] = []
    for key in (
        "image_caption",
        "image_footnote",
        "table_caption",
        "table_footnote",
        "chart_caption",
        "chart_footnote",
    ):
        value = item.get(key)
        if isinstance(value, list):
            values.extend(str(part).strip() for part in value if str(part).strip())
        elif str(value or "").strip():
            values.append(str(value).strip())
    return " ".join(values)


def content_list_to_chunks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_heading = ""
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").lower()
        if item_type in {"header", "footer", "page_number", "aside_text", "page_footnote"}:
            continue
        text = _content_text(item)
        if not text:
            continue
        page_index = item.get("page_idx")
        try:
            page = int(page_index) + 1
        except (TypeError, ValueError):
            page = None
        text_level = item.get("text_level")
        is_heading = item_type == "text" and str(text_level or "0").isdigit() and int(text_level or 0) > 0
        kind = "section_heading" if is_heading else "equation" if item_type == "equation" else "paragraph"
        latex = ""
        source_label = str(item.get("source_label") or "")
        if kind == "equation":
            latex, source_label = _equation_parts(text, source_label)
        chunk: dict[str, Any] = {
            "source": "mineru",
            "kind": kind,
            "text": text,
            "page": page,
            "reading_order": len(chunks),
            "block_id": f"mineru-{len(chunks)}",
            "section_heading": current_heading,
        }
        bounds = _bbox(item.get("bbox"))
        if bounds is not None:
            chunk["bbox"] = bounds
        if kind == "equation":
            chunk["latex"] = latex
            chunk["source_label"] = source_label
        if is_heading:
            current_heading = text
            chunk["section_heading"] = current_heading
        chunks.append(chunk)
    return chunks


def _find_output(output_root: Path, suffix: str) -> Path | None:
    candidates = [
        path
        for path in output_root.rglob(f"*{suffix}")
        if "content_list_v2" not in path.name
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_size)


def run_mineru(input_path: Path, output_path: Path) -> None:
    backend = os.getenv("MATHONTOSPEAK_MINERU_BACKEND", "pipeline").strip() or "pipeline"
    method = os.getenv("MATHONTOSPEAK_MINERU_METHOD", "auto").strip() or "auto"
    with tempfile.TemporaryDirectory(prefix="mathontospeak-mineru-output-") as temp_dir:
        output_root = Path(temp_dir)
        command = [
            sys.executable,
            "-m",
            "mineru.cli.client",
            "-p",
            str(input_path),
            "-o",
            str(output_root),
            "-b",
            backend,
            "-m",
            method,
        ]
        process = subprocess.run(command, capture_output=True, check=False)
        if process.returncode != 0:
            stderr = process.stderr.decode("utf-8", errors="replace").strip()
            stdout = process.stdout.decode("utf-8", errors="replace").strip()
            raise RuntimeError((stderr or stdout or "MinerU CLI failed.")[-1200:])
        content_path = _find_output(output_root, "_content_list.json")
        if content_path is None:
            raise RuntimeError("MinerU did not produce a content_list.json file.")
        items = json.loads(content_path.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            raise RuntimeError("MinerU content_list.json was not a list.")
        chunks = content_list_to_chunks(items)
        text = "\n\n".join(str(chunk.get("text") or "") for chunk in chunks).strip()
        try:
            engine_version = version("mineru")
        except PackageNotFoundError:
            engine_version = "unknown"
        device = "cpu"
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
        except (ImportError, RuntimeError):
            pass
        output_path.write_text(
            json.dumps(
                {
                    "text": text,
                    "chunks": chunks,
                    "engine_version": engine_version,
                    "backend": backend,
                    "device": device,
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: mineru_pdf_worker.py INPUT.pdf OUTPUT.json", file=sys.stderr)
        return 2
    try:
        run_mineru(Path(sys.argv[1]), Path(sys.argv[2]))
    except Exception as exc:
        print(f"MinerU worker failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
