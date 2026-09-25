"""Skill personali: procedure in Markdown che l'utente insegna a Jarvis.

Formato compatibile con lo standard agentskills.io (usato anche da Hermes agent):
`<vault>/skills/<nome>/SKILL.md` con frontmatter `name` e `description`.
Si creano solo a mano o con conferma sull'anteprima completa; nessuna importazione di skill di terzi.
Le azioni che una skill descrive passano comunque da permessi e conferme.
"""

from __future__ import annotations

import re
from typing import Any

from jarvis.memory.vault import Vault
from jarvis.tools.audit import contains_secret
from jarvis.tools.base import Tool, ToolResult

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")


def skill_name(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")[:60]


class SkillStore:
    def __init__(self, vault: Vault):
        self.root = vault.root / "skills"

    def path(self, name: str):
        return self.root / name / "SKILL.md"

    def names(self) -> list[tuple[str, str]]:
        """(nome, descrizione) di ogni skill."""
        out = []
        for f in sorted(self.root.glob("*/SKILL.md")) if self.root.exists() else []:
            m = re.search(r"^description:\s*(.+)$", f.read_text(encoding="utf-8"), re.M)
            out.append((f.parent.name, m.group(1).strip() if m else ""))
        return out

    def read(self, name: str) -> str | None:
        p = self.path(skill_name(name))
        return p.read_text(encoding="utf-8") if p.exists() else None

    @staticmethod
    def render(name: str, text: str) -> str:
        desc = re.split(r"(?<=[.!?])\s|\n", text.strip(), maxsplit=1)[0][:150]
        return f"---\nname: {name}\ndescription: {desc}\n---\n\n{text.strip()}\n"

    def save(self, name: str, text: str) -> None:
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.render(name, text), encoding="utf-8")


class ListSkillsTool(Tool):
    name = "skills.list"
    capability = "skills.list"
    description = "Elenca le skill (procedure insegnate dall'utente) con la loro descrizione."

    def __init__(self, store: SkillStore):
        self.store = store

    async def run(self, args: dict[str, Any]) -> ToolResult:
        items = self.store.names()
        if not items:
            return ToolResult(True, "Nessuna skill salvata", {"skills": []}, verified=True)
        return ToolResult(True, "Skill: " + "; ".join(f"{n} — {d}" for n, d in items),
                          {"skills": [{"name": n, "description": d} for n, d in items]}, verified=True)


class ReadSkillTool(Tool):
    name = "skills.read"
    capability = "skills.read"
    description = "Legge una skill per seguirne il procedimento."
    parameters = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}

    def __init__(self, store: SkillStore):
        self.store = store

    async def run(self, args: dict[str, Any]) -> ToolResult:
        text = self.store.read(args["name"])
        if text is None:
            return ToolResult(False, f"Nessuna skill «{args['name']}»")
        return ToolResult(True, f"Skill «{skill_name(args['name'])}» letta", {"skill": text[:4000]}, verified=True)


class SaveSkillTool(Tool):
    name = "skills.save"
    capability = "skills.save"
    description = ("Salva come skill un procedimento che l'utente vuole riutilizzare (richiede conferma). "
                   "name: breve, minuscolo; text: istruzioni passo passo.")
    parameters = {"type": "object", "properties": {"name": {"type": "string"}, "text": {"type": "string"}},
                  "required": ["name", "text"]}

    def __init__(self, store: SkillStore):
        self.store = store

    async def run(self, args: dict[str, Any]) -> ToolResult:
        name, text = skill_name(args["name"]), args["text"].strip()[:4000]
        if not _NAME.match(name) or not text:
            return ToolResult(False, "Serve un nome e un testo per la skill")
        if contains_secret(text):
            return ToolResult(False, "Sembra contenere un segreto (password/chiave): non la salvo")
        self.store.save(name, text)
        ok = self.store.read(name) == SkillStore.render(name, text)
        return ToolResult(ok, f"Skill «{name}» salvata", {"file": f"skills/{name}/SKILL.md"}, verified=ok)

    def preview(self, args: dict[str, Any]) -> str:
        name = skill_name(args.get("name", ""))
        warn = "ATTENZIONE: sostituisce la skill esistente.\n" if self.store.read(name) is not None else ""
        return f"{warn}Salvare skills/{name}/SKILL.md:\n\n{SkillStore.render(name, args.get('text', ''))}"
