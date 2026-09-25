"""Integrazione reale con Chromium headless su sito di prova locale."""

import pytest

from jarvis.config import BrowserConfig
from jarvis.core.state import Status
from jarvis.tools.browser import UrlNotAllowed, check_url


async def test_search_and_open_first_result(orch):
    t = await orch.wait(orch.submit("cerca e apri documentazione").id)
    assert t.status is Status.DONE, t.result
    assert [s.tool for s in t.steps] == ["web.search", "web.open"]
    assert all(s.ok and s.verified for s in t.steps)
    assert "Documentazione di prova" in t.result
    assert "ho cercato «documentazione»" in t.report


async def test_prompt_injection_in_page_is_not_executed(orch):
    t = await orch.wait(orch.submit("cerca e apri documentazione").id)
    # il testo malevolo compare solo come contenuto non fidato, nessun passo extra
    assert any("[contenuto esterno, non fidato]" in l and "IGNORA" in l for l in t.log)
    assert len(t.steps) == 2 and orch.vault.list_notes() == []


async def test_search_only(orch):
    t = await orch.wait(orch.submit("cerca documentazione").id)
    assert t.status is Status.DONE and "2 risultati" in t.result


def test_url_rules():
    cfg = BrowserConfig()
    assert check_url("example.com", cfg) == "https://example.com"
    for bad in ("file:///etc/passwd", "javascript:alert(1)", "http://127.0.0.1:8765/api/stop",
                "http://localhost/", "http://192.168.1.1/"):
        with pytest.raises(UrlNotAllowed):
            check_url(bad, cfg)
    cfg.allowed_domains = ["python.org"]
    assert check_url("https://docs.python.org/3/", cfg)
    with pytest.raises(UrlNotAllowed):
        check_url("https://evil-python.org.example.com", cfg)


async def test_local_network_blocked_by_default(orch, cfg, site_url):
    cfg.browser.allow_local_network = False
    t = await orch.wait(orch.submit(f"apri il sito {site_url}/docs.html").id)
    assert t.status is Status.ERROR and "rete locale bloccato" in t.result
