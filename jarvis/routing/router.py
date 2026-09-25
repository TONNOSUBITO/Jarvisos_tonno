"""Instradamento delle richieste.

Livello 1: regole deterministiche locali (costo zero, nessuna rete).
Livello 2/3: modello / agente — non attivi in Fase 1.
Un adattatore Jev (TypeSafe) potrà implementare `IntentRouter` in Fase 3,
solo dopo un confronto misurato con `RuleRouter`.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Intent:
    kind: str  # open_app | web_search | web_search_open | web_open | note | stop | unknown
    slots: dict[str, str] = field(default_factory=dict)
    level: int = 1
    confidence: float = 1.0


class IntentRouter(ABC):
    @abstractmethod
    def route(self, text: str) -> Intent: ...


_WAKE = re.compile(r"^(?:ehi\s+|hey\s+|ok\s+)?jarvis[\s,:!]*", re.I)
_URL = re.compile(r"^(?:https?://)?[\w\-]+(?:\.[\w\-]+)+(?::\d+)?(?:/\S*)?$", re.I)

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("stop", re.compile(r"^(?:stop|fermati|ferma(?:ti)? tutto|basta|annulla)$")),
    ("web_search_open", re.compile(
        r"^(?:cerca e apri|trova e apri|apri il primo risultato (?:per|di|su))\s+(?P<query>.+)$")),
    ("web_open", re.compile(r"^(?:apri|vai su|visita)\s+(?:il sito|la pagina|il link)\s+(?P<url>\S+)$")),
    ("web_search", re.compile(
        r"^(?:cerca|ricerca|trova)(?:\s+(?:su internet|online|sul web|in rete))?\s+(?P<query>.+)$")),
    ("note", re.compile(
        r"^(?:prepara|crea|scrivi)\s+(?:una?\s+)?(?:nota|report|appunto)"
        r"(?:\s+(?:sulla|sullo|sul|su|per|con)(?=\s))?\s*:?\s*(?P<text>.+)$")),
    ("open_app", re.compile(r"^(?:apri|avvia|lancia|esegui)\s+(?:l'app\s+|l'applicazione\s+|il programma\s+)?(?P<app>.+)$")),
]


def normalize(text: str) -> str:
    t = text.strip()
    t = _WAKE.sub("", t)
    t = re.sub(r"\s+", " ", t)
    t = t.rstrip(".!?;")
    return t.strip()


class RuleRouter(IntentRouter):
    """Regole in italiano per i comandi della Fase 1."""

    def route(self, text: str) -> Intent:
        t = normalize(text)
        low = t.lower()
        src = t if len(low) == len(t) else low  # lower() può cambiare lunghezza (rari unicode)
        for kind, rx in _RULES:
            m = rx.match(low)
            if not m:
                continue
            # recupera gli slot dal testo originale (mantiene maiuscole)
            slots = {k: src[m.start(k):m.end(k)].strip() for k in m.groupdict()}
            if kind == "web_open" and not _URL.match(slots["url"]):
                continue
            if kind == "open_app" and _URL.match(slots["app"]):
                return Intent("web_open", {"url": slots["app"]})
            return Intent(kind, slots)
        return Intent("unknown", {"text": t}, level=2, confidence=0.0)
