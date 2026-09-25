import functools
import http.server
import threading
from pathlib import Path

import pytest

from jarvis.app import build_orchestrator
from jarvis.config import DeviceConfig
from jarvis.tools.apps import MockAppAdapter

SITE = Path(__file__).parent / "fixtures" / "site"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def site_url():
    handler = functools.partial(_Quiet, directory=str(SITE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def cfg(tmp_path, site_url):
    c = DeviceConfig(device_id="test", data_dir=tmp_path / "data", vault_dir=tmp_path / "vault")
    c.allowed_apps = {"calcolatrice": ["calc.exe"]}
    c.browser.headless = True
    c.browser.allow_local_network = True
    c.browser.search_url = site_url + "/search.html?q={q}"
    c.browser.result_selector = "a.result"
    c.limits.confirm_timeout_s = 5
    return c


@pytest.fixture
def apps():
    return MockAppAdapter()


@pytest.fixture
async def orch(cfg, apps):
    o = build_orchestrator(cfg, apps)
    yield o
    await o.stop()
