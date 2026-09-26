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
    g = GuardedProvider(paid, BudgetMeter(0.015), allow_paid=True)
    await g.complete([])
    await g.complete([])  # spesi 0,01 < 0,015: ammessa, porta a 0,02
    with pytest.raises(BudgetExceeded):
        await g.complete([])
    assert len(paid.calls) == 2


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


def test_providers_example_file(tmp_path, monkeypatch):
    """config/providers.example.toml accodato a device.toml: 15 provider, saltati quelli senza chiave."""
    from pathlib import Path

    from jarvis.config import load_config
    from jarvis.providers.base import build_provider

    f = tmp_path / "device.toml"
    f.write_text('[model]\nenabled = true\n' + Path("config/providers.example.toml").read_text(encoding="utf-8"),
                 encoding="utf-8")
    for p in load_config(f).model.providers:
        if p.api_key_env:
            monkeypatch.delenv(p.api_key_env, raising=False)
    cfg = load_config(f)
    assert [p.name for p in cfg.model.providers] == [
        "omniroute", "groq", "cerebras", "gemini", "mistral", "openrouter", "cohere", "huggingface",
        "nvidia", "together", "anthropic", "deepseek", "fireworks", "openai", "xai"]
    assert [p.name for p in cfg.model.providers if not p.paid] == [
        "omniroute", "groq", "cerebras", "gemini", "mistral", "openrouter", "cohere", "huggingface"]
    # nessuna chiave → resta solo OmniRoute locale (senza chiave)
    assert [p.name for p in build_provider(cfg.model, BudgetMeter(0)).providers] == ["omniroute"]
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k2")
    fb = build_provider(cfg.model, BudgetMeter(0))
    assert [p.name for p in fb.providers] == ["omniroute", "gemini", "anthropic"] and not fb.allow_paid


def test_providers_example_is_ascii():
    """PowerShell 5.1 (Get-Content | Add-Content) riscrive i non-ASCII in ANSI: il file deve restare ASCII."""
    from pathlib import Path

    Path("config/providers.example.toml").read_bytes().decode("ascii")


async def test_gateway_reports_served_model_and_fallback_on_bad_replies():
    """OmniRoute con model "auto": l'HUD mostra il modello reale; spento o risposta rotta → provider successivo."""
    import httpx

    from jarvis.providers.base import FallbackProvider, OpenAICompatibleProvider

    def down(req):
        raise httpx.ConnectError("refused")

    def broken(req):
        return httpx.Response(200, json={"choices": []})

    def ok(req):
        return httpx.Response(200, json={"model": "groq/llama-x", "choices": [{"message": {"content": "ciao"}}]})

    mk = lambda name, h: OpenAICompatibleProvider("http://127.0.0.1:20128/v1", "auto", label=name,
                                                  transport=httpx.MockTransport(h))
    fb = FallbackProvider([mk("spento", down), mk("rotto", broken), mk("omniroute", ok)], BudgetMeter(0), False)
    r = await fb.complete([{"role": "user", "content": "x"}])
    assert r.text == "ciao" and r.provider == "omniroute · groq/llama-x"
    assert [e.split(":")[0] for e in fb.last_errors] == ["spento", "rotto"]


def test_doctor_local_gateway_probe():
    from jarvis.tools_cli import _is_loopback, _local_models

    assert _is_loopback("http://127.0.0.1:20128/v1") and not _is_loopback("https://api.groq.com/openai/v1")
    assert _local_models("http://127.0.0.1:9/v1") is None  # porta chiusa: nessuna eccezione


def test_doctor_reports_jev(monkeypatch, capsys):
    from jarvis.config import DeviceConfig
    from jarvis.tools_cli import doctor

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    cfg = DeviceConfig(app_adapter="mock")
    cfg.voice.stt_engine, cfg.voice.tts_engine = "none", "none"
    cfg.router.engine = "rules+jev"
    doctor(cfg, "nessun-file.toml")
    out = capsys.readouterr().out
    assert "✖ Router Jev: chiave TYPESAFE_API_KEY MANCANTE" in out
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    cfg.limits.budget_eur = 1.0
    doctor(cfg, "nessun-file.toml")
    assert "✔ Router Jev: chiave TYPESAFE_API_KEY presente, budget 1.0 € ok" in capsys.readouterr().out
