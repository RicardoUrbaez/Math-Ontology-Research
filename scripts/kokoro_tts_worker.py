from __future__ import annotations

import json
import sys
from pathlib import Path


RESULT_PREFIX = "MATHONTOSPEAK_KOKORO="


def synthesize(request_path: Path) -> dict[str, object]:
    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KPipeline

    request = json.loads(request_path.read_text(encoding="utf-8"))
    text = str(request.get("text") or "").strip()
    output_path = Path(str(request.get("output_path") or ""))
    if not text or not output_path:
        raise ValueError("Kokoro requires text and an output path.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipeline = KPipeline(lang_code="a", device=device)
    voice = str(request.get("voice") or "af_heart")
    speed = float(request.get("speed") or 0.92)
    pieces = [audio for _graphemes, _phonemes, audio in pipeline(text, voice=voice, speed=speed)]
    if not pieces:
        raise RuntimeError("Kokoro returned no audio samples.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.concatenate([np.asarray(piece, dtype=np.float32) for piece in pieces])
    sf.write(str(output_path), audio, 24000)
    return {
        "status": "ok",
        "backend": "kokoro",
        "audio_path": str(output_path),
        "voice": voice,
        "sample_rate": 24000,
        "device": device,
        "segments": len(pieces),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: kokoro_tts_worker.py REQUEST_JSON", file=sys.stderr)
        return 2
    try:
        payload = synthesize(Path(sys.argv[1]))
    except Exception as exc:  # noqa: BLE001 - the worker reports failures to the API process.
        print(RESULT_PREFIX + json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(RESULT_PREFIX + json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
