"""Stato osservabile delle attività: unica fonte per UI, futuro HUD e Cockpit."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    TRANSCRIBING = "trascrizione"
    PLANNING = "pianificazione"
    AWAITING_CONFIRMATION = "attesa_conferma"
    EXECUTING = "esecuzione"
    RESPONDING = "risposta"
    DONE = "completato"
    STOPPED = "fermato"
    ERROR = "errore"

    @property
    def terminal(self) -> bool:
        return self in (Status.DONE, Status.STOPPED, Status.ERROR)


@dataclass
class Action:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class StepRecord:
    tool: str
    args: dict[str, Any]
    ok: bool
    summary: str
    verified: bool = False
    duration_ms: int = 0


@dataclass
class PendingConfirmation:
    action_hash: str
    tool: str
    preview: str


@dataclass
class Task:
    command: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: Status = Status.PLANNING
    intent: str = ""
    plan: list[Action] = field(default_factory=list)
    steps: list[StepRecord] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    pending: PendingConfirmation | None = None
    source: str = "testo"  # testo | voce
    level: int = 1         # 1 regole, 2 risposta del modello, 3 agente con strumenti
    metrics: dict[str, float] = field(default_factory=dict)  # misure reali (ms, €)
    tainted: bool = False  # ha letto dati privati: le azioni web richiedono conferma
    result: str = ""
    report: str = ""
    created_at: float = field(default_factory=time.time)

    def add_log(self, msg: str) -> None:
        self.log.append(f"{time.strftime('%H:%M:%S')} {msg}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d
