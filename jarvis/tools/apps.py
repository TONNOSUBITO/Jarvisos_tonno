"""Apertura di app approvate, con adapter per sistema operativo.

Solo app presenti nell'allowlist del dispositivo (`[apps]` nel TOML), lanciate
come lista di argomenti senza shell. Gli adapter nativi NON sono testati in cloud.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from jarvis.tools.base import Tool, ToolResult


class AppAdapter(ABC):
    @abstractmethod
    async def launch(self, argv: list[str]) -> tuple[bool, str]: ...


class MockAppAdapter(AppAdapter):
    """Usato in cloud e nei test: registra i lanci senza eseguire nulla."""

    def __init__(self):
        self.launched: list[list[str]] = []

    async def launch(self, argv: list[str]) -> tuple[bool, str]:
        self.launched.append(argv)
        return True, f"[mock] avvio simulato: {' '.join(argv)}"


class NativeAppAdapter(AppAdapter):
    """Windows/Linux: Popen senza shell, verifica che il processo sia partito."""

    async def launch(self, argv: list[str]) -> tuple[bool, str]:
        exe = argv[0]
        if shutil.which(exe) is None and not _is_path(exe):
            return False, f"Eseguibile non trovato: {exe}"
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, close_fds=True)
        except OSError as e:
            return False, f"Avvio fallito: {e}"
        await asyncio.sleep(0.5)
        code = proc.poll()
        # alcune app (launcher) terminano subito con 0 dopo aver aperto la finestra
        if code not in (None, 0):
            return False, f"Processo terminato con codice {code}"
        return True, f"Avviato {exe} (pid {proc.pid})"


def _is_path(s: str) -> bool:
    return "/" in s or "\\" in s


def make_adapter(kind: str) -> AppAdapter:
    return NativeAppAdapter() if kind == "native" else MockAppAdapter()


class OpenAppTool(Tool):
    name = "app.open"
    capability = "app.open"
    description = "Apre un'applicazione approvata sul PC, indicata per nome."
    parameters = {"type": "object", "properties": {"app": {"type": "string"}}, "required": ["app"]}

    def __init__(self, allowed_apps: dict[str, list[str]], adapter: AppAdapter):
        self.allowed = {k.lower(): v for k, v in allowed_apps.items()}
        self.adapter = adapter

    def resolve(self, app: str) -> list[str] | None:
        return self.allowed.get(app.strip().lower())

    async def run(self, args: dict[str, Any]) -> ToolResult:
        app = args["app"]
        argv = self.resolve(app)
        if not argv:
            known = ", ".join(sorted(self.allowed)) or "nessuna"
            return ToolResult(False, f"«{app}» non è tra le app approvate (approvate: {known})")
        ok, msg = await self.adapter.launch(list(argv))
        return ToolResult(ok, msg, {"app": app, "argv": argv}, verified=ok)

    def preview(self, args: dict[str, Any]) -> str:
        return f"Aprire l'app approvata «{args.get('app')}»"
