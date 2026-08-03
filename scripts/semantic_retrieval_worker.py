from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: semantic_retrieval_worker.py REQUEST.json RESPONSE.json", file=sys.stderr)
        return 2
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    model_name = str(request["model"])

    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device="cpu")
    request_groups = request.get("requests")
    if isinstance(request_groups, list):
        scores = []
        for group in request_groups:
            query = str(group["query"])
            texts = [str(text) for text in group["texts"]]
            embeddings = model.encode([query, *texts], normalize_embeddings=True, show_progress_bar=False)
            query_embedding = embeddings[0]
            scores.append([float(query_embedding @ embedding) for embedding in embeddings[1:]])
    else:
        query = str(request["query"])
        texts = [str(text) for text in request["texts"]]
        embeddings = model.encode([query, *texts], normalize_embeddings=True, show_progress_bar=False)
        query_embedding = embeddings[0]
        scores = [float(query_embedding @ embedding) for embedding in embeddings[1:]]
    Path(sys.argv[2]).write_text(
        json.dumps({"model": model_name, "scores": scores}, ensure_ascii=True),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
