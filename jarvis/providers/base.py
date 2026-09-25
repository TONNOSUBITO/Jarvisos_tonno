"""Astrazione dei modelli linguistici e contatore di spesa.

Fase 1: solo `MockProvider` è usato nei test. `OpenAICompatibleProvider` copre
OmniRoute (endpoint OpenAI-compatibile, porta di default 20128, path /v1) e
Ollama (/v1 compatibile), ma NON è stato provato contro un server reale.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx


class BudgetExceeded(Exception):
    pass


class PaidRouteDisabled(Exception):
    pass


@dataclass
class ModelResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    cost_eur: float = 0.0
    provider: str = ""


class BudgetMeter:
    """Soglia di spesa per processo. limit 0 = nessuna spesa ammessa."""

    def __init__(self, limit_eur: float):
        self.limit_eur = limit_eur
        self.spent_eur = 0.0

    def check(self, estimated_eur: float) -> None:
        if estimated_eur > 0 and self.spent_eur + estimated_eur > self.limit_eur:
            raise BudgetExceeded(
                f"Spesa stimata {estimated_eur:.4f}€ oltre il limite "
                f"({self.spent_eur:.4f}/{self.limit_eur:.2f}€)")

    def charge(self, eur: float) -> None:
        self.spent_eur += max(0.0, eur)


class ModelProvider(ABC):
    name: str = "base"
    is_paid: bool = False

    @abstractmethod
    async def complete(self, messages: list[dict[str, str]],
                       tools: list[dict[str, Any]] | None = None,
                       timeout_s: float = 30.0) -> ModelResponse: ...


class MockProvider(ModelProvider):
    name = "mock"

    def __init__(self, reply: str = "ok", cost_eur: float = 0.0, is_paid: bool = False):
        self.reply = reply
        self.cost_eur = cost_eur
        self.is_paid = is_paid
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages, tools=None, timeout_s=30.0) -> ModelResponse:
        self.calls.append(messages)
        return ModelResponse(self.reply, cost_eur=self.cost_eur, provider=self.name)


class OpenAICompatibleProvider(ModelProvider):
    """Client minimo /chat/completions. Non verificato su server reale (Fase 3)."""

    def __init__(self, base_url: str, model: str, api_key: str = "", is_paid: bool = False,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.name = f"openai-compat:{base_url}"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.is_paid = is_paid
        self._transport = transport

    async def complete(self, messages, tools=None, timeout_s=30.0) -> ModelResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = tools
        async with httpx.AsyncClient(timeout=timeout_s, transport=self._transport) as c:
            r = await c.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        msg = data["choices"][0]["message"]
        return ModelResponse(msg.get("content") or "", msg.get("tool_calls") or [], provider=self.name)


class GuardedProvider:
    """Applica al provider: rotte a pagamento disattivate e soglia di spesa."""

    def __init__(self, provider: ModelProvider, budget: BudgetMeter, allow_paid: bool,
                 estimated_cost_eur: float = 0.0):
        self.provider = provider
        self.budget = budget
        self.allow_paid = allow_paid
        self.estimated_cost_eur = estimated_cost_eur

    async def complete(self, messages, tools=None, timeout_s=30.0) -> ModelResponse:
        if self.provider.is_paid and not self.allow_paid:
            raise PaidRouteDisabled(f"Rotta a pagamento '{self.provider.name}' disattivata")
        self.budget.check(self.estimated_cost_eur)
        resp = await self.provider.complete(messages, tools, timeout_s)
        self.budget.charge(resp.cost_eur)
        return resp
