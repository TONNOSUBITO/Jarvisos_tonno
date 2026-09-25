"""Prova end-to-end della voce: server reale, UI reale, microfono SIMULATO di Chromium.

Kokoro pronuncia un comando in un WAV, Chromium lo usa come microfono, la UI lo
registra col push-to-talk, Whisper trascrive, il router esegue sul sito di prova.
Stampa le misure. Uso (dalla radice del progetto, con modelli scaricati):

    python tests/e2e_voice.py
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.audio.base import float32_to_wav, wav_to_float32  # noqa: E402
from jarvis.audio.tts import KokoroTTS  # noqa: E402

PHRASE = "Cerca e apri documentazione."


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    models = ROOT / "data" / "models"
    wav = asyncio.run(KokoroTTS(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"),
                                "im_nicola").synthesize(PHRASE))
    a = wav_to_float32(wav, 60)
    a = np.concatenate([np.zeros(8000, np.float32), a, np.zeros(16000, np.float32)])
    cmd_wav = tmp / "cmd.wav"
    cmd_wav.write_bytes(float32_to_wav(a, 16000))

    site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "tests" / "fixtures" / "site")))
    threading.Thread(target=site.serve_forever, daemon=True).start()
    port = free_port()
    cfg = tmp / "device.toml"
    cfg.write_text(f"""[device]
device_id = "e2e"
data_dir = "{(ROOT / 'data').as_posix()}"
vault_dir = "{(tmp / 'vault').as_posix()}"
[browser]
headless = true
search_url = "http://127.0.0.1:{site.server_address[1]}/search.html?q={{q}}"
result_selector = "a.result"
allow_local_network = true
[voice]
tts_engine = "kokoro"
kokoro_model = "{(models / 'kokoro-v1.0.onnx').as_posix()}"
kokoro_voices = "{(models / 'voices-v1.0.bin').as_posix()}"
""", encoding="utf-8")
    # data_dir = data/ del progetto: riusa i modelli già scaricati (vault e config restano temporanee)
    srv = subprocess.Popen([sys.executable, "-m", "jarvis", "--config", str(cfg), "--port", str(port)], cwd=ROOT)
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", port), 1).close()
                break
            except OSError:
                time.sleep(1)
        time.sleep(10)  # precaricamento modelli
        from playwright.sync_api import expect, sync_playwright

        with sync_playwright() as p:
            b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                        f"--use-file-for-fake-audio-capture={cmd_wav}%noloop",
                                        "--autoplay-policy=no-user-gesture-required"])
            pg = b.new_context(permissions=["microphone"]).new_page()
            pg.goto(f"http://127.0.0.1:{port}/")
            expect(pg.locator("#info")).to_contain_text("faster-whisper", timeout=15000)
            box = pg.locator("#talk").bounding_box()
            pg.mouse.move(box["x"] + 10, box["y"] + 10)
            pg.mouse.down()
            expect(pg.locator("#talk")).to_have_text("● Sto ascoltando…", timeout=5000)
            pg.wait_for_timeout(3500)
            pg.mouse.up()
            expect(pg.locator("#status")).to_have_text("completato", timeout=90000)
            expect(pg.locator("#metrics")).to_contain_text("prima_risposta_audio_ms", timeout=60000)
            print("comando trascritto:", pg.inner_text("#command"))
            print("risultato:", pg.inner_text("#result"))
            print(pg.inner_text("#metrics"))
            assert "Documentazione di prova" in pg.inner_text("#result")
            b.close()
    finally:
        srv.terminate()
        site.shutdown()
    print("E2E voce OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
