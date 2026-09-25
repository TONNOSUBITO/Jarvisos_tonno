import httpx
import pytest

from jarvis.memory.vault import Vault, VaultError
from jarvis.providers.base import (BudgetExceeded, BudgetMeter, GuardedProvider, MockProvider,
                                   OpenAICompatibleProvider, PaidRouteDisabled)


def test_vault_crud_and_safety(tmp_path):
    v = Vault(tmp_path / "v")
    rel = v.write_note("inbox", "Spesa è ok", "latte")
    rel2 = v.write_note("inbox", "Spesa è ok", "pane")
    assert rel != rel2 and rel.startswith("inbox/")
    assert "latte" in v.read(rel)
    v.update(rel, "# nuovo")
    assert v.read(rel) == "# nuovo"
    v.delete(rel)
    assert v.list_notes() == [rel2]
    with pytest.raises(VaultError):
        v.read("../fuori.md")
    with pytest.raises(VaultError):
        v.write_note("segreti", "x", "y")
    with pytest.raises(VaultError):
        v.write_note("inbox", "chiave", "api_key=abc123")


async def test_budget_and_paid_routes():
    paid = MockProvider(is_paid=True, cost_eur=0.01)
    with pytest.raises(PaidRouteDisabled):
        await GuardedProvider(paid, BudgetMeter(1), allow_paid=False).complete([])
    g = GuardedProvider(paid, BudgetMeter(0.015), allow_paid=True, estimated_cost_eur=0.01)
    await g.complete([])
    with pytest.raises(BudgetExceeded):
        await g.complete([])
    assert len(paid.calls) == 1


async def test_openai_compatible_provider_with_mock_transport():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ciao"}}]})

    p = OpenAICompatibleProvider("http://127.0.0.1:20128/v1", "auto", api_key="k",
                                 transport=httpx.MockTransport(handler))
    r = await p.complete([{"role": "user", "content": "hi"}])
    assert r.text == "ciao"
    assert seen["url"].endswith("/v1/chat/completions") and seen["auth"] == "Bearer k"


def test_multiple_providers_from_config(tmp_path, monkeypatch):
    from jarvis.config import load_config
    from jarvis.providers.base import build_provider

    f = tmp_path / "d.toml"
    f.write_text("""[model]
enabled = true
[[model.providers]]
name = "groq"
base_url = "https://api.groq.com/openai/v1"
model = "m1"
api_key_env = "GROQ_API_KEY"
[[model.providers]]
name = "gemini"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
model = "m2"
api_key_env = "GEMINI_API_KEY"
paid = true
""")
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = load_config(f)
    fb = build_provider(cfg.model, BudgetMeter(0))
    assert [p.name for p in fb.providers] == ["groq", "gemini"]
    assert fb.providers[0].api_key == "k1" and fb.providers[1].api_key == ""
    assert fb.providers[1].is_paid and not fb.allow_paid
    assert fb.providers[1].base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
