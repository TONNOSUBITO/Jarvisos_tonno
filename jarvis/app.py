"""Assemblaggio dei componenti a partire dalla configurazione del dispositivo."""

from __future__ import annotations

from pathlib import Path

from jarvis.config import DeviceConfig
from jarvis.core.orchestrator import Orchestrator
from jarvis.memory.vault import Vault
from jarvis.routing.router import RuleRouter
from jarvis.tools.apps import AppAdapter, OpenAppTool, make_adapter
from jarvis.tools.audit import AuditLog
from jarvis.tools.browser import BrowserSession, WebOpenTool, WebSearchTool
from jarvis.tools.notes import DraftNoteTool, SaveNoteTool


def build_orchestrator(cfg: DeviceConfig, app_adapter: AppAdapter | None = None) -> Orchestrator:
    data = Path(cfg.data_dir)
    session = BrowserSession(cfg.browser, data / "browser-profile")
    vault = Vault(cfg.vault_dir)
    tools = [
        OpenAppTool(cfg.allowed_apps, app_adapter or make_adapter(cfg.app_adapter)),
        WebSearchTool(session),
        WebOpenTool(session),
        DraftNoteTool(),
        SaveNoteTool(vault),
    ]
    audit = AuditLog(data / "audit.jsonl", cfg.device_id)
    orch = Orchestrator(cfg, RuleRouter(), tools, audit)
    orch.vault = vault  # esposto alla UI per elenco/cancellazione note
    return orch
