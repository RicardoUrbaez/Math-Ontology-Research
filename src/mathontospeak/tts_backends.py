from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol


class TTSBackend(Protocol):
    name: str

    def synthesize(self, text: str, ssml: str, output_path: str | Path) -> dict[str, Any]:
        ...


class MockTTSBackend:
    name = "mock"

    def synthesize(self, text: str, ssml: str, output_path: str | Path) -> dict[str, Any]:
        path = Path(output_path).with_suffix(".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"MOCK TTS TRANSCRIPT\n\nTEXT:\n{text}\n\nSSML:\n{ssml}\n",
            encoding="utf-8",
        )
        return {
            "backend": self.name,
            "status": "ok",
            "audio_path": str(path),
            "detail": "mock backend wrote transcript file",
        }


class GTTSBackend:
    name = "gtts"

    def __init__(self, fallback: TTSBackend | None = None) -> None:
        self.fallback = fallback or MockTTSBackend()

    def synthesize(self, text: str, ssml: str, output_path: str | Path) -> dict[str, Any]:
        path = Path(output_path).with_suffix(".mp3")
        try:
            from gtts import gTTS

            path.parent.mkdir(parents=True, exist_ok=True)
            gTTS(text=text, lang="en").save(str(path))
            return {"backend": self.name, "status": "ok", "audio_path": str(path), "detail": "gTTS MP3 written"}
        except Exception as exc:
            fallback_path = Path(output_path).with_suffix(".txt")
            result = self.fallback.synthesize(text, ssml, fallback_path)
            result.update(
                {
                    "backend": "mock",
                    "status": "warning",
                    "detail": f"gTTS unavailable or failed; fell back to mock transcript: {exc}",
                }
            )
            return result


class AzureTTSBackend:
    name = "azure"

    def __init__(
        self,
        speech_key: str | None = None,
        speech_region: str | None = None,
        fallback: TTSBackend | None = None,
    ) -> None:
        self.speech_key = speech_key or os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = speech_region or os.getenv("AZURE_SPEECH_REGION")
        self.fallback = fallback or MockTTSBackend()

    def synthesize(self, text: str, ssml: str, output_path: str | Path) -> dict[str, Any]:
        path = Path(output_path).with_suffix(".wav")
        if not self.speech_key or not self.speech_region:
            result = self.fallback.synthesize(text, ssml, Path(output_path).with_suffix(".txt"))
            result.update(
                {
                    "backend": "mock",
                    "status": "warning",
                    "detail": "Azure Speech is not configured; set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION. Fell back to mock.",
                }
            )
            return result
        try:
            import azure.cognitiveservices.speech as speechsdk

            path.parent.mkdir(parents=True, exist_ok=True)
            speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
            audio_config = speechsdk.audio.AudioOutputConfig(filename=str(path))
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            result = synthesizer.speak_ssml_async(ssml).get()
            if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                raise RuntimeError(getattr(result, "cancellation_details", result.reason))
            return {"backend": self.name, "status": "ok", "audio_path": str(path), "detail": "Azure WAV written"}
        except Exception as exc:
            fallback_result = self.fallback.synthesize(text, ssml, Path(output_path).with_suffix(".txt"))
            fallback_result.update(
                {
                    "backend": "mock",
                    "status": "warning",
                    "detail": f"Azure synthesis failed; fell back to mock transcript: {exc}",
                }
            )
            return fallback_result


def get_tts_backend(name: str) -> TTSBackend:
    normalized = (name or "mock").lower()
    if normalized == "mock":
        return MockTTSBackend()
    if normalized == "gtts":
        return GTTSBackend()
    if normalized == "azure":
        return AzureTTSBackend()
    raise ValueError(f"Unknown TTS backend: {name}")
