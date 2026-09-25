"""Sintesi vocale.

- KokoroTTS: locale (kokoro-onnx, CPU). Voci italiane: if_sara, im_nicola.
- FishAudioTTS: CLOUD, opt-in. Invia il testo a api.fish.audio. Richiede
  `FISH_API_KEY` in .env e la capacità `tts.cloud` diversa da `deny`.
- "browser": la UI usa speechSynthesis del browser (nessun lavoro lato server).
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

import httpx

from jarvis.audio.base import TextToSpeech, VoiceUnavailable, float32_to_wav

FISH_TTS_URL = "https://api.fish.audio/v1/tts"  # verificato su docs.fish.audio, 25/09/2026


class KokoroTTS(TextToSpeech):
    name = "kokoro"

    def __init__(self, model_path: str, voices_path: str, voice: str = "if_sara", speed: float = 1.0):
        self.model_path = model_path
        self.voices_path = voices_path
        self.voice = voice
        self.speed = speed
        self._k = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._k is None:
                try:
                    from kokoro_onnx import Kokoro
                except ImportError as e:
                    raise VoiceUnavailable("kokoro-onnx non installato: pip install -e .[tts]") from e
                for p in (self.model_path, self.voices_path):
                    if not Path(p).exists():
                        raise VoiceUnavailable(f"File modello Kokoro mancante: {p} (vedi scripts/download_models.py)")
                self._k = Kokoro(self.model_path, self.voices_path)
            return self._k

    def _synth(self, text: str) -> bytes:
        samples, sr = self._load().create(text, voice=self.voice, speed=self.speed, lang="it")
        return float32_to_wav(samples, sr)

    async def synthesize(self, text: str) -> bytes:
        return await asyncio.to_thread(self._synth, text[:1000])


class FishAudioTTS(TextToSpeech):
    name = "fish"
    local = False

    def __init__(self, model: str = "s2.1-pro-free", reference_id: str = "", api_key: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.model = model
        self.reference_id = reference_id
        self.api_key = api_key if api_key is not None else os.environ.get("FISH_API_KEY", "")
        self._transport = transport

    async def synthesize(self, text: str) -> bytes:
        if not self.api_key:
            raise VoiceUnavailable("FISH_API_KEY mancante nel file .env")
        body: dict = {"text": text[:1000], "format": "wav"}
        if self.reference_id:
            body["reference_id"] = self.reference_id
        headers = {"Authorization": f"Bearer {self.api_key}", "model": self.model}
        async with httpx.AsyncClient(timeout=30, transport=self._transport) as c:
            r = await c.post(FISH_TTS_URL, json=body, headers=headers)
            if r.status_code != 200:
                raise VoiceUnavailable(f"Fish Audio ha risposto {r.status_code}")
            return r.content


def make_tts(cfg) -> TextToSpeech | None:
    v = cfg.voice
    if v.tts_engine == "kokoro":
        return KokoroTTS(v.kokoro_model, v.kokoro_voices, v.tts_voice, v.tts_speed)
    if v.tts_engine == "fish":
        return FishAudioTTS(v.fish_model, v.fish_reference_id)
    return None  # "browser" o "none": nessuna sintesi lato server
