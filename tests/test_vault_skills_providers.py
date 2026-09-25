import httpx
import pytest

from jarvis.memory.vault import Vault, VaultError
from jarvis.providers.base import (BudgetExceeded, BudgetMeter, GuardedProvider, MockProvider,
                                   OpenAICompatibleProvider, PaidRouteDisabled)
from jarvis.skills.loader import load_skills, parse_skill


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


def test_skills_loader(tmp_path):
    skills = load_skills("skills")
    assert [s.name for s in skills] == ["demo-ricerca-nota"]
    assert "notes.save" in skills[0].uses
    d = tmp_path / "x"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: x\ndescription: d\nversion: 1\n---\ncorpo")
    assert load_skills(tmp_path) == []  # non revisionata → ignorata
    assert parse_skill(d / "SKILL.md").body == "corpo"


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
