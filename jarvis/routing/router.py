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


class IntentRouter(ABC):
    @abstractmethod
    def route(self, text: str) -> Intent: ...


_WAKE = re.compile(r"^(?:ehi\s+|hey\s+|ok\s+)?jarvis[\s,:!]*", re.I)
_URL = re.compile(r"^(?:https?://)?[\w\-]+(?:\.[\w\-]+)+(?::\d+)?(?:/\S*)?$", re.I)

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("stop", re.compile(r"^(?:stop|fermati|ferma(?:ti)? tutto|basta|annulla)$")),
    ("memory_list", re.compile(r"^(?:cosa ricordi(?: di me)?|cosa sai di me|mostra(?:mi)? (?:la )?memoria)$")),
    ("remember", re.compile(r"^(?:ricorda(?:ti)?(?: che)?|memorizza(?: che)?)\s+(?P<fact>.+)$")),
    ("forget", re.compile(r"^(?:dimentica(?: che)?|cancella dalla memoria)\s+(?P<query>.+)$")),
    ("vault_search", re.compile(r"^(?:cerca|trova) nelle (?:mie )?note\s+(?P<query>.+)$")),
    ("files_list", re.compile(r"^(?:elenca|mostra(?:mi)?) (?:i )?file(?:\s+(?:in|nella cartella)\s+(?P<path>.+))?$")),
    ("files_read", re.compile(r"^(?:leggi|apri) (?:il )?file\s+(?P<path>.+)$")),
    ("files_delete", re.compile(r"^(?:elimina|cancella|cestina) (?:il )?file\s+(?P<path>.+)$")),
    ("files_move", re.compile(r"^(?:sposta|rinomina) (?:il )?file\s+(?P<src>.+?)\s+(?:in|a|come)\s+(?P<dst>.+)$")),
    ("web_search_open", re.compile(
        r"^(?:(?:cerca|trova)\s+(?:e|ed|i|e poi|poi)\s+apri|apri il primo risultato (?:per|di|su))\s+(?P<query>.+)$")),
    ("web_open", re.compile(r"^(?:apri|vai su|visita)\s+(?:(?:il sito|la pagina|il link)\s+)?(?P<url>\S+)$")),
    ("web_search", re.compile(
        r"^(?:cerca|ricerca|trova)(?:\s+(?:su internet|online|sul web|in rete))?\s+(?P<query>.+)$")),
    ("note", re.compile(
        r"^(?:prepara|crea|scrivi)\s+(?:una?\s+)?(?:nota|report|appunto)"
        r"(?:\s+(?:sulla|sullo|sul|su|per|con)(?=\s))?\s*:?\s*(?P<text>.+)$")),
    ("open_app", re.compile(r"^(?:apri|avvia|lancia|esegui)\s+(?:l'app\s+|l'applicazione\s+|il programma\s+)?(?P<app>.+)$")),
]


_VERB_MAP = {"aprire": "apri", "aprimi": "apri", "apri mi": "apri", "cercare": "cerca", "cercami": "cerca",
             "trovare": "trova", "trovami": "trova", "avviare": "avvia", "ricordare": "ricorda",
             "fermare": "ferma", "preparare": "prepara", "preparami": "prepara", "creare": "crea",
             "scrivere": "scrivi", "scrivimi": "scrivi", "leggere": "leggi", "leggimi": "leggi",
             "elencare": "elenca", "elencami": "elenca", "dimenticare": "dimentica"}
_VERBS = re.compile(r"^(" + "|".join(sorted(_VERB_MAP, key=len, reverse=True)) + r")\b", re.I)


def normalize(text: str) -> str:
    # la trascrizione vocale aggiunge punteggiatura e maiuscole: la togliamo ai bordi
    t = text.strip().strip("\"'«»“”")
    t = _WAKE.sub("", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[.!?;,]+$", "", t)
    t = re.sub(r"[\s,]+(?:per favore|grazie)$", "", t, flags=re.I)
    # forme cortesi/infinite del parlato → imperativo delle regole ("puoi aprire" → "apri")
    t = re.sub(r"^(?:per favore\s+)?(?:mi\s+)?(?:(?:puoi|potresti|riesci a|vorrei|voglio)\s+)?", "", t, flags=re.I)
    t = _VERBS.sub(lambda m: _VERB_MAP[m.group(1).lower()], t)
    t = re.sub(r"\bappr[iì]\b", "apri", t, flags=re.I)  # Whisper sente «apri» come «apprì»
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
            slots = {k: src[m.start(k):m.end(k)].strip() for k, v in m.groupdict().items() if v is not None}
            if kind == "web_open" and not _URL.match(slots["url"]):
                continue
            if kind == "open_app" and _URL.match(slots["app"]):
                return Intent("web_open", {"url": slots["app"]})
            return Intent(kind, slots)
        return Intent("unknown", {"text": t})
