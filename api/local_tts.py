from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def kokoro_python_path() -> Path:
    configured = os.getenv("MATHONTOSPEAK_KOKORO_PYTHON", "").strip()
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


def kokoro_runtime_status() -> dict[str, Any]:
    python_path = kokoro_python_path()
    site_packages = python_path.parent.parent / "Lib" / "site-packages"
    available = (
        python_path.is_file()
        and (site_packages / "kokoro").is_dir()
        and ((site_packages / "soundfile.py").is_file() or (site_packages / "soundfile").is_dir())
    )
    return {
        "available": available,
        "engine": "Kokoro-82M",
        "python": str(python_path),
        "voice": os.getenv("MATHONTOSPEAK_KOKORO_VOICE", "af_heart"),
        "device_policy": "CUDA when available, otherwise CPU",
        "model": "hexgrad/Kokoro-82M",
        "license": "Apache-2.0 model weights",
        "detail": (
            "Local neural speech is ready."
            if available
            else "Install kokoro and soundfile in the configured isolated runtime."
        ),
    }
