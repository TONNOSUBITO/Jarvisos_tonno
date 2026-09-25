import pytest

from jarvis.core.state import Status
from jarvis.providers.base import MockProvider, ModelResponse
from jarvis.routing.router import RuleRouter
from test_memory_files import confirm_and_wait


@pytest.mark.parametrize("text,kind,slots", [
    ("crea la skill Email Cliente: rispondi cortese", "skill_save",
     {"name": "Email Cliente", "text": "rispondi cortese"}),
    ("elenca le skill", "skill_list", {}),
    ("quali skill hai?", "skill_list", {}),
    ("mostra la skill email-cliente", "skill_read", {"name": "email-cliente"}),
])
def test_skill_intents(text, kind, slots):
    i = RuleRouter().route(text)
    assert (i.kind, i.slots) == (kind, slots)


async def test_skill_cycle(orch, cfg):
    t, preview = await confirm_and_wait(orch, "crea la skill Email Cliente: Rispondi cortese. Firma Paolo")
    assert t.status is Status.DONE and "skills/email-cliente/SKILL.md" in preview
    f = cfg.vault_dir / "skills" / "email-cliente" / "SKILL.md"
    assert f.read_text(encoding="utf-8").startswith("---\nname: email-cliente\ndescription: Rispondi cortese.\n---")
    t = await orch.wait(orch.submit("elenca le skill").id)
    assert "email-cliente — Rispondi cortese." in t.result
    t = await orch.wait(orch.submit("mostra la skill email cliente").id)
    assert t.status is Status.DONE
    _, preview = await confirm_and_wait(orch, "crea la skill email-cliente: altro", approve=False)
    assert "sostituisce" in preview and "Firma Paolo" in f.read_text(encoding="utf-8")


async def test_skill_rejects_secret_and_missing(orch, cfg):
    t, _ = await confirm_and_wait(orch, "crea la skill login: la password=segreta123")
    assert t.status is Status.ERROR and not (cfg.vault_dir / "skills" / "login").exists()
    t = await orch.wait(orch.submit("mostra la skill inesistente").id)
    assert t.status is Status.ERROR


async def test_agent_reads_skill(cfg, apps):
    from jarvis.app import build_orchestrator
    cfg.permissions["model.chat"] = "auto"
    call = {"id": "c1", "type": "function", "function": {"name": "skills_read", "arguments": '{"name": "saluto"}'}}
    o = build_orchestrator(cfg, apps, provider=MockProvider([ModelResponse("", [call]), "Ciao, fatto."]))
    o.tools["skills.save"].store.save("saluto", "Saluta in modo formale.")
    t = await o.wait(o.submit("fai come sai per salutare il cliente").id)
    assert t.status is Status.DONE and t.steps[0].tool == "skills.read" and t.steps[0].ok
    await o.stop()
