import time

from fastapi.testclient import TestClient

from jarvis.app import build_orchestrator
from jarvis.server import create_app


def client(cfg, apps):
    orch = build_orchestrator(cfg, apps)
    app = create_app(cfg, orch, token="tok", allowed_hosts=["testserver"])
    return TestClient(app)


def poll(c, tid, pred, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        t = next(x for x in c.get("/api/state", headers={"X-Jarvis-Token": "tok"}).json()["tasks"] if x["id"] == tid)
        if pred(t):
            return t
        time.sleep(0.05)
    raise AssertionError(t)


def test_token_required(cfg, apps):
    with client(cfg, apps) as c:
        assert c.post("/api/command", json={"text": "apri calcolatrice"}).status_code == 401
        assert c.post("/api/stop", headers={"X-Jarvis-Token": "no"}).status_code == 401
        html = c.get("/").text
        assert "tok" in html and "STOP" in html and "J.A.R.V.I.S." in html


def test_foreign_host_rejected(cfg, apps):
    orch = build_orchestrator(cfg, apps)
    c = TestClient(create_app(cfg, orch, token="tok"))  # solo loopback
    assert c.get("/", headers={"host": "evil.example"}).status_code == 400


def test_full_flow_note_via_api(cfg, apps):
    H = {"X-Jarvis-Token": "tok"}
    with client(cfg, apps) as c:
        tid = c.post("/api/command", json={"text": "prepara una nota: prova API"}, headers=H).json()["id"]
        t = poll(c, tid, lambda t: t["status"] == "attesa_conferma")
        h = t["pending"]["action_hash"]
        assert c.post(f"/api/tasks/{tid}/confirm", json={"action_hash": "x", "approve": True}, headers=H).status_code == 409
        assert c.post(f"/api/tasks/{tid}/confirm", json={"action_hash": h, "approve": True}, headers=H).status_code == 200
        poll(c, tid, lambda t: t["status"] == "completato")
        notes = c.get("/api/vault", headers=H).json()["notes"]
        assert len(notes) == 1
        assert "prova API" in c.get("/api/vault/note", params={"path": notes[0]}, headers=H).json()["content"]
        assert c.delete("/api/vault/note", params={"path": notes[0]}, headers=H).status_code == 200
        assert c.get("/api/vault", headers=H).json()["notes"] == []


def test_stop_endpoint(cfg, apps):
    H = {"X-Jarvis-Token": "tok"}
    with client(cfg, apps) as c:
        tid = c.post("/api/command", json={"text": "prepara una nota: da fermare"}, headers=H).json()["id"]
        poll(c, tid, lambda t: t["status"] == "attesa_conferma")
        assert c.post("/api/stop", headers=H).json()["stopped"] == [tid]
        poll(c, tid, lambda t: t["status"] == "fermato")


def test_info_has_real_system_data(cfg, apps):
    with client(cfg, apps) as c:
        info = c.get("/api/info", headers={"X-Jarvis-Token": "tok"}).json()
        total, free = info["ram_gb"]
        assert 0 < free <= total and info["provider"] == ""
