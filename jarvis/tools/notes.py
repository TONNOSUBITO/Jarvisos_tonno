"""Note/report: salvataggio in vault, sempre con conferma e anteprima."""

from __future__ import annotations

from typing import Any

from jarvis.memory.vault import Vault, VaultError
from jarvis.tools.base import Tool, ToolResult


class SaveNoteTool(Tool):
    name = "notes.save"
    capability = "notes.save"
    description = "Salva una nota Markdown nella vault (richiede conferma dell'utente)."
    parameters = {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "folder": {"type": "string", "enum": ["inbox", "daily", "projects", "reports"]}}, "required": ["title", "body"]}

    def __init__(self, vault: Vault):
        self.vault = vault

    async def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            rel = self.vault.write_note(args.get("folder", "inbox"), args["title"], args["body"])
        except VaultError as e:
            return ToolResult(False, str(e))
        ok = rel in self.vault.list_notes()
        return ToolResult(ok, f"Nota salvata in vault: {rel}", {"path": rel}, verified=ok)

    def preview(self, args: dict[str, Any]) -> str:
        body = args.get("body", "")
        return (f"Salvare nella vault, cartella «{args.get('folder', 'inbox')}», titolo «{args.get('title')}».\n"
                f"Contenuto ({len(body)} caratteri):\n{body[:500]}")
