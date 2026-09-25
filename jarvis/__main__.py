"""Avvio.

    python -m jarvis [--config config/device.toml] [--port 8765] [--open]
    python -m jarvis doctor      # verifica installazione
    python -m jarvis models      # scarica i modelli voce locali (verificati)
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import os
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from jarvis.app import build_orchestrator
from jarvis.config import load_config
from jarvis.server import create_app


def load_dotenv(path: Path = Path(".env")) -> None:
    """Carica .env (NOME=valore) senza sovrascrivere variabili già presenti."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jarvis")
    ap.add_argument("command", nargs="?", default="run", choices=["run", "doctor", "models"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--headless", action="store_true", help="browser senza finestra (cloud/test)")
    ap.add_argument("--open", action="store_true", help="apre l'interfaccia nel browser predefinito")
    ap.add_argument("--kokoro", action="store_true", help="con 'models': scarica Kokoro anche se non selezionato")
    a = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):  # console Windows non UTF-8: niente crash sui simboli
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    load_dotenv()
    cfg = load_config(a.config)
    if a.command == "doctor":
        from jarvis.tools_cli import doctor
        return doctor(cfg, a.config)
    if a.command == "models":
        from jarvis.tools_cli import download_models
        return download_models(cfg)

    host = "127.0.0.1" if a.host == "localhost" else a.host
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
    except ValueError:
        print("Rifiutato: Jarvis ascolta solo su loopback (127.0.0.1 / ::1).", file=sys.stderr)
        return 2

    if a.headless:
        cfg.browser.headless = True
    app = create_app(cfg, build_orchestrator(cfg))
    url = f"http://{host}:{a.port}"
    print(f"Jarvis {cfg.device_id} su {url}  (Ctrl+C per fermare)")
    if a.open:
        threading.Timer(1.5, webbrowser.open, [url]).start()
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
