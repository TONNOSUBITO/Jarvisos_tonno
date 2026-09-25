"""Avvio: `python -m jarvis [--config config/device.toml] [--port 8765]`."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import sys

import uvicorn

from jarvis.app import build_orchestrator
from jarvis.config import load_config
from jarvis.server import create_app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jarvis")
    ap.add_argument("--config", default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--headless", action="store_true", help="browser senza finestra (cloud/test)")
    a = ap.parse_args(argv)

    host = "127.0.0.1" if a.host == "localhost" else a.host
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
    except ValueError:
        print("Rifiutato: Jarvis ascolta solo su loopback (127.0.0.1 / ::1).", file=sys.stderr)
        return 2

    cfg = load_config(a.config)
    if a.headless:
        cfg.browser.headless = True
    app = create_app(cfg, build_orchestrator(cfg))
    print(f"Jarvis {cfg.device_id} su http://{host}:{a.port}  (Ctrl+C per fermare)")
    # asyncio.run usa il loop di default (Proactor su Windows), necessario a Playwright
    # per avviare Chromium; uvicorn.run su Windows potrebbe imporre un loop Selector.
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=a.port, log_level="warning"))
    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
