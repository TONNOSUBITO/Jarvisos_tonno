"""Vault Markdown compatibile Obsidian, leggibile senza Jarvis.

Scrive solo su richiesta esplicita (tool `notes.save`, che richiede conferma).
Rifiuta contenuti che sembrano segreti. Nessuna sovrascrittura silenziosa.
"""

from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

from jarvis.tools.audit import contains_secret

FOLDERS = ("inbox", "daily", "projects", "reports", "skills", "memory")


class VaultError(Exception):
    pass


def slugify(title: str, max_len: int = 60) -> str:
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return (t[:max_len].rstrip("-")) or "nota"


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)

    def init(self) -> None:
        for f in FOLDERS:
            (self.root / f).mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        root = self.root.resolve()
        if root != p and root not in p.parents:
            raise VaultError(f"Percorso fuori dalla vault: {rel}")
        if p.suffix != ".md":
            raise VaultError("Solo file .md")
        return p

    def write_note(self, folder: str, title: str, body: str) -> str:
        if folder not in FOLDERS:
            raise VaultError(f"Cartella non ammessa: {folder}")
        if contains_secret(title) or contains_secret(body):
            raise VaultError("Il contenuto sembra contenere un segreto: non salvato")
        self.init()
        base = f"{time.strftime('%Y-%m-%d')}-{slugify(title)}"
        rel = f"{folder}/{base}.md"
        n = 2
        while (self.root / rel).exists():
            rel = f"{folder}/{base}-{n}.md"
            n += 1
        path = self._resolve(rel)
        content = f"---\ncreated: {time.strftime('%Y-%m-%dT%H:%M:%S')}\nsource: jarvis\n---\n\n# {title}\n\n{body.strip()}\n"
        with path.open("x", encoding="utf-8") as f:
            f.write(content)
        return rel

    def list_notes(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace("\\", "/") for p in self.root.rglob("*.md"))

    def search(self, query: str, limit: int = 20) -> list[dict[str, str]]:
        q = query.lower().strip()
        hits = []
        for rel in self.list_notes():
            text = (self.root / rel).read_text(encoding="utf-8", errors="replace")
            i = text.lower().find(q) if q else -1
            if i >= 0:
                hits.append({"path": rel, "snippet": text[max(0, i - 80): i + 120].replace("\n", " ")})
                if len(hits) >= limit:
                    break
        return hits

    def read(self, rel: str) -> str:
        return self._resolve(rel).read_text(encoding="utf-8")

    def update(self, rel: str, content: str) -> None:
        if contains_secret(content):
            raise VaultError("Il contenuto sembra contenere un segreto: non salvato")
        p = self._resolve(rel)
        if not p.exists():
            raise VaultError(f"Nota inesistente: {rel}")
        p.write_text(content, encoding="utf-8")

    def delete(self, rel: str) -> None:
        p = self._resolve(rel)
        if not p.exists():
            raise VaultError(f"Nota inesistente: {rel}")
        p.unlink()
