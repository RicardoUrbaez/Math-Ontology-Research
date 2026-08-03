from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from api.external_integrations import semantic_retrieval_status


ROOT = Path(__file__).resolve().parents[1]


def semantic_similarity_scores(
    query: str,
    texts: list[str],
    *,
    timeout_seconds: int = 180,
) -> tuple[list[float], dict[str, Any]]:
    if not texts:
        return [], {"status": "skipped", "engine": "sentence_transformers", "detail": "No evidence candidates."}
    runtime = semantic_retrieval_status()
    if not runtime.get("enabled"):
        return [], {
            "status": "not_configured",
            "engine": "sentence_transformers",
            "detail": "The semantic retrieval runtime is not available.",
        }
    model = os.getenv("MATHONTOSPEAK_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    cache_root = Path(os.getenv("MATHONTOSPEAK_CACHE_DIR", str(Path.home() / ".cache" / "mathontospeak")))
    cache_key = hashlib.sha256(json.dumps([model, query, texts], ensure_ascii=True).encode("utf-8")).hexdigest()
    cache_path = cache_root / "semantic" / f"{cache_key}.json"
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        scores = [float(score) for score in payload["scores"]]
        if len(scores) != len(texts):
            raise ValueError("Score count mismatch")
        return scores, {
            "status": "ok",
            "engine": "sentence_transformers",
            "model": model,
            "cache_hit": True,
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass

    worker_path = ROOT / "scripts" / "semantic_retrieval_worker.py"
    with tempfile.TemporaryDirectory(prefix="mathontospeak-semantic-") as temp_dir:
        request_path = Path(temp_dir) / "request.json"
        response_path = Path(temp_dir) / "response.json"
        request_path.write_text(
            json.dumps({"model": model, "query": query, "texts": texts}, ensure_ascii=True),
            encoding="utf-8",
        )
        try:
            result = subprocess.run(
                [str(runtime["python"]), str(worker_path), str(request_path), str(response_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [], {
                "status": "failed",
                "engine": "sentence_transformers",
                "detail": f"Semantic reranking failed: {type(exc).__name__}: {exc}",
            }
        if result.returncode != 0 or not response_path.is_file():
            detail = (result.stderr or result.stdout or "No semantic scores returned.").strip()
            return [], {"status": "failed", "engine": "sentence_transformers", "detail": detail[-800:]}
        try:
            payload = json.loads(response_path.read_text(encoding="utf-8"))
            scores = [float(score) for score in payload["scores"]]
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return [], {"status": "failed", "engine": "sentence_transformers", "detail": str(exc)}
    if len(scores) != len(texts):
        return [], {
            "status": "failed",
            "engine": "sentence_transformers",
            "detail": "The semantic score count did not match the evidence candidates.",
        }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"scores": scores}), encoding="utf-8")
    except OSError:
        pass
    return scores, {
        "status": "ok",
        "engine": "sentence_transformers",
        "model": str(payload.get("model") or model),
        "cache_hit": False,
    }


def semantic_similarity_scores_batch(
    requests: list[tuple[str, list[str]]],
    *,
    timeout_seconds: int = 240,
) -> tuple[list[list[float]], dict[str, Any]]:
    """Score all equations in one worker so the embedding model loads once per paper."""
    if not requests:
        return [], {
            "status": "skipped",
            "engine": "sentence_transformers",
            "detail": "No equation evidence requests.",
        }
    runtime = semantic_retrieval_status()
    if not runtime.get("enabled"):
        return [], {
            "status": "not_configured",
            "engine": "sentence_transformers",
            "detail": "The semantic retrieval runtime is not available.",
        }

    model = os.getenv("MATHONTOSPEAK_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    cache_root = Path(os.getenv("MATHONTOSPEAK_CACHE_DIR", str(Path.home() / ".cache" / "mathontospeak")))
    results: list[list[float] | None] = [None] * len(requests)
    missing: list[tuple[int, str, list[str], Path]] = []
    for index, (query, texts) in enumerate(requests):
        if not texts:
            results[index] = []
            continue
        cache_key = hashlib.sha256(
            json.dumps([model, query, texts], ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        cache_path = cache_root / "semantic" / f"{cache_key}.json"
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            scores = [float(score) for score in payload["scores"]]
            if len(scores) != len(texts):
                raise ValueError("Score count mismatch")
            results[index] = scores
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            missing.append((index, query, texts, cache_path))

    if not missing:
        return [scores or [] for scores in results], {
            "status": "ok",
            "engine": "sentence_transformers",
            "model": model,
            "cache_hit": True,
            "batch_size": len(requests),
        }

    worker_path = ROOT / "scripts" / "semantic_retrieval_worker.py"
    with tempfile.TemporaryDirectory(prefix="mathontospeak-semantic-batch-") as temp_dir:
        request_path = Path(temp_dir) / "request.json"
        response_path = Path(temp_dir) / "response.json"
        request_path.write_text(
            json.dumps(
                {
                    "model": model,
                    "requests": [
                        {"query": query, "texts": texts}
                        for _index, query, texts, _cache_path in missing
                    ],
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        try:
            process = subprocess.run(
                [str(runtime["python"]), str(worker_path), str(request_path), str(response_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [], {
                "status": "failed",
                "engine": "sentence_transformers",
                "detail": f"Batched semantic reranking failed: {type(exc).__name__}: {exc}",
            }
        if process.returncode != 0 or not response_path.is_file():
            detail = (process.stderr or process.stdout or "No batched semantic scores returned.").strip()
            return [], {
                "status": "failed",
                "engine": "sentence_transformers",
                "detail": detail[-800:],
            }
        try:
            payload = json.loads(response_path.read_text(encoding="utf-8"))
            missing_scores = [
                [float(score) for score in score_group]
                for score_group in payload["scores"]
            ]
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return [], {
                "status": "failed",
                "engine": "sentence_transformers",
                "detail": str(exc),
            }

    if len(missing_scores) != len(missing):
        return [], {
            "status": "failed",
            "engine": "sentence_transformers",
            "detail": "The batched semantic result count did not match the equation requests.",
        }
    for (index, _query, texts, cache_path), scores in zip(missing, missing_scores, strict=True):
        if len(scores) != len(texts):
            return [], {
                "status": "failed",
                "engine": "sentence_transformers",
                "detail": "A batched semantic score count did not match its evidence candidates.",
            }
        results[index] = scores
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"scores": scores}), encoding="utf-8")
        except OSError:
            pass

    return [scores or [] for scores in results], {
        "status": "ok",
        "engine": "sentence_transformers",
        "model": str(payload.get("model") or model),
        "cache_hit": len(missing) != len(requests),
        "batch_size": len(requests),
    }
