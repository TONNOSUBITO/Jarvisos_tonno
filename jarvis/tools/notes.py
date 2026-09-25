"""Note/report: bozza (nessuna scrittura) e salvataggio in vault (con conferma)."""

from __future__ import annotations

from typing import Any

from jarvis.memory.vault import Vault, VaultError
from jarvis.tools.base import Tool, ToolResult


class DraftNoteTool(Tool):
    name = "notes.draft"
    capability = "notes.draft"

    async def run(self, args: dict[str, Any]) -> ToolResult:
        text = args["text"].strip()
        title = args.get("title") or text[:60]
        body = text
        if args.get("sources"):
            body += "\n\n## Fonti\n" + "\n".join(f"- {s}" for s in args["sources"])
        return ToolResult(True, f"Bozza pronta: «{title}» ({len(body)} caratteri), non salvata",
                          {"title": title, "body": body}, verified=True)

    def preview(self, args: dict[str, Any]) -> str:
        return f"Preparare bozza: {args.get('text', '')[:80]}"


class SaveNoteTool(Tool):
    name = "notes.save"
    capability = "notes.save"

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
