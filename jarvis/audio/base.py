"""Interfacce voce e decodifica audio.

Push-to-talk soltanto: l'audio arriva dalla UI solo mentre il tasto è premuto,
resta in memoria e non viene mai scritto su disco.
"""

from __future__ import annotations

import io
import wave
from abc import ABC, abstractmethod

import numpy as np

SAMPLE_RATE = 16000


class AudioError(Exception):
    pass


class VoiceUnavailable(Exception):
    """Motore voce non installato o non configurato."""


def wav_to_float32(wav_bytes: bytes, max_seconds: float = 30.0) -> np.ndarray:
    """WAV PCM16 → float32 mono 16 kHz (ricampiona linearmente se serve)."""
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            if w.getsampwidth() != 2:
                raise AudioError("Serve WAV PCM a 16 bit")
            ch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
            if n / sr > max_seconds:
                raise AudioError(f"Registrazione troppo lunga (> {max_seconds:.0f}s)")
            data = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
    except (wave.Error, EOFError) as e:
        raise AudioError(f"Audio non valido: {e}") from e
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != SAMPLE_RATE and len(data):
        idx = np.linspace(0, len(data) - 1, int(len(data) * SAMPLE_RATE / sr))
        data = np.interp(idx, np.arange(len(data)), data).astype(np.float32)
    return data


def float32_to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class SpeechToText(ABC):
    name = "base"

    @abstractmethod
    def transcribe(self, audio: np.ndarray, language: str = "it") -> str:
        """Bloccante: chiamare con asyncio.to_thread."""


class TextToSpeech(ABC):
    name = "base"
    content_type = "audio/wav"

    @abstractmethod
    async def synthesize(self, text: str) -> bytes: ...


class MockSTT(SpeechToText):
    name = "mock"

    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def transcribe(self, audio, language="it") -> str:
        self.calls += 1
        return self.text


class MockTTS(TextToSpeech):
    name = "mock"

    def __init__(self):
        self.spoken: list[str] = []

    async def synthesize(self, text: str) -> bytes:
        self.spoken.append(text)
        return float32_to_wav(np.zeros(1600, dtype=np.float32), SAMPLE_RATE)
