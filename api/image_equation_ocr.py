from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SUPPORTED_IMAGE_SUFFIXES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
OCR_RESULT_PREFIX = "MATHONTOSPEAK_IMAGE_OCR="


def image_ocr_python_path() -> Path:
    configured = os.getenv("MATHONTOSPEAK_IMAGE_OCR_PYTHON", "").strip()
    if configured:
        return Path(configured)
    external_root = Path(
        os.getenv(
            "MATHONTOSPEAK_EXTERNAL_ROOT",
            str(Path.home() / "Documents" / "MathOntoSpeak-External"),
        )
    )
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return external_root / ".venvs" / "marker" / scripts_dir / executable


def image_ocr_runtime_status() -> dict[str, Any]:
    python_path = image_ocr_python_path()
    site_packages = python_path.parent.parent / "Lib" / "site-packages"
    return {
        "available": python_path.is_file() and (site_packages / "pix2tex").is_dir(),
        "python": str(python_path),
        "engine": "pix2tex+rapidocr",
        "supported_types": ["image/png", "image/jpeg"],
    }


def is_equation_image(filename: str, media_type: str = "") -> bool:
    return media_type.lower() in {"image/png", "image/jpeg", "image/jpg"} or Path(filename).suffix.lower() in SUPPORTED_IMAGE_SUFFIXES


def _extract_worker_payload(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(OCR_RESULT_PREFIX):
            try:
                payload = json.loads(line[len(OCR_RESULT_PREFIX) :])
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
            return payload if isinstance(payload, dict) else None
    return None


def extract_equation_image_context(
    encoded_image: str,
    *,
    filename: str,
    media_type: str = "",
    timeout_seconds: int = 180,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    mime_type = media_type.lower() if media_type else SUPPORTED_IMAGE_SUFFIXES.get(Path(filename).suffix.lower(), "")
    if mime_type == "image/jpg":
        mime_type = "image/jpeg"
    if mime_type not in {"image/png", "image/jpeg"}:
        return "", [], {"status": "failed", "input_type": "image", "detail": "Only PNG and JPEG equation images are supported."}
    try:
        raw_image = base64.b64decode(encoded_image, validate=True)
    except (binascii.Error, ValueError) as exc:
        return "", [], {"status": "failed", "input_type": "image", "detail": f"Image base64 decode failed: {exc}"}
    if not raw_image:
        return "", [], {"status": "failed", "input_type": "image", "detail": "The uploaded image was empty."}
    if len(raw_image) > 20 * 1024 * 1024:
        return "", [], {"status": "failed", "input_type": "image", "detail": "Equation images must be 20 MB or smaller."}

    python_path = image_ocr_python_path()
    worker_path = Path(__file__).resolve().parents[1] / "scripts" / "image_equation_ocr_worker.py"
    if not python_path.is_file() or not worker_path.is_file():
        return "", [], {
            "status": "not_configured",
            "input_type": "image",
            "extractor": "latex_ocr",
            "detail": "The local LaTeX-OCR image runtime is not installed.",
        }

    cache_root = Path(os.getenv("MATHONTOSPEAK_CACHE_DIR", str(Path.home() / ".cache" / "mathontospeak")))
    document_id = hashlib.sha256(raw_image + b"image-equation-ocr-v1").hexdigest()
    cache_path = cache_root / "images" / f"{document_id}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(cached, dict) and cached.get("latex"):
            worker_payload = cached
            cache_hit = True
        else:
            raise ValueError("Invalid image OCR cache entry")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        cache_hit = False
        suffix = Path(filename).suffix.lower() if Path(filename).suffix.lower() in SUPPORTED_IMAGE_SUFFIXES else ".png"
        with tempfile.TemporaryDirectory(prefix="mathontospeak-image-") as temp_dir:
            image_path = Path(temp_dir) / f"equation{suffix}"
            image_path.write_bytes(raw_image)
            environment = dict(os.environ)
            environment.setdefault("PYTHONIOENCODING", "utf-8")
            environment.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
            try:
                result = subprocess.run(
                    [str(python_path), str(worker_path), str(image_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    check=False,
                    env=environment,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return "", [], {
                    "status": "failed",
                    "input_type": "image",
                    "extractor": "latex_ocr",
                    "detail": f"Image equation recognition failed: {type(exc).__name__}: {exc}",
                }
        worker_payload = _extract_worker_payload(result.stdout)
        if result.returncode != 0 or not worker_payload:
            detail = (result.stderr or result.stdout or "No OCR result was returned.").strip()
            return "", [], {
                "status": "failed",
                "input_type": "image",
                "extractor": "latex_ocr",
                "detail": f"LaTeX-OCR could not recognize the equation: {detail[-600:]}",
            }
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(worker_payload, ensure_ascii=True), encoding="utf-8")
        except OSError:
            pass

    latex = str(worker_payload.get("latex") or "").strip()
    if not latex:
        return "", [], {"status": "failed", "input_type": "image", "extractor": "latex_ocr", "detail": "No equation was recognized in the image."}
    source_label = str(worker_payload.get("source_label") or "")
    ocr_text = str(worker_payload.get("ocr_text") or latex)
    image_data_url = f"data:{mime_type};base64,{encoded_image}"
    block_id = f"image-{document_id[:12]}"
    equation_text = f"$${latex}$$" + (f" ({source_label})" if source_label else "")
    confidence = "high" if float(worker_payload.get("text_confidence") or 0.0) >= 0.9 else "medium"
    chunks = [
        {
            "source": "image_ocr",
            "kind": "equation",
            "text": equation_text,
            "latex": latex,
            "source_label": source_label,
            "page": 1,
            "bbox": list(worker_payload.get("bbox") or []),
            "polygon": [],
            "reading_order": 0,
            "block_id": block_id,
            "method": "latex_ocr_image",
            "confidence": confidence,
            "equation_image": image_data_url,
        },
        {
            "source": "image_ocr",
            "kind": "ocr_text",
            "text": ocr_text,
            "page": 1,
            "reading_order": 1,
            "block_id": f"{block_id}-text",
        },
    ]
    status = {
        "status": "ok",
        "input_type": "image",
        "extractor": "latex_ocr",
        "detail": f"Recognized one equation from {filename or 'the uploaded image'}.",
        "filename": filename,
        "mime_type": mime_type,
        "equation_candidate_count": 1,
        "context_chunk_count": len(chunks),
        "pages_processed": 1,
        "cache_hit": cache_hit,
        "document_id": document_id,
        "label_confidence": float(worker_payload.get("label_confidence") or 0.0),
        "ocr_confidence": float(worker_payload.get("text_confidence") or 0.0),
    }
    return ocr_text, chunks, status
