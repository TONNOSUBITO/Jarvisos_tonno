"""Resoconto comprensibile di cosa è stato fatto e di cosa NON è stato fatto."""

from __future__ import annotations

from jarvis.core.state import Status, Task

_DONE_PHRASE = {
    "app.open": "ho aperto l'app {app}",
    "web.search": "ho cercato «{query}»",
    "web.open": "ho aperto {url}",
    "notes.save": "ho salvato la nota nella vault",
    "memory.remember": "ho memorizzato «{fact}»",
    "memory.list": "ho letto la memoria",
    "memory.forget": "ho dimenticato i ricordi con «{query}»",
    "vault.search": "ho cercato «{query}» nelle note",
    "files.list": "ho elencato i file",
    "files.read": "ho letto {path}",
    "files.write": "ho creato {path}",
    "files.move": "ho spostato {src} in {dst}",
    "files.delete": "ho spostato {path} nel cestino di Jarvis (recuperabile)",
}

# Azioni con effetti esterni che Jarvis in Fase 1 non ha affatto.
_NEVER = "non ho inviato, pubblicato, acquistato né eliminato definitivamente nulla"


def build_report(task: Task, status: Status) -> str:
    parts = []
    for s in task.steps:
        if s.ok:
            tmpl = _DONE_PHRASE.get(s.tool, s.tool)
            try:
                parts.append(tmpl.format(**s.args))
            except (KeyError, IndexError):
                parts.append(tmpl)
        else:
            parts.append(f"{s.tool} non riuscito ({s.summary})")
    saved = any(s.tool == "notes.save" and s.ok for s in task.steps)
    if any(a.tool == "notes.save" for a in task.plan) and not saved:
        parts.append("non ho salvato nulla su disco")
    parts.append(_NEVER)
    head = {Status.DONE: "Fatto", Status.STOPPED: "Fermato", Status.ERROR: "Interrotto"}.get(status, status.value)
    return f"{head}: " + ", ".join(parts) + "."
