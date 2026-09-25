"""Memoria durevole su richiesta esplicita e ricerca nella vault.

La memoria è un file Markdown leggibile e modificabile a mano:
`<vault>/memory/preferenze.md`, una riga per fatto. Salvare e dimenticare
richiedono conferma; nessun salvataggio automatico di conversazioni.
"""

from __future__ import annotations

import time
from typing import Any

from jarvis.memory.vault import Vault
from jarvis.tools.audit import contains_secret
from jarvis.tools.base import Tool, ToolResult

MEMORY_FILE = "memory/preferenze.md"
HEADER = "# Cose che Jarvis ricorda\n\nModificabile a mano. Una riga per fatto.\n\n"


class MemoryStore:
    def __init__(self, vault: Vault):
        self.vault = vault

    @property
    def path(self):
        return self.vault.root / MEMORY_FILE

    def facts(self) -> list[str]:
        if not self.path.exists():
            return []
        return [ln[2:].strip() for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.startswith("- ")]

    def _write(self, facts: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(HEADER + "".join(f"- {f}\n" for f in facts), encoding="utf-8")

    def add(self, fact: str) -> None:
        self._write(self.facts() + [f"{fact.strip()} _(aggiunto {time.strftime('%Y-%m-%d')})_"])

    def matching(self, query: str) -> list[str]:
        q = query.lower().strip()
        return [f for f in self.facts() if q and q in f.lower()]

    def remove(self, query: str) -> list[str]:
        gone = self.matching(query)
        self._write([f for f in self.facts() if f not in gone])
        return gone


class RememberTool(Tool):
    name = "memory.remember"
    capability = "memory.remember"
    description = "Memorizza un fatto o una preferenza durevole dell'utente (richiede conferma)."
    parameters = {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}

    def __init__(self, store: MemoryStore):
        self.store = store

    async def run(self, args: dict[str, Any]) -> ToolResult:
        fact = args["fact"].strip()[:500]
        if not fact:
            return ToolResult(False, "Niente da ricordare")
        if contains_secret(fact):
            return ToolResult(False, "Sembra un segreto (password/chiave): non lo memorizzo")
        self.store.add(fact)
        ok = any(fact in f for f in self.store.facts())
        return ToolResult(ok, f"Ricorderò: «{fact}»", {"file": MEMORY_FILE}, verified=ok)

    def preview(self, args: dict[str, Any]) -> str:
        return f"Aggiungere alla memoria ({MEMORY_FILE}):\n«{args.get('fact', '')}»"


class ListMemoryTool(Tool):
    name = "memory.list"
    capability = "memory.list"
    description = "Elenca i fatti memorizzati sull'utente."
    private_data = True

    def __init__(self, store: MemoryStore):
        self.store = store

    async def run(self, args: dict[str, Any]) -> ToolResult:
        facts = self.store.facts()
        if not facts:
            return ToolResult(True, "Non ricordo ancora nulla", {"facts": []}, verified=True)
        return ToolResult(True, "Ricordo: " + "; ".join(facts), {"facts": facts}, verified=True)


class ForgetTool(Tool):
    name = "memory.forget"
    capability = "memory.forget"
    description = "Dimentica i fatti memorizzati che contengono il testo indicato (richiede conferma)."
    parameters = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    def __init__(self, store: MemoryStore):
        self.store = store

    async def run(self, args: dict[str, Any]) -> ToolResult:
        gone = self.store.remove(args["query"])
        if not gone:
            return ToolResult(False, f"Nessun ricordo contiene «{args['query']}»")
        return ToolResult(True, f"Dimenticati {len(gone)} ricordi", {"removed": gone},
                          verified=not self.store.matching(args["query"]))

    def preview(self, args: dict[str, Any]) -> str:
        m = self.store.matching(args.get("query", ""))
        lines = "\n".join(f"- {f}" for f in m) or "(nessuno)"
        return f"Cancellare definitivamente dalla memoria {len(m)} ricordi:\n{lines}"


class SearchNotesTool(Tool):
    name = "vault.search"
    capability = "vault.search"
    description = "Cerca un testo nelle note Markdown della vault e restituisce file e frammenti."
    parameters = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    private_data = True

    def __init__(self, vault: Vault):
        self.vault = vault

    async def run(self, args: dict[str, Any]) -> ToolResult:
        hits = self.vault.search(args["query"])
        if not hits:
            return ToolResult(True, f"Nessuna nota contiene «{args['query']}»", {"hits": []}, verified=True)
        return ToolResult(True, f"Trovate {len(hits)} note con «{args['query']}»: "
                          + ", ".join(h["path"] for h in hits[:5]), {"hits": hits}, verified=True,
                          untrusted_text="\n".join(h["snippet"] for h in hits[:5]))
