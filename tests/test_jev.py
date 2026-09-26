import json

import httpx
import pytest

from jarvis.app import build_orchestrator
from jarvis.config import RouterConfig
from jarvis.core.state import Status
from jarvis.providers.base import BudgetMeter
from jarvis.routing.jev import JevRouter, build_jev


def answer(kind, conf, app=None, tokens=300):
    a = {"intento": {"type": "choice", "choice": kind, "confidence": conf}}
    if app:
        a["app"] = {"type": "choice", "choice": app, "confidence": 0.9}
    return {"model": "jev-1.13.0", "answers": a, "usage": {"input_tokens": tokens, "output_tokens": 20}}


def jev(body, apps=("calcolatrice",), budget=1.0, status=200, seen=None):
    def handler(req):
        if seen is not None:
            seen.append(req)
        return httpx.Response(status, json=body)
    return JevRouter(RouterConfig(engine="rules+jev"), list(apps), BudgetMeter(budget), "k",
                     transport=httpx.MockTransport(handler))


async def test_request_shape_and_cost():
    seen = []
    r = jev(answer("open_app", 0.9, "calcolatrice"), seen=seen)
    intent, note = await r.route_async("Mi fai partire la calcolatrice?")
    assert (intent.kind, intent.slots) == ("open_app", {"app": "calcolatrice"}) and "0.90" in note
    req = seen[0]
    body = json.loads(req.content)
    assert str(req.url) == "https://api.typesafe.ai/v1/systemone"
    assert req.headers["authorization"] == "Bearer k" and body["model"] == "jev-latest"
    assert body["questions"]["app"]["criteria"] == {"calcolatrice": None}
    assert r.budget.spent_eur == pytest.approx(300 * 0.042 / 1e6)


@pytest.mark.parametrize("body,status,kind", [
    (answer("web_search", 0.5), 200, "unknown"),        # confidenza bassa
    (answer("domanda", 0.95), 200, "unknown"),          # domanda generale → agente
    ({}, 429, "unknown"),
    ({}, 529, "unknown"),
    ([1, 2], 200, "unknown"),                           # risposta malformata
    (answer("open_app", 0.9, "rm"), 200, "unknown"),    # app fuori dall'elenco approvato
])
async def test_fallbacks(body, status, kind):
    intent, _ = await jev(body, status=status).route_async("boh")
    assert intent.kind == kind


async def test_search_slot_and_no_budget():
    intent, _ = await jev(answer("web_search", 0.9)).route_async("cercami il meteo di domani a Roma")
    assert intent.slots == {"query": "il meteo di domani a Roma"}
    seen = []
    intent, note = await jev(answer("stop", 0.99), budget=0, seen=seen).route_async("x")
    assert intent.kind == "unknown" and not seen and "budget" in note


def test_build_requires_optin_key_budget(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    on = RouterConfig(engine="rules+jev")
    assert build_jev(on, [], BudgetMeter(1)) is None
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    assert build_jev(RouterConfig(), [], BudgetMeter(1)) is None
    assert build_jev(on, [], BudgetMeter(0)) is None
    assert build_jev(on, [], BudgetMeter(1)) is not None


async def test_orchestrator_uses_jev_only_after_rules(cfg, apps):
    seen = []
    o = build_orchestrator(cfg, apps)
    o.jev = jev(answer("open_app", 0.9, "calcolatrice"), seen=seen)
    t = await o.wait(o.submit("apri calcolatrice").id)
    assert t.status is Status.DONE and not seen
    t = await o.wait(o.submit("mi serve fare due conti").id)
    assert t.status is Status.DONE and len(seen) == 1 and apps.launched and "router_ms" in t.metrics
    await o.stop()


async def test_route_shown_for_rules_and_jev(cfg, apps):
    o = build_orchestrator(cfg, apps)
    t = await o.wait(o.submit("apri calcolatrice").id)
    assert t.route == "regole locali"
    o.jev = jev(answer("open_app", 0.9, "calcolatrice"))
    t = await o.wait(o.submit("mi serve fare due conti").id)
    assert t.route.startswith("Jev: open_app")
    await o.stop()
