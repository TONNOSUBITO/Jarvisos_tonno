import asyncio

from jarvis.core.orchestrator import Orchestrator
from jarvis.core.state import Status
from jarvis.routing.router import Intent, IntentRouter
from jarvis.tools.audit import AuditLog
from jarvis.tools.base import Tool, ToolResult


async def wait_status(orch, task, status, timeout=5):
    for _ in range(int(timeout / 0.02)):
        if task.status == status:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"stato {task.status} invece di {status}")


async def test_open_approved_app(orch, apps):
    t = await orch.wait(orch.submit("apri calcolatrice").id)
    assert t.status is Status.DONE
    assert apps.launched == [["calc.exe"]]
    assert "ho aperto l'app calcolatrice" in t.report
    assert "non ho inviato" in t.report


async def test_unapproved_app_refused(orch, apps):
    t = await orch.wait(orch.submit("apri regedit").id)
    assert t.status is Status.ERROR and apps.launched == []
    assert "non è tra le app approvate" in t.result


async def test_unknown_asks_clarification_without_model(orch):
    t = await orch.wait(orch.submit("qual è il senso della vita").id)
    assert t.status is Status.DONE and "Non ho capito" in t.result and t.steps == []


async def test_denied_capability(orch, cfg, apps):
    cfg.permissions["app.open"] = "deny"
    t = await orch.wait(orch.submit("apri calcolatrice").id)
    assert t.status is Status.ERROR and "Permesso negato" in t.result and apps.launched == []


async def test_note_requires_confirmation_then_saves(orch):
    t = orch.submit("prepara una nota: comprare latte e pane")
    await wait_status(orch, t, Status.AWAITING_CONFIRMATION)
    assert orch.vault.list_notes() == []
    assert "comprare latte" in t.pending.preview
    h = t.pending.action_hash
    assert not orch.confirm(t.id, "hash-sbagliato", True)
    assert orch.confirm(t.id, h, True)
    await orch.wait(t.id)
    assert t.status is Status.DONE
    notes = orch.vault.list_notes()
    assert len(notes) == 1 and "comprare latte" in orch.vault.read(notes[0])
    assert not orch.confirm(t.id, h, True)  # non riutilizzabile


async def test_note_rejected_saves_nothing(orch):
    t = orch.submit("prepara una nota: segreto di famiglia")
    await wait_status(orch, t, Status.AWAITING_CONFIRMATION)
    assert orch.confirm(t.id, t.pending.action_hash, False)
    await orch.wait(t.id)
    assert t.status is Status.ERROR and orch.vault.list_notes() == []
    assert "non ho salvato nulla" in t.report


async def test_confirmation_timeout(orch, cfg):
    cfg.limits.confirm_timeout_s = 0.2
    t = await orch.wait(orch.submit("prepara una nota: x").id)
    assert t.status is Status.ERROR and orch.vault.list_notes() == []


# ---- stop / timeout / limiti con tool finti ----
class SlowTool(Tool):
    name = capability = "app.open"

    def __init__(self, delay):
        self.delay = delay
        self.stopped = False

    async def run(self, args):
        await asyncio.sleep(self.delay)
        return ToolResult(True, "finito")

    async def stop(self):
        self.stopped = True


class ManyStepsRouter(IntentRouter):
    def route(self, text):
        return Intent("open_app", {"app": "x"})


def make(cfg, tool, tmp_path):
    return Orchestrator(cfg, ManyStepsRouter(), [tool], AuditLog(tmp_path / "a.jsonl", "t"))


async def test_stop_interrupts_running_tool(cfg, tmp_path):
    tool = SlowTool(10)
    o = make(cfg, tool, tmp_path)
    t = o.submit("qualsiasi")
    await wait_status(o, t, Status.EXECUTING)
    assert await o.stop() == [t.id]
    assert t.status is Status.STOPPED and tool.stopped
    assert "Fermato" in t.report


async def test_stop_single_task(cfg, tmp_path):
    o = make(cfg, SlowTool(10), tmp_path)
    t1, t2 = o.submit("a"), o.submit("b")
    await wait_status(o, t1, Status.EXECUTING)
    await o.stop(t1.id)
    assert t1.status is Status.STOPPED and not t2.status.terminal
    await o.stop()


async def test_tool_timeout(cfg, tmp_path):
    cfg.limits.tool_timeout_s = 0.1
    t = await (o := make(cfg, SlowTool(5), tmp_path)).wait(o.submit("x").id)
    assert t.status is Status.ERROR and "Timeout" in t.result


async def test_task_timeout(cfg, tmp_path):
    cfg.limits.task_timeout_s = 0.1
    t = await (o := make(cfg, SlowTool(5), tmp_path)).wait(o.submit("x").id)
    assert t.status is Status.ERROR and "Timeout attività" in t.result


async def test_max_steps(orch, cfg):
    cfg.limits.max_steps = 1
    t = orch.submit("cerca e apri qualcosa")  # piano di 2 passi
    await orch.wait(t.id)
    assert t.status is Status.ERROR and "Limite di 1 passi" in t.result
    assert len(t.steps) == 1


async def test_voice_stop_command_stops_others(cfg, tmp_path, orch):
    slow = SlowTool(10)
    o = make(cfg, slow, tmp_path)
    t = o.submit("x")
    await wait_status(o, t, Status.EXECUTING)
    # il comando "stop" passa dal RuleRouter
    from jarvis.routing.router import RuleRouter
    o.router = RuleRouter()
    s = await o.wait(o.submit("fermati").id)
    assert s.status is Status.DONE and t.status is Status.STOPPED
