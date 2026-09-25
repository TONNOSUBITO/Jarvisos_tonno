"""Permessi per capacità e per dispositivo, conferme puntuali.

Una conferma è legata all'hash esatto di (task, tool, argomenti): autorizza solo
l'azione mostrata in anteprima, una volta sola.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

from jarvis.config import DeviceConfig


class Decision(str, Enum):
    ALLOW = "auto"
    CONFIRM = "confirm"
    DENY = "deny"


def action_hash(task_id: str, tool: str, args: dict[str, Any]) -> str:
    payload = json.dumps([task_id, tool, args], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class PermissionPolicy:
    def __init__(self, config: DeviceConfig):
        self.config = config
        self._used: set[str] = set()

    def decide(self, capability: str) -> Decision:
        return Decision(self.config.permission(capability))

    def consume_confirmation(self, expected_hash: str, given_hash: str) -> bool:
        """True solo se l'hash corrisponde e non è già stato usato."""
        if given_hash != expected_hash or given_hash in self._used:
            return False
        self._used.add(given_hash)
        return True
