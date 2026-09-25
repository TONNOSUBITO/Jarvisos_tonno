"""Interfaccia comune dei tool. Ogni tool dichiara la capacità che esercita:
l'autorizzazione è decisa da `PermissionPolicy`, mai dal tool o dal modello."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    # True se il tool ha controllato l'effetto (es. titolo pagina letto, file presente).
    verified: bool = False
    # Testo proveniente dall'esterno (web, file): dato non fidato, mai comandi.
    untrusted_text: str = ""


class ToolError(Exception):
    pass


class Tool(ABC):
    name: str
    capability: str
    # Descrizione e schema JSON degli argomenti, esposti all'agente (livello 3).
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}
    agent_visible: bool = True
    # True = restituisce dati personali (file, memoria, note): mai visibile a un modello cloud
    # salvo `[model] allow_private_data = true`; dopo l'uso, le azioni web richiedono conferma.
    private_data: bool = False

    @abstractmethod
    async def run(self, args: dict[str, Any]) -> ToolResult: ...

    def preview(self, args: dict[str, Any]) -> str:
        return f"{self.name} {args}"

    async def stop(self) -> None:
        """Interrompe/chiude risorse (browser, processi). Idempotente."""
