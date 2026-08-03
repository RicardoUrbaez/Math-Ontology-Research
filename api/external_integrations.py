from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.equation_normalization import normalize_extracted_equation


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCLING_TIMEOUT_SECONDS = 900
DEFAULT_MINERU_TIMEOUT_SECONDS = 1200


def external_root_path() -> Path:
    return Path(
        os.getenv(
            "MATHONTOSPEAK_EXTERNAL_ROOT",
            str(Path.home() / "Documents" / "MathOntoSpeak-External"),
        )
    )


def _venv_python(root: Path, name: str) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return root / ".venvs" / name / scripts_dir / executable


def _runtime_python(root: Path, name: str, fallbacks: tuple[str, ...] = ()) -> Path:
    configured = os.getenv(f"MATHONTOSPEAK_{name.upper()}_PYTHON", "").strip()
    if configured:
        return Path(configured)
    preferred = _venv_python(root, name)
    if preferred.is_file():
        return preferred
    for fallback in fallbacks:
        candidate = _venv_python(root, fallback)
        if candidate.is_file():
            return candidate
    return preferred


@lru_cache(maxsize=16)
def _python_module_available_cached(python_path: str, module_name: str) -> bool:
    path = Path(python_path)
    if not path.is_file():
        return False
    command = [
        str(path),
        "-c",
        f"import importlib; importlib.import_module({module_name!r})",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def python_module_available(python_path: Path, module_name: str) -> bool:
    return _python_module_available_cached(str(python_path), module_name)


def _enabled(name: str, runtime_available: bool) -> bool:
    configured = os.getenv(f"MATHONTOSPEAK_{name.upper()}_ENABLED", "auto").strip().lower()
    if configured in {"0", "false", "no", "off", "disabled"}:
        return False
    return runtime_available


def _python_integration(
    *,
    root: Path,
    repository: str,
    runtime: str,
    module: str,
    role: str,
    fallback_runtimes: tuple[str, ...] = (),
) -> dict[str, Any]:
    repository_path = root / "repos" / repository
    python_path = _runtime_python(root, runtime, fallback_runtimes)
    runtime_available = python_module_available(python_path, module)
    key = module.replace("-", "_")
    return {
        "role": role,
        "wired": True,
        "cloned": (repository_path / ".git").is_dir(),
        "repository_path": str(repository_path),
        "python": str(python_path),
        "runtime_available": runtime_available,
        "enabled": _enabled(key, runtime_available),
        "verification": f"{module} import through its isolated Python runtime",
    }


def grobid_runtime_status(*, external_root: Path | None = None) -> dict[str, Any]:
    root = external_root or external_root_path()
    repository_path = root / "repos" / "grobid"
    endpoint = os.getenv("MATHONTOSPEAK_GROBID_URL", "http://127.0.0.1:8070").rstrip("/")
    version = ""
    detail = "GROBID service is not running."
    try:
        with urllib.request.urlopen(f"{endpoint}/api/version", timeout=0.75) as response:
            version = response.read().decode("utf-8", errors="replace").strip()
        runtime_available = True
        detail = "GROBID service responded to its version endpoint."
    except (OSError, TimeoutError, urllib.error.URLError):
        runtime_available = False
    return {
        "role": "scientific_document_structure",
        "wired": True,
        "cloned": (repository_path / ".git").is_dir(),
        "repository_path": str(repository_path),
        "endpoint": endpoint,
        "runtime_available": runtime_available,
        "enabled": _enabled("grobid", runtime_available),
        "version": version,
        "detail": detail,
        "verification": "GET /api/version from the configured GROBID service",
    }


def integration_registry(*, external_root: Path | None = None) -> dict[str, dict[str, Any]]:
    root = external_root or external_root_path()
    integrations = {
        "docling": _python_integration(
            root=root,
            repository="docling",
            runtime="docling",
            module="docling",
            role="document_extraction",
            fallback_runtimes=("marker",),
        ),
        "mineru": _python_integration(
            root=root,
            repository="MinerU",
            runtime="mineru",
            module="mineru",
            role="scanned_pdf_fallback",
        ),
        "sentence_transformers": _python_integration(
            root=root,
            repository="sentence-transformers",
            runtime="semantic",
            module="sentence_transformers",
            role="semantic_evidence_reranking",
            fallback_runtimes=("marker",),
        ),
        "ragas": _python_integration(
            root=root,
            repository="ragas",
            runtime="ragas",
            module="ragas",
            role="grounding_evaluation",
            fallback_runtimes=("marker",),
        ),
        "grobid": grobid_runtime_status(external_root=root),
    }
    return integrations


def docling_runtime_status(*, external_root: Path | None = None) -> dict[str, Any]:
    return integration_registry(external_root=external_root)["docling"]


def mineru_runtime_status(*, external_root: Path | None = None) -> dict[str, Any]:
    return integration_registry(external_root=external_root)["mineru"]


def semantic_retrieval_status(*, external_root: Path | None = None) -> dict[str, Any]:
    root = external_root or external_root_path()
    return _python_integration(
        root=root,
        repository="sentence-transformers",
        runtime="semantic",
        module="sentence_transformers",
        role="semantic_evidence_reranking",
        fallback_runtimes=("marker",),
    )


def ragas_runtime_status(*, external_root: Path | None = None) -> dict[str, Any]:
    root = external_root or external_root_path()
    return _python_integration(
        root=root,
        repository="ragas",
        runtime="ragas",
        module="ragas",
        role="grounding_evaluation",
        fallback_runtimes=("marker",),
    )


def extract_pdf_context_with_docling(
    raw_pdf: bytes,
    *,
    pdf_filename: str = "",
    python_path: Path | None = None,
    worker_path: Path | None = None,
    timeout_seconds: int = DEFAULT_DOCLING_TIMEOUT_SECONDS,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    root = external_root_path()
    python_path = python_path or _runtime_python(root, "docling", ("marker",))
    worker_path = worker_path or ROOT / "scripts" / "docling_pdf_worker.py"
    document_id = hashlib.sha256(raw_pdf + b"docling-v1").hexdigest()
    cache_root = Path(os.getenv("MATHONTOSPEAK_CACHE_DIR", str(Path.home() / ".cache" / "mathontospeak")))
    cache_path = cache_root / "docling" / f"{document_id}.json"

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload.get("text"):
            raise ValueError("Invalid Docling cache entry")
        cache_hit = True
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        cache_hit = False
        with tempfile.TemporaryDirectory(prefix="mathontospeak-docling-") as temp_dir:
            input_path = Path(temp_dir) / (Path(pdf_filename).name or "paper.pdf")
            output_path = Path(temp_dir) / "docling-result.json"
            input_path.write_bytes(raw_pdf)
            try:
                result = subprocess.run(
                    [str(python_path), str(worker_path), str(input_path), str(output_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return "", [], {
                    "status": "failed",
                    "extractor": "docling",
                    "detail": f"Docling extraction failed: {type(exc).__name__}: {exc}",
                }
            if result.returncode != 0 or not output_path.is_file():
                detail = (result.stderr or result.stdout or "Docling returned no result.").strip()
                return "", [], {
                    "status": "failed",
                    "extractor": "docling",
                    "detail": detail[-800:],
                }
            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return "", [], {
                    "status": "failed",
                    "extractor": "docling",
                    "detail": f"Docling result could not be read: {exc}",
                }
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        except OSError:
            pass

    text = str(payload.get("text") or "").strip()
    chunks = [chunk for chunk in payload.get("chunks", []) if isinstance(chunk, dict)]
    for chunk in chunks:
        if chunk.get("kind") != "equation":
            continue
        latex, source_label = normalize_extracted_equation(
            str(chunk.get("latex") or chunk.get("text") or ""),
            str(chunk.get("source_label") or ""),
        )
        chunk["latex"] = latex
        chunk["source_label"] = source_label
    if not text:
        return "", [], {
            "status": "empty",
            "extractor": "docling",
            "detail": "Docling completed but returned no document text.",
        }
    return text, chunks, {
        "status": "ok",
        "extractor": "docling",
        "detail": f"Docling extracted {len(chunks)} structured document blocks.",
        "filename": pdf_filename,
        "document_id": document_id,
        "context_chunk_count": len(chunks),
        "equation_candidate_count": sum(1 for chunk in chunks if chunk.get("kind") == "equation"),
        "engine_version": str(payload.get("engine_version") or "unknown"),
        "device": str(payload.get("device") or "unknown"),
        "ocr_enabled": bool(payload.get("ocr_enabled", False)),
        "cache_hit": cache_hit,
    }


def extract_pdf_context_with_mineru(
    raw_pdf: bytes,
    *,
    pdf_filename: str = "",
    python_path: Path | None = None,
    worker_path: Path | None = None,
    timeout_seconds: int = DEFAULT_MINERU_TIMEOUT_SECONDS,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    root = external_root_path()
    python_path = python_path or _runtime_python(root, "mineru")
    worker_path = worker_path or ROOT / "scripts" / "mineru_pdf_worker.py"
    backend = os.getenv("MATHONTOSPEAK_MINERU_BACKEND", "pipeline").strip() or "pipeline"
    document_id = hashlib.sha256(raw_pdf + f"mineru-v1:{backend}".encode("utf-8")).hexdigest()
    cache_root = Path(os.getenv("MATHONTOSPEAK_CACHE_DIR", str(Path.home() / ".cache" / "mathontospeak")))
    cache_path = cache_root / "mineru" / f"{document_id}.json"

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload.get("text"):
            raise ValueError("Invalid MinerU cache entry")
        cache_hit = True
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        cache_hit = False
        with tempfile.TemporaryDirectory(prefix="mathontospeak-mineru-") as temp_dir:
            input_path = Path(temp_dir) / (Path(pdf_filename).name or "paper.pdf")
            output_path = Path(temp_dir) / "mineru-result.json"
            input_path.write_bytes(raw_pdf)
            try:
                result = subprocess.run(
                    [str(python_path), str(worker_path), str(input_path), str(output_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    check=False,
                    env={
                        **os.environ,
                        "MATHONTOSPEAK_MINERU_BACKEND": backend,
                        "MINERU_MODEL_SOURCE": os.getenv("MINERU_MODEL_SOURCE", "huggingface"),
                    },
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return "", [], {
                    "status": "failed",
                    "extractor": "mineru",
                    "detail": f"MinerU extraction failed: {type(exc).__name__}: {exc}",
                }
            if result.returncode != 0 or not output_path.is_file():
                detail = (result.stderr or result.stdout or "MinerU returned no result.").strip()
                return "", [], {
                    "status": "failed",
                    "extractor": "mineru",
                    "detail": detail[-800:],
                }
            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return "", [], {
                    "status": "failed",
                    "extractor": "mineru",
                    "detail": f"MinerU result could not be read: {exc}",
                }
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        except OSError:
            pass

    text = str(payload.get("text") or "").strip()
    chunks = [chunk for chunk in payload.get("chunks", []) if isinstance(chunk, dict)]
    for chunk in chunks:
        if chunk.get("kind") != "equation":
            continue
        latex, source_label = normalize_extracted_equation(
            str(chunk.get("latex") or chunk.get("text") or ""),
            str(chunk.get("source_label") or ""),
        )
        chunk["latex"] = latex
        chunk["source_label"] = source_label
    if not text:
        return "", [], {
            "status": "empty",
            "extractor": "mineru",
            "detail": "MinerU completed but returned no document text.",
        }
    return text, chunks, {
        "status": "ok",
        "extractor": "mineru",
        "detail": f"MinerU extracted {len(chunks)} structured document blocks.",
        "filename": pdf_filename,
        "document_id": document_id,
        "context_chunk_count": len(chunks),
        "equation_candidate_count": sum(1 for chunk in chunks if chunk.get("kind") == "equation"),
        "engine_version": str(payload.get("engine_version") or "unknown"),
        "backend": str(payload.get("backend") or backend),
        "device": str(payload.get("device") or "unknown"),
        "cache_hit": cache_hit,
    }
