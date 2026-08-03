from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from api.external_integrations import ragas_runtime_status


ROOT = Path(__file__).resolve().parents[1]


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]+", value or "")
        if len(token) > 2
    }


def _ragas_similarity(
    reference: str,
    response: str,
    *,
    timeout_seconds: int = 120,
) -> tuple[float | None, dict[str, Any]]:
    runtime = ragas_runtime_status()
    if not runtime.get("enabled"):
        return None, {"status": "not_configured", "engine": "ragas"}
    cache_root = Path(os.getenv("MATHONTOSPEAK_CACHE_DIR", str(Path.home() / ".cache" / "mathontospeak")))
    cache_key = hashlib.sha256(f"{reference}\n---\n{response}".encode("utf-8")).hexdigest()
    cache_path = cache_root / "ragas" / f"{cache_key}.json"
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return float(payload["score"]), {"status": "ok", "engine": "ragas", "cache_hit": True}
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass

    with tempfile.TemporaryDirectory(prefix="mathontospeak-ragas-") as temp_dir:
        request_path = Path(temp_dir) / "request.json"
        response_path = Path(temp_dir) / "response.json"
        request_path.write_text(
            json.dumps({"reference": reference, "response": response}, ensure_ascii=True),
            encoding="utf-8",
        )
        try:
            result = subprocess.run(
                [
                    str(runtime["python"]),
                    str(ROOT / "scripts" / "ragas_grounding_worker.py"),
                    str(request_path),
                    str(response_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, {"status": "failed", "engine": "ragas", "detail": str(exc)}
        if result.returncode != 0 or not response_path.is_file():
            detail = (result.stderr or result.stdout or "Ragas returned no result.").strip()
            return None, {"status": "failed", "engine": "ragas", "detail": detail[-800:]}
        try:
            payload = json.loads(response_path.read_text(encoding="utf-8"))
            score = float(payload["score"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return None, {"status": "failed", "engine": "ragas", "detail": str(exc)}
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"score": score}), encoding="utf-8")
    except OSError:
        pass
    return score, {"status": "ok", "engine": "ragas", "cache_hit": False}


def evaluate_grounding(
    *,
    context_summary: str,
    evidence: list[dict[str, Any]],
    unresolved_symbols: list[str],
    allow_ragas: bool = False,
) -> dict[str, Any]:
    evidence_text = " ".join(str(item.get("text") or "") for item in evidence).strip()
    summary_tokens = _tokens(context_summary)
    evidence_tokens = _tokens(evidence_text)
    token_coverage = (
        len(summary_tokens.intersection(evidence_tokens)) / len(summary_tokens)
        if summary_tokens
        else 0.0
    )
    evaluation = {
        "status": "ok",
        "engine": "deterministic_grounding",
        "metric": "summary_token_coverage",
        "score": round(token_coverage, 4),
        "evidence_count": len(evidence),
        "unresolved_symbol_count": len(unresolved_symbols),
        "claim": "evidence_alignment_only",
        "detail": "This score is an alignment diagnostic, not proof that every generated claim is correct.",
    }
    if allow_ragas and evidence_text and context_summary:
        ragas_score, ragas_status = _ragas_similarity(evidence_text, context_summary)
        if ragas_score is not None:
            evaluation.update(
                {
                    "engine": "ragas",
                    "metric": "non_llm_string_similarity",
                    "score": round(ragas_score, 4),
                    "cache_hit": bool(ragas_status.get("cache_hit", False)),
                }
            )
        elif ragas_status.get("status") == "failed":
            evaluation["ragas"] = ragas_status
    return evaluation
