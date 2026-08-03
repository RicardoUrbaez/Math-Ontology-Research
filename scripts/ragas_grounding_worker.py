from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def score(reference: str, response: str) -> float:
    from ragas.metrics.collections import DistanceMeasure, NonLLMStringSimilarity

    metric = NonLLMStringSimilarity(distance_measure=DistanceMeasure.JARO_WINKLER)
    result = await metric.ascore(reference=reference, response=response)
    return float(result.value)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: ragas_grounding_worker.py REQUEST.json RESPONSE.json", file=sys.stderr)
        return 2
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    value = asyncio.run(score(str(request["reference"]), str(request["response"])))
    Path(sys.argv[2]).write_text(json.dumps({"score": value}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
