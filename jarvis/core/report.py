"""Resoconto comprensibile di cosa è stato fatto e di cosa NON è stato fatto."""

from __future__ import annotations

from jarvis.core.state import Status, Task

_DONE_PHRASE = {
    "app.open": "ho aperto l'app {app}",
    "web.search": "ho cercato «{query}»",
    "web.open": "ho aperto {url}",
    "notes.draft": "ho preparato una bozza",
    "notes.save": "ho salvato la nota nella vault",
}

# Azioni con effetti esterni che Jarvis in Fase 1 non ha affatto.
_NEVER = "non ho inviato, pubblicato, acquistato né eliminato nulla"


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
