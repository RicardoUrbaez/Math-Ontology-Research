from __future__ import annotations

import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaperJobManager:
    """Single-worker local queue so OCR and local LLM work do not compete for the GPU."""

    def __init__(
        self,
        analyzer: Callable[..., dict[str, Any]],
        cache_dir: Path | None = None,
    ) -> None:
        self.analyzer = analyzer
        self.cache_dir = cache_dir or Path(
            os.getenv(
                "MATHONTOSPEAK_CACHE_DIR",
                str(Path.home() / ".cache" / "mathontospeak"),
            )
        ) / "jobs"
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mathontospeak-paper")

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = _now()
        job = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": "",
        }
        self._store(job)
        self._executor.submit(self._run, job_id, request)
        return dict(job)

    def get(self, job_id: str) -> dict[str, Any] | None:
        if not job_id.isalnum():
            return None
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return dict(job)
        path = self.cache_dir / f"{job_id}.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(loaded, dict):
            return None
        if loaded.get("status") in {"queued", "processing"}:
            loaded.update(
                {
                    "status": "failed",
                    "stage": "interrupted",
                    "progress": 100,
                    "updated_at": _now(),
                    "error": "The local API restarted during analysis. Your PDF is unchanged; submit it again to resume with the extraction cache.",
                }
            )
            self._store(loaded)
        return loaded

    def _run(self, job_id: str, request: dict[str, Any]) -> None:
        self._update(job_id, status="processing", stage="extracting_document", progress=10)
        def report_progress(stage: str, progress: int) -> None:
            self._update(
                job_id,
                status="processing",
                stage=stage,
                progress=max(10, min(int(progress), 99)),
            )
        try:
            result = self.analyzer(**request, progress_callback=report_progress)
        except Exception as exc:  # noqa: BLE001 - convert background failures into job state.
            self._update(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                error=f"{type(exc).__name__}: {exc}",
            )
            return
        try:
            json.dumps(result, ensure_ascii=True)
        except (TypeError, ValueError, RecursionError) as exc:
            self._update(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                error=f"Analysis result could not be encoded as JSON: {type(exc).__name__}: {exc}",
            )
            return
        self._update(
            job_id,
            status="complete",
            stage="complete",
            progress=100,
            result=result,
        )

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            current = dict(self._jobs.get(job_id) or {"job_id": job_id, "created_at": _now()})
        current.update(changes)
        current["updated_at"] = _now()
        self._store(current)

    def _store(self, job: dict[str, Any]) -> None:
        with self._lock:
            self._jobs[str(job["job_id"])] = dict(job)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            target = self.cache_dir / f"{job['job_id']}.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(job, ensure_ascii=True), encoding="utf-8")
            temporary.replace(target)
        except OSError:
            pass
