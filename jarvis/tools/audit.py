"""Audit locale JSONL con segreti oscurati. Nessun invio in rete."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"),                       # chiavi stile OpenAI/Anthropic
    re.compile(r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}"),  # token GitHub
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                            # AWS access key
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)\b(password|passwd|pwd|token|api[_-]?key|secret|cookie)\s*[=:]\s*\S+"),
    re.compile(r"\b[A-Fa-f0-9]{40,}\b"),                            # hex lunghi
]

REDACTED = "[OSCURATO]"


def redact(text: str) -> str:
    for p in _PATTERNS:
        text = p.sub(REDACTED, text)
    return text


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _PATTERNS)


def _redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: _redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact_obj(v) for v in obj]
    return obj


class AuditLog:
    def __init__(self, path: Path, device_id: str):
        self.path = path
        self.device_id = device_id
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        rec = {"ts": time.time(), "device": self.device_id, "event": event, **_redact_obj(fields)}
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
