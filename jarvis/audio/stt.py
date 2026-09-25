"""Trascrizione locale. Nessun audio viene inviato in rete.

Il modello `base` multilingue si scarica da Hugging Face al primo uso.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from jarvis.audio.base import SpeechToText, VoiceUnavailable


class FasterWhisperSTT(SpeechToText):
    name = "faster-whisper"

    def __init__(self, model: str = "base", models_dir: Path = Path("data/models/whisper")):
        self.model_name = model
        self.models_dir = models_dir
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
        segs, _ = self._load().transcribe(audio, language=language, beam_size=1,
                                          vad_filter=True, condition_on_previous_text=False)
        return "".join(s.text for s in segs).strip()


def make_stt(engine: str, model: str, data_dir: Path) -> SpeechToText | None:
    if engine == "faster-whisper":
        return FasterWhisperSTT(model, Path(data_dir) / "models" / "whisper")
    return None
