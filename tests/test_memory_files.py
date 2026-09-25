import asyncio

import pytest

from jarvis.core.state import Status
from jarvis.routing.router import RuleRouter
from jarvis.tools.files import TRASH


async def wait_status(t, status, timeout=5):
    for _ in range(int(timeout / 0.02)):
        if t.status == status:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(t.status)


async def confirm_and_wait(orch, text, approve=True):
    t = orch.submit(text)
    await wait_status(t, Status.AWAITING_CONFIRMATION)
    preview = t.pending.preview
    orch.confirm(t.id, t.pending.action_hash, approve)
    await orch.wait(t.id)
    return t, preview


@pytest.mark.parametrize("text,kind,slots", [
    ("ricorda che preferisco il caffè amaro", "remember", {"fact": "preferisco il caffè amaro"}),
    ("cosa ricordi di me?", "memory_list", {}),
    ("dimentica caffè", "forget", {"query": "caffè"}),
    ("cerca nelle note riunione", "vault_search", {"query": "riunione"}),
    ("elenca i file", "files_list", {}),
    ("elenca i file in progetti", "files_list", {"path": "progetti"}),
    ("leggi il file appunti.txt", "files_read", {"path": "appunti.txt"}),
    ("elimina il file vecchio.txt", "files_delete", {"path": "vecchio.txt"}),
    ("sposta il file a.txt in archivio", "files_move", {"src": "a.txt", "dst": "archivio"}),
])
def test_new_intents(text, kind, slots):
    i = RuleRouter().route(text)
    assert (i.kind, i.slots) == (kind, slots)


async def test_memory_cycle(orch):
    t, preview = await confirm_and_wait(orch, "ricorda che preferisco il caffè amaro")
    assert t.status is Status.DONE and "caffè amaro" in preview
    assert any("caffè amaro" in f for f in orch.memory.facts())
    t = await orch.wait(orch.submit("cosa ricordi").id)
    assert "caffè amaro" in t.result
    t, preview = await confirm_and_wait(orch, "dimentica caffè")
    assert "caffè amaro" in preview and orch.memory.facts() == []


async def test_memory_rejects_secrets_and_rejection(orch):
    t, _ = await confirm_and_wait(orch, "ricorda che la password=ciao123")
    assert t.status is Status.ERROR and orch.memory.facts() == []
    t, _ = await confirm_and_wait(orch, "ricorda che amo il mare", approve=False)
    assert orch.memory.facts() == []


async def test_vault_search(orch):
    orch.vault.write_note("projects", "Riunione", "decidere il budget di ottobre")
    t = await orch.wait(orch.submit("cerca nelle note budget").id)
    assert t.status is Status.DONE and "projects/" in t.result


async def test_files_without_workdir_refused(orch):
    t = await orch.wait(orch.submit("elenca i file").id)
    assert t.status is Status.ERROR and "Nessuna cartella di lavoro" in t.result


@pytest.fixture
def wd(cfg, tmp_path):
    d = tmp_path / "lavoro"
    d.mkdir()
    (d / "appunti.txt").write_text("lista della spesa")
    (d / ".env").write_text("API_KEY=x")
    (d / "sub").mkdir()
    cfg.work_dir = d
    return d


async def test_files_list_read(wd, cfg, apps):
    from jarvis.app import build_orchestrator
    o = build_orchestrator(cfg, apps)
    t = await o.wait(o.submit("elenca i file").id)
    assert t.status is Status.DONE and "3 elementi" in t.result
    t = await o.wait(o.submit("leggi il file appunti.txt").id)
    assert t.status is Status.DONE and any("lista della spesa" in l for l in t.log)
    t = await o.wait(o.submit("leggi il file .env").id)
    assert t.status is Status.ERROR and "segreti" in t.result
    t = await o.wait(o.submit("leggi il file ../../etc/passwd").id)
    assert t.status is Status.ERROR and "fuori dalla cartella" in t.result


async def test_files_move_delete_with_confirmation(wd, cfg, apps):
    from jarvis.app import build_orchestrator
    o = build_orchestrator(cfg, apps)
    t, _ = await confirm_and_wait(o, "sposta il file appunti.txt in sub", approve=False)
    assert (wd / "appunti.txt").exists()
    t, _ = await confirm_and_wait(o, "sposta il file appunti.txt in sub")
    assert t.status is Status.DONE and (wd / "sub" / "appunti.txt").exists()
    t, preview = await confirm_and_wait(o, "elimina il file sub")
    assert t.status is Status.DONE and not (wd / "sub").exists() and "1 file" in preview
    trashed = list((wd / TRASH).iterdir())
    assert len(trashed) == 1 and (trashed[0] / "appunti.txt").exists()
    t = await o.wait(o.submit(f"leggi il file {TRASH}/x").id)
    assert t.status is Status.ERROR


async def test_write_never_overwrites(wd, cfg, apps):
    from jarvis.tools.files import WorkDir, WriteFileTool
    tool = WriteFileTool(WorkDir(wd))
    assert (await tool.run({"path": "nuovo.md", "content": "ciao"})).ok
    r = await tool.run({"path": "nuovo.md", "content": "altro"})
    assert not r.ok and (wd / "nuovo.md").read_text() == "ciao"
