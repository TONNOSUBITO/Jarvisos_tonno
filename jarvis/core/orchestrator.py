"""Orchestratore: comando → intento → piano → tool (con permessi) → verifica → resoconto.

Garanzie:
- Stop: cancella il task asyncio (anche a metà di un tool) e chiude le risorse.
- Timeout per task e per tool, limite di passi, nessun retry automatico.
- Conferma puntuale per le capacità in modalità `confirm`, legata all'hash dell'azione.
- Il testo esterno (untrusted_text) viene mostrato ma mai riusato come comando.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from jarvis.config import DeviceConfig
from jarvis.core.report import build_report
from jarvis.core.state import Action, PendingConfirmation, Status, StepRecord, Task
from jarvis.routing.router import Intent, IntentRouter
from jarvis.tools.audit import AuditLog, redact
from jarvis.tools.base import Tool, ToolResult
from jarvis.tools.permissions import Decision, PermissionPolicy, action_hash

# Riferimento a un risultato precedente negli argomenti di un'azione.
FIRST_RESULT_URL = "$prev.first_result_url"


class StepLimitExceeded(Exception):
    pass


def plan_for(intent: Intent) -> list[Action]:
    s = intent.slots
    match intent.kind:
        case "open_app":
            return [Action("app.open", {"app": s["app"]}, f"apro l'app «{s['app']}»")]
        case "web_search":
            return [Action("web.search", {"query": s["query"]}, f"cerco «{s['query']}»")]
        case "web_search_open":
            return [Action("web.search", {"query": s["query"]}, f"cerco «{s['query']}»"),
                    Action("web.open", {"url": FIRST_RESULT_URL}, "apro il primo risultato")]
        case "web_open":
            return [Action("web.open", {"url": s["url"]}, f"apro {s['url']}")]
        case "remember":
            return [Action("memory.remember", {"fact": s["fact"]}, "memorizzo (solo dopo conferma)")]
        case "memory_list":
            return [Action("memory.list", {}, "leggo la memoria")]
        case "forget":
            return [Action("memory.forget", {"query": s["query"]}, f"dimentico «{s['query']}» (dopo conferma)")]
        case "vault_search":
            return [Action("vault.search", {"query": s["query"]}, f"cerco «{s['query']}» nelle note")]
        case "files_list":
            return [Action("files.list", {"path": s.get("path", "")}, "elenco i file")]
        case "files_read":
            return [Action("files.read", {"path": s["path"]}, f"leggo {s['path']}")]
        case "files_delete":
            return [Action("files.delete", {"path": s["path"]}, f"sposto nel cestino {s['path']} (dopo conferma)")]
        case "files_move":
            return [Action("files.move", {"src": s["src"], "dst": s["dst"]}, f"sposto {s['src']} (dopo conferma)")]
        case "skill_save":
            return [Action("skills.save", {"name": s["name"], "text": s["text"]}, "salvo la skill (dopo conferma)")]
        case "skill_list":
            return [Action("skills.list", {}, "elenco le skill")]
        case "skill_read":
            return [Action("skills.read", {"name": s["name"]}, f"leggo la skill «{s['name']}»")]
        case "note":
            return [Action("notes.save", {"title": s["text"][:60], "body": s["text"], "folder": "inbox"},
                           "salvo la nota (solo dopo conferma)")]
    return []


class Orchestrator:
    def __init__(self, config: DeviceConfig, router: IntentRouter, tools: list[Tool],
                 audit: AuditLog):
        self.config = config
        self.router = router
        self.tools = {t.name: t for t in tools}
        self.policy = PermissionPolicy(config)
        self.audit = audit
        self.tasks: dict[str, Task] = {}
        self._runners: dict[str, asyncio.Task] = {}
        self._confirm: dict[str, tuple[asyncio.Event, list[bool]]] = {}
        self.vault = None  # impostato da build_orchestrator
        self.stt = None    # SpeechToText, opzionale
        self.agent = None  # Agent (livelli 2-3), opzionale
        self.tts = None    # TextToSpeech lato server, opzionale
        self.memory = None
        self.budget = None
        self.jev = None    # JevRouter, opzionale: solo quando le regole non capiscono
        self.last_provider = ""  # ultimo provider che ha risposto (mostrato nell'HUD)

    # ---------- API pubblica ----------
    def submit(self, text: str = "", audio=None) -> Task:
        """Testo, oppure audio (float32 16 kHz) da trascrivere localmente."""
        task = Task(command=text.strip()[:500], source="voce" if audio is not None else "testo")
        if audio is not None:
            task.status = Status.TRANSCRIBING
        self.tasks[task.id] = task
        self._runners[task.id] = asyncio.create_task(self._run_guarded(task, audio))
        return task

    async def wait(self, task_id: str) -> Task:
        runner = self._runners.get(task_id)
        if runner:
            try:
                await runner
            except asyncio.CancelledError:
                pass
        return self.tasks[task_id]

    def confirm(self, task_id: str, given_hash: str, approve: bool) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.pending is None or task_id not in self._confirm:
            return False
        if approve and not self.policy.consume_confirmation(task.pending.action_hash, given_hash):
            return False
        if not approve and given_hash != task.pending.action_hash:
            return False
        ev, box = self._confirm[task_id]
        box.append(approve)
        ev.set()
        return True

    async def stop(self, task_id: str | None = None, exclude: str | None = None) -> list[str]:
        """Ferma un task o, senza id, tutti (interruttore di emergenza)."""
        ids = [task_id] if task_id else [i for i, t in self.tasks.items()
                                         if not t.status.terminal and i != exclude]
        stopped = []
        for i in ids:
            runner = self._runners.get(i)
            task = self.tasks.get(i)
            if task is None or task.status.terminal:
                continue
            if runner and not runner.done():
                runner.cancel()
                try:
                    await runner
                except (asyncio.CancelledError, Exception):
                    pass
            if not task.status.terminal:
                self._finish(task, Status.STOPPED, "Fermato dall'utente")
            stopped.append(i)
        for tool in self.tools.values():
            await tool.stop()
        return stopped

    # ---------- esecuzione ----------
    def _set(self, task: Task, status: Status, msg: str | None = None) -> None:
        task.status = status
        if msg:
            task.add_log(msg)

    def _finish(self, task: Task, status: Status, result: str) -> None:
        task.pending = None
        task.result = result
        task.report = build_report(task, status)
        self._set(task, status, result)
        self.audit.write("task_end", task=task.id, status=status.value, result=result,
                         steps=[{"tool": s.tool, "ok": s.ok} for s in task.steps])

    async def _run_guarded(self, task: Task, audio=None) -> None:
        try:
            await asyncio.wait_for(self._run(task, audio), timeout=self.config.limits.task_timeout_s)
        except asyncio.TimeoutError:
            self._finish(task, Status.ERROR, f"Timeout attività ({self.config.limits.task_timeout_s:.0f}s)")
        except asyncio.CancelledError:
            if not task.status.terminal:
                self._finish(task, Status.STOPPED, "Fermato dall'utente")
            raise
        except StepLimitExceeded as e:
            self._finish(task, Status.ERROR, str(e))
        except Exception as e:  # noqa: BLE001 — l'errore va mostrato, non propagato
            self._finish(task, Status.ERROR, f"Errore: {redact(str(e))[:300]}")
        finally:
            self._confirm.pop(task.id, None)

    async def _run(self, task: Task, audio=None) -> None:
        t_start = time.monotonic()
        if audio is not None:
            if self.stt is None:
                self._finish(task, Status.ERROR, "Trascrizione non configurata ([voice] stt_engine)")
                return
            self._set(task, Status.TRANSCRIBING, f"Trascrivo {len(audio) / 16000:.1f}s di audio (locale)")
            text = await asyncio.to_thread(self.stt.transcribe, audio, self.config.voice.stt_language)
            task.metrics["stt_ms"] = round((time.monotonic() - t_start) * 1000)
            task.metrics["audio_s"] = round(len(audio) / 16000, 2)
            task.command = text.strip()[:500]
            if not task.command:
                self._finish(task, Status.ERROR, "Non ho sentito nulla: riprova tenendo premuto il tasto")
                return
        self._set(task, Status.PLANNING, f"Comando: {task.command}")
        # nel registro solo il comando (max 500 caratteri), mai l'audio
        self.audit.write("task_start", task=task.id, command=task.command, source=task.source)
        intent = self.router.route(task.command)
        if intent.kind != "unknown":
            task.route = "regole locali"
        if intent.kind == "unknown" and self.jev is not None:
            t0 = time.monotonic()
            intent, note = await self.jev.route_async(task.command)
            task.metrics["router_ms"] = round((time.monotonic() - t0) * 1000)
            task.add_log(note)
            if intent.kind != "unknown":
                task.route = note
            self.audit.write("jev", task=task.id, note=note, intent=intent.kind, ms=task.metrics["router_ms"])
        task.intent = intent.kind
        if intent.kind == "stop":
            await self.stop(exclude=task.id)
            self._finish(task, Status.DONE, "Tutte le attività sono state fermate")
            return
        if intent.kind == "unknown" and self.agent is not None \
                and self.policy.decide("model.chat") is not Decision.DENY:
            answer = await self.agent.run(self, task)
            self._set(task, Status.RESPONDING)
            self._finish(task, Status.DONE, answer)
            return
        if intent.kind == "unknown":
            self._finish(task, Status.DONE,
                         "Non ho capito il comando. Esempi: «apri calcolatrice», «cerca meteo Roma», "
                         "«cerca e apri documentazione Python», «prepara una nota: ...».")
            return
        task.plan = plan_for(intent)
        self._set(task, Status.PLANNING, "Piano: " + "; ".join(a.description for a in task.plan))

        prev: ToolResult | None = None
        for action in task.plan:
            args = self._resolve_args(action.args, prev)
            prev = await self._execute(task, action.tool, args)
            if not prev.ok:
                self._finish(task, Status.ERROR, prev.summary)
                return
        self._set(task, Status.RESPONDING)
        self._finish(task, Status.DONE, prev.summary if prev else "Nulla da fare")

    def _resolve_args(self, args: dict[str, Any], prev: ToolResult | None) -> dict[str, Any]:
        out = dict(args)
        if out.get("url") == FIRST_RESULT_URL:
            results = (prev.data.get("results") if prev else None) or []
            if not results:
                raise RuntimeError("Nessun risultato da aprire")
            out["url"] = results[0]["url"]
        return out

    async def _execute(self, task: Task, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """Unico punto di esecuzione dei tool (regole e agente): permessi, conferme, audit."""
        if len(task.steps) >= self.config.limits.max_steps:
            raise StepLimitExceeded(f"Limite di {self.config.limits.max_steps} passi raggiunto")
        tool = self.tools.get(tool_name)
        if tool is None:
            return ToolResult(False, f"Strumento non disponibile: {tool_name}")
        decision = self.policy.decide(tool.capability)
        if decision is Decision.ALLOW and task.tainted and tool.capability.startswith("web."):
            # dopo aver letto dati privati, ogni uscita verso il web va confermata (anti-esfiltrazione)
            decision = Decision.CONFIRM
        if decision is Decision.DENY:
            self.audit.write("denied", task=task.id, tool=tool_name, args=args)
            return ToolResult(False, f"Permesso negato per «{tool.capability}» su {self.config.device_id}")
        if decision is Decision.CONFIRM:
            approved = await self._ask_confirmation(task, tool, args)
            if not approved:
                self.audit.write("rejected", task=task.id, tool=tool_name)
                return ToolResult(False, f"Azione «{tool_name}» non confermata: nulla è stato fatto",
                                  {"rejected": True})

        self._set(task, Status.EXECUTING, f"Eseguo {tool_name}")
        t0 = time.monotonic()
        try:
            res = await asyncio.wait_for(tool.run(args), timeout=self.config.limits.tool_timeout_s)
        except asyncio.TimeoutError:
            res = ToolResult(False, f"Timeout di {tool_name} ({self.config.limits.tool_timeout_s:.0f}s)")
        except Exception as e:  # noqa: BLE001
            res = ToolResult(False, f"{tool_name} fallito: {redact(str(e))[:300]}")
        ms = int((time.monotonic() - t0) * 1000)
        if res.ok and tool.private_data:
            task.tainted = True
        task.steps.append(StepRecord(tool_name, _loggable(args), res.ok, res.summary, res.verified, ms))
        task.add_log(("✔ " if res.ok else "✖ ") + res.summary)
        if res.untrusted_text:
            task.add_log("[contenuto esterno, non fidato] " + res.untrusted_text[:300].replace("\n", " "))
        self.audit.write("step", task=task.id, tool=tool_name, args=_loggable(args), ok=res.ok,
                         summary=res.summary, ms=ms)
        return res

    async def _ask_confirmation(self, task: Task, tool: Tool, args: dict[str, Any]) -> bool:
        h = action_hash(task.id, tool.name, args)
        task.pending = PendingConfirmation(h, tool.name, tool.preview(args))
        ev = asyncio.Event()
        box: list[bool] = []
        self._confirm[task.id] = (ev, box)
        self._set(task, Status.AWAITING_CONFIRMATION, f"Attendo conferma per {tool.name}")
        try:
            await asyncio.wait_for(ev.wait(), timeout=self.config.limits.confirm_timeout_s)
        except asyncio.TimeoutError:
            return False
        finally:
            task.pending = None
            self._confirm.pop(task.id, None)
        return bool(box and box[0])


def _loggable(args: dict[str, Any]) -> dict[str, Any]:
    return {k: (v[:200] + "…" if isinstance(v, str) and len(v) > 200 else v) for k, v in args.items()}
