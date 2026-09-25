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
    """Risposte scriptate: stringhe (testo) o ModelResponse (anche con tool_calls)."""

    name = "mock"

    def __init__(self, reply: str | list = "ok", cost_eur: float = 0.0, is_paid: bool = False,
                 fail: bool = False):
        self.script = list(reply) if isinstance(reply, list) else None
        self.reply = reply
        self.cost_eur = cost_eur
        self.is_paid = is_paid
        self.fail = fail
        self.calls: list[list[dict[str, Any]]] = []

    async def complete(self, messages, tools=None, timeout_s=30.0) -> ModelResponse:
        self.calls.append([dict(m) for m in messages])
        if self.fail:
            raise httpx.ConnectError("mock non raggiungibile")
        item = (self.script.pop(0) if self.script else "fine") if self.script is not None else self.reply
        if isinstance(item, ModelResponse):
            item.cost_eur = item.cost_eur or self.cost_eur
            return item
        return ModelResponse(item, cost_eur=self.cost_eur, provider=self.name)


class OpenAICompatibleProvider(ModelProvider):
    """Client minimo /chat/completions. Non verificato su server reale (Fase 3)."""

    def __init__(self, base_url: str, model: str, api_key: str = "", is_paid: bool = False,
                 transport: httpx.AsyncBaseTransport | None = None, price_in: float = 0.0,
                 price_out: float = 0.0, label: str = ""):
        self.name = label or f"openai-compat:{base_url}"
        self.price_in = price_in
        self.price_out = price_out
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
        usage = data.get("usage") or {}
        cost = (usage.get("prompt_tokens", 0) * self.price_in
                + usage.get("completion_tokens", 0) * self.price_out) / 1_000_000
        return ModelResponse(msg.get("content") or "", msg.get("tool_calls") or [], cost, self.name)


class GuardedProvider:
    """Applica al provider: rotte a pagamento disattivate e soglia di spesa."""

    def __init__(self, provider: ModelProvider, budget: BudgetMeter, allow_paid: bool):
        self.provider = provider
        self.budget = budget
        self.allow_paid = allow_paid

    async def complete(self, messages, tools=None, timeout_s=30.0) -> ModelResponse:
        if self.provider.is_paid and not self.allow_paid:
            raise PaidRouteDisabled(f"Rotta a pagamento '{self.provider.name}' disattivata")
        if self.provider.is_paid and self.budget.spent_eur >= self.budget.limit_eur:
            raise BudgetExceeded(f"Budget esaurito: spesi {self.budget.spent_eur:.4f}€ su un limite di "
                                 f"{self.budget.limit_eur:.2f}€")
        resp = await self.provider.complete(messages, tools, timeout_s)
        self.budget.charge(resp.cost_eur)
        return resp


class FallbackProvider(ModelProvider):
    """Prova i provider in ordine; salta quelli a pagamento se non ammessi.
    BudgetExceeded interrompe tutto (nessun tentativo su rotte più costose)."""

    name = "fallback"

    def __init__(self, providers: list[ModelProvider], budget: BudgetMeter, allow_paid: bool):
        self.providers = providers
        self.budget = budget
        self.allow_paid = allow_paid
        self.last_errors: list[str] = []

    async def complete(self, messages, tools=None, timeout_s=30.0) -> ModelResponse:
        self.last_errors = []
        for p in self.providers:
            try:
                return await GuardedProvider(p, self.budget, self.allow_paid).complete(messages, tools, timeout_s)
            except BudgetExceeded:
                raise
            except PaidRouteDisabled as e:
                self.last_errors.append(str(e))
            except (httpx.HTTPError, KeyError, ValueError) as e:
                self.last_errors.append(f"{p.name}: {type(e).__name__}")
        raise RuntimeError("Nessun modello disponibile: " + "; ".join(self.last_errors or ["nessun provider configurato"]))


def build_provider(model_cfg, budget: BudgetMeter) -> FallbackProvider | None:
    import os

    if not model_cfg.enabled:
        return None
    # un provider che richiede una chiave assente dal .env viene saltato (niente chiamate a vuoto)
    ps = [OpenAICompatibleProvider(p.base_url, p.model, os.environ.get(p.api_key_env, "") if p.api_key_env else "",
                                   is_paid=p.paid, price_in=p.price_in_per_mtok_eur, price_out=p.price_out_per_mtok_eur,
                                   label=p.name)
          for p in model_cfg.providers if not p.api_key_env or os.environ.get(p.api_key_env)]
    return FallbackProvider(ps, budget, model_cfg.allow_paid) if ps else None
