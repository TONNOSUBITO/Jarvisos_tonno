"""File in UNA cartella di lavoro autorizzata (`[device] work_dir`).

- elenca / leggi: automatici (se abilitati), il contenuto è dato non fidato;
- crea / sposta / elimina: conferma con anteprima. «Elimina» sposta nel cestino
  `.cestino-jarvis/` dentro la stessa cartella: recuperabile, mai cancellazione definitiva.
Nessuna sovrascrittura. File che sembrano segreti (.env, chiavi) non vengono letti.
"""

from __future__ import annotations

import fnmatch
import shutil
import time
from pathlib import Path
from typing import Any

from jarvis.tools.base import Tool, ToolResult

TRASH = ".cestino-jarvis"
SECRET_NAMES = [".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.kdbx", "*password*",
                "*credential*", "*secret*", "*token*", "cookies*", "*.sqlite"]
MAX_READ = 20_000


class FileAccessError(Exception):
    pass


class WorkDir:
    def __init__(self, root: Path | None):
        self.root = Path(root).resolve() if root else None

    def resolve(self, rel: str) -> Path:
        if self.root is None:
            raise FileAccessError("Nessuna cartella di lavoro autorizzata (imposta [device] work_dir)")
        p = (self.root / (rel or ".")).resolve()
        if p != self.root and self.root not in p.parents:
            raise FileAccessError(f"Percorso fuori dalla cartella autorizzata: {rel}")
        if TRASH in p.relative_to(self.root).parts[:1]:
            raise FileAccessError("Il cestino di Jarvis non è accessibile dai comandi")
        return p

    def rel(self, p: Path) -> str:
        return str(p.relative_to(self.root)).replace("\\", "/") or "."


def _is_secret_name(name: str) -> bool:
    return any(fnmatch.fnmatch(name.lower(), pat) for pat in SECRET_NAMES)


class _FileTool(Tool):
    def __init__(self, wd: WorkDir):
        self.wd = wd

    async def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            return self._run(args)
        except (FileAccessError, OSError) as e:
            return ToolResult(False, str(e))

    def _run(self, args: dict[str, Any]) -> ToolResult:  # pragma: no cover
        raise NotImplementedError


class ListFilesTool(_FileTool):
    name = "files.list"
    capability = "files.list"
    description = "Elenca file e cartelle nella cartella di lavoro autorizzata."
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}}
    private_data = True

    def _run(self, args):
        d = self.wd.resolve(args.get("path", ""))
        if not d.is_dir():
            raise FileAccessError(f"Non è una cartella: {args.get('path')}")
        items = sorted((p for p in d.iterdir() if p.name != TRASH), key=lambda p: (p.is_file(), p.name.lower()))
        entries = [self.wd.rel(p) + ("/" if p.is_dir() else "") for p in items[:200]]
        return ToolResult(True, f"{len(entries)} elementi in «{self.wd.rel(d)}»", {"entries": entries}, verified=True)


class ReadFileTool(_FileTool):
    name = "files.read"
    capability = "files.read"
    description = "Legge un file di testo nella cartella di lavoro autorizzata (contenuto = dato non fidato)."
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    private_data = True

    def _run(self, args):
        p = self.wd.resolve(args["path"])
        if _is_secret_name(p.name):
            raise FileAccessError(f"«{p.name}» sembra contenere segreti: non lo leggo")
        if not p.is_file():
            raise FileAccessError(f"File inesistente: {args['path']}")
        raw = p.read_bytes()[: MAX_READ * 4]
        if b"\x00" in raw[:4096]:
            raise FileAccessError("File binario: non leggibile come testo")
        text = raw.decode("utf-8", errors="replace")[:MAX_READ]
        return ToolResult(True, f"Letto «{self.wd.rel(p)}» ({len(text)} caratteri)", {"path": self.wd.rel(p)},
                          verified=True, untrusted_text=text)


class WriteFileTool(_FileTool):
    name = "files.write"
    capability = "files.write"
    description = "Crea un NUOVO file di testo nella cartella di lavoro (richiede conferma, mai sovrascrive)."
    parameters = {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                  "required": ["path", "content"]}

    def _run(self, args):
        p = self.wd.resolve(args["path"])
        if p.exists():
            raise FileAccessError(f"Esiste già: {args['path']} (non sovrascrivo)")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("x", encoding="utf-8") as f:
            f.write(args["content"])
        return ToolResult(p.is_file(), f"Creato «{self.wd.rel(p)}»", {"path": self.wd.rel(p)}, verified=p.is_file())

    def preview(self, args):
        c = args.get("content", "")
        return f"Creare il file «{args.get('path')}» ({len(c)} caratteri):\n{c[:500]}"


class MoveFileTool(_FileTool):
    name = "files.move"
    capability = "files.move"
    description = "Sposta o rinomina un file dentro la cartella di lavoro (richiede conferma)."
    parameters = {"type": "object", "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
                  "required": ["src", "dst"]}

    def _run(self, args):
        src, dst = self.wd.resolve(args["src"]), self.wd.resolve(args["dst"])
        if not src.exists():
            raise FileAccessError(f"Inesistente: {args['src']}")
        if dst.is_dir():
            dst = dst / src.name
        if dst.exists():
            raise FileAccessError(f"Destinazione già esistente: {self.wd.rel(dst)}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        ok = dst.exists() and not src.exists()
        return ToolResult(ok, f"Spostato «{args['src']}» → «{self.wd.rel(dst)}»", {"dst": self.wd.rel(dst)}, verified=ok)

    def preview(self, args):
        return f"Spostare «{args.get('src')}» in «{args.get('dst')}» (dentro {self.wd.root})"


class DeleteFileTool(_FileTool):
    name = "files.delete"
    capability = "files.delete"
    description = "Sposta un file o una cartella nel cestino di Jarvis (recuperabile; richiede conferma)."
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}

    def _run(self, args):
        p = self.wd.resolve(args["path"])
        if p == self.wd.root:
            raise FileAccessError("Non posso eliminare la cartella di lavoro stessa")
        if not p.exists():
            raise FileAccessError(f"Inesistente: {args['path']}")
        dest = self.wd.root / TRASH / f"{time.strftime('%Y%m%d-%H%M%S')}-{p.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))
        ok = dest.exists() and not p.exists()
        return ToolResult(ok, f"«{args['path']}» spostato nel cestino ({TRASH}/{dest.name})", {"trash": dest.name}, verified=ok)

    def preview(self, args):
        try:
            p = self.wd.resolve(args.get("path", ""))
            n = sum(1 for _ in p.rglob("*")) if p.is_dir() else 1
        except (FileAccessError, OSError):
            n = 0
        return f"Spostare nel cestino «{args.get('path')}» ({n} file). Recuperabile da {TRASH}/."
