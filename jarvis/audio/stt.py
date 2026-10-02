"""Trascrizione locale. Nessun audio viene inviato in rete.

Il modello `base` multilingue si scarica da Hugging Face al primo uso.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from jarvis.audio.base import SpeechToText, VoiceUnavailable


# Suggerimento al decoder con le parole dei comandi: misurato su 16 frasi sintetiche con rumore
# (Kokoro, 2 voci) il modello `base` passa da 4/16 a 10/16 trascrizioni esatte (con beam_size=5).
COMMAND_PROMPT = ("Comandi a Jarvis: cerca, cerca e apri, apri, ricorda che, prepara una nota, elenca i file, "
                  "cerca nelle note, dimentica, fermati. Esempi: cerca meteo Roma; apri la calcolatrice.")


def command_prompt(apps: list[str] | None = None) -> str:
    return COMMAND_PROMPT + (" App: " + ", ".join(apps) + "." if apps else "")


class FasterWhisperSTT(SpeechToText):
    name = "faster-whisper"

    def __init__(self, model: str = "base", models_dir: Path = Path("data/models/whisper"),
                 prompt: str = COMMAND_PROMPT, beam_size: int = 5):
        self.model_name = model
        self.models_dir = models_dir
        self.prompt = prompt
        self.beam_size = beam_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as e:
                    raise VoiceUnavailable("faster-whisper non installato: pip install -e .[voice]") from e
                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8",
                                           download_root=str(self.models_dir))
            return self._model

    def transcribe(self, audio: np.ndarray, language: str = "it") -> str:
        segs, _ = self._load().transcribe(audio, language=language, beam_size=self.beam_size,
                                          initial_prompt=self.prompt or None,
                                          vad_filter=True, condition_on_previous_text=False)
        return "".join(s.text for s in segs).strip()


def make_stt(engine: str, model: str, data_dir: Path, apps: list[str] | None = None) -> SpeechToText | None:
    if engine == "faster-whisper":
        return FasterWhisperSTT(model, Path(data_dir) / "models" / "whisper", command_prompt(apps))
    return None
