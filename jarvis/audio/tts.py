"""Sintesi vocale.

- KokoroTTS: locale (kokoro-onnx, CPU). Voci italiane: if_sara, im_nicola.
- "browser": la UI usa speechSynthesis del browser (nessun lavoro lato server).
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from jarvis.audio.base import TextToSpeech, VoiceUnavailable, float32_to_wav


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


def make_tts(cfg) -> TextToSpeech | None:
    v = cfg.voice
    if v.tts_engine == "kokoro":
        return KokoroTTS(v.kokoro_model, v.kokoro_voices, v.tts_voice, v.tts_speed)
    return None  # "browser" o "none": nessuna sintesi lato server
