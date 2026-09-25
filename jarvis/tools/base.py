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

    @abstractmethod
    async def run(self, args: dict[str, Any]) -> ToolResult: ...

    def preview(self, args: dict[str, Any]) -> str:
        return f"{self.name} {args}"

    async def stop(self) -> None:
        """Interrompe/chiude risorse (browser, processi). Idempotente."""
