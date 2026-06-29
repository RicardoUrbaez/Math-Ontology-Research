from __future__ import annotations

import re
from typing import Any
from xml.sax.saxutils import escape as xml_escape


def escape_ssml_text(text: str) -> str:
    return xml_escape(text or "", {'"': "&quot;", "'": "&apos;"})


def _with_math_pauses(text: str, pause_ms: int) -> str:
    escaped = escape_ssml_text(text)
    escaped = re.sub(r"^([^:]{1,90}):\s+", rf'\1:<break time="{pause_ms}ms"/> ', escaped, count=1)
    escaped = re.sub(r";\s+", rf';<break time="{max(100, pause_ms // 2)}ms"/> ', escaped)
    escaped = re.sub(r"([.!?])\s+", rf'\1<break time="{pause_ms}ms"/> ', escaped)
    return escaped


def build_ssml(text: str, rate: str = "-10%", pitch: str = "+0%", pause_ms: int = 250) -> dict[str, str]:
    """Build Azure-style SSML and return it with a plain text fallback."""

    plain_text = re.sub(r"\s+", " ", text or "").strip()
    marked_text = _with_math_pauses(plain_text, pause_ms)
    ssml = (
        '<speak version="1.0" xml:lang="en-US" xmlns="http://www.w3.org/2001/10/synthesis">'
        '<voice name="en-US-JennyNeural">'
        f'<prosody rate="{escape_ssml_text(rate)}" pitch="{escape_ssml_text(pitch)}">'
        f"{marked_text}"
        "</prosody>"
        "</voice>"
        "</speak>"
    )
    return {"plain_text": plain_text, "ssml": ssml}


def build_all_surface_form_ssml(surface_forms: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        name: build_ssml(text)
        for name, text in surface_forms.items()
    }
