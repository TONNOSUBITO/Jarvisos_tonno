"""Caricamento delle skill `SKILL.md`.

Una skill è un'istruzione versionata e revisionata, NON un'autorizzazione:
non può abilitare capacità; ogni azione passa comunque da PermissionPolicy.
Vengono caricate solo skill con `reviewed: true` nel frontmatter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    version: str
    reviewed: bool
    body: str
    uses: list[str] = field(default_factory=list)  # capacità citate: solo documentazione
    path: str = ""


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError("Frontmatter mancante")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("Frontmatter non chiuso")
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[end + 4:].lstrip("\n")


def parse_skill(path: Path) -> Skill:
    meta, body = _frontmatter(path.read_text(encoding="utf-8"))
    for key in ("name", "description", "version"):
        if not meta.get(key):
            raise ValueError(f"{path}: campo '{key}' mancante")
    uses = [u.strip() for u in meta.get("uses", "").strip("[]").split(",") if u.strip()]
    return Skill(meta["name"], meta["description"], meta["version"],
                 meta.get("reviewed", "false").lower() == "true", body, uses, str(path))


def load_skills(root: Path) -> list[Skill]:
    skills = []
    for p in sorted(Path(root).glob("*/SKILL.md")):
        s = parse_skill(p)
        if s.reviewed:
            skills.append(s)
    return skills
