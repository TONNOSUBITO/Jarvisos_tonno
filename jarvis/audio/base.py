"""Interfacce voce. NON IMPLEMENTATE in Fase 1 (nessun microfono in cloud).

Fase 2: `WhisperCppSTT` (whisper.cpp, modello multilingue `base`, locale) e
`KokoroTTS` (Kokoro-82M, lingua 'i', 1 voce femminile + 1 maschile italiane,
qualità da verificare sul PC). Fase 3: `FishAudioTTS` opt-in (invia testo a un
servizio esterno). Push-to-talk soltanto: nessun ascolto continuo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SpeechToText(ABC):
    @abstractmethod
    async def transcribe(self, wav_bytes: bytes, language: str = "it") -> str: ...


class TextToSpeech(ABC):
    local: bool = True  # False = invia testo a un servizio esterno

    @abstractmethod
    async def synthesize(self, text: str) -> bytes: ...


class MockSTT(SpeechToText):
    def __init__(self, text: str):
        self.text = text

    async def transcribe(self, wav_bytes: bytes, language: str = "it") -> str:
        return self.text


class NullTTS(TextToSpeech):
    async def synthesize(self, text: str) -> bytes:
        return b""


class WhisperCppSTT(SpeechToText):
    async def transcribe(self, wav_bytes: bytes, language: str = "it") -> str:
        raise NotImplementedError("Fase 2: whisper.cpp da integrare e misurare sul PC reale")


class KokoroTTS(TextToSpeech):
    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError("Fase 2: Kokoro da integrare e ascoltare sul PC reale")
