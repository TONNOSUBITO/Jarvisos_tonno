"""Assemblaggio dei componenti a partire dalla configurazione del dispositivo."""

from __future__ import annotations

from pathlib import Path

from jarvis.audio.stt import make_stt
from jarvis.audio.tts import make_tts
from jarvis.config import DeviceConfig
from jarvis.core.agent import Agent
from jarvis.core.orchestrator import Orchestrator
from jarvis.memory.vault import Vault
from jarvis.providers.base import BudgetMeter, ModelProvider, build_provider
from jarvis.routing.router import RuleRouter
from jarvis.tools.apps import AppAdapter, OpenAppTool, make_adapter
from jarvis.tools.audit import AuditLog
from jarvis.tools.browser import BrowserSession, WebOpenTool, WebSearchTool
from jarvis.tools.files import (DeleteFileTool, ListFilesTool, MoveFileTool, ReadFileTool, WorkDir,
                                WriteFileTool)
from jarvis.tools.memory import ForgetTool, ListMemoryTool, MemoryStore, RememberTool, SearchNotesTool
from jarvis.tools.notes import SaveNoteTool


def build_orchestrator(cfg: DeviceConfig, app_adapter: AppAdapter | None = None,
                       provider: ModelProvider | None = None, stt=None, tts=None) -> Orchestrator:
    data = Path(cfg.data_dir)
    session = BrowserSession(cfg.browser, data / "browser-profile")
    vault = Vault(cfg.vault_dir)
    memory = MemoryStore(vault)
    wd = WorkDir(cfg.work_dir)
    tools = [
        OpenAppTool(cfg.allowed_apps, app_adapter or make_adapter(cfg.app_adapter)),
        WebSearchTool(session),
        WebOpenTool(session),
        SaveNoteTool(vault),
        RememberTool(memory), ListMemoryTool(memory), ForgetTool(memory), SearchNotesTool(vault),
        ListFilesTool(wd), ReadFileTool(wd), WriteFileTool(wd), MoveFileTool(wd), DeleteFileTool(wd),
    ]
    audit = AuditLog(data / "audit.jsonl", cfg.device_id)
    orch = Orchestrator(cfg, RuleRouter(), tools, audit)
    orch.vault = vault
    orch.memory = memory
    orch.budget = BudgetMeter(cfg.limits.budget_eur)
    if provider is None:
        provider = build_provider(cfg.model, orch.budget)
    if provider is not None:
        orch.agent = Agent(provider, use_tools=cfg.model.agent_tools, timeout_s=cfg.model.timeout_s)
    orch.stt = stt if stt is not None else make_stt(cfg.voice.stt_engine, cfg.voice.stt_model, data)
    orch.tts = tts if tts is not None else make_tts(cfg)
    return orch
