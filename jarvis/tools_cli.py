"""Comandi di servizio: `python -m jarvis models` e `python -m jarvis doctor`."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import platform
import shutil
import sys
import urllib.request
from pathlib import Path

from jarvis.config import DeviceConfig

# Fonte: release ufficiali di thewh1teagle/kokoro-onnx (model-files-v1.1).
# Hash calcolati sui file scaricati il 25/09/2026: un file diverso viene rifiutato.
KOKORO_FILES = {
    "kokoro-v1.0.onnx": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
        "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a"),
    "voices-v1.0.bin": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
        "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_models(cfg: DeviceConfig) -> int:
    """Scarica i modelli voce locali (circa 350 MB Kokoro + 145 MB Whisper base)."""
    dest = Path(cfg.voice.kokoro_model).parent
    dest.mkdir(parents=True, exist_ok=True)
    if cfg.voice.tts_engine == "kokoro" or "--kokoro" in sys.argv:
        for name, (url, sha) in KOKORO_FILES.items():
            target = dest / name
            if target.exists() and _sha256(target) == sha:
                print(f"✔ {name} già presente e verificato")
                continue
            print(f"↓ {name} da {url}")
            tmp = target.with_suffix(".part")
            urllib.request.urlretrieve(url, tmp)
            if _sha256(tmp) != sha:
                tmp.unlink()
                print(f"✖ {name}: hash diverso da quello atteso, file scartato")
                return 1
            tmp.replace(target)
            print(f"✔ {name} verificato")
    stt = cfg.voice.stt_engine
    if stt == "faster-whisper":
        from jarvis.audio.stt import make_stt

        print(f"↓ modello {stt} «{cfg.voice.stt_model}» (Hugging Face)…")
        make_stt(stt, cfg.voice.stt_model, cfg.data_dir)._load()
        print("✔ trascrizione pronta")
    return 0


def _mem_gb() -> str:
    try:
        if platform.system() == "Windows":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong)] + [(f"x{i}", ctypes.c_ulonglong) for i in range(5)]
            m = MS(); m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return f"{m.total / 2**30:.1f} GB totali, {m.avail / 2**30:.1f} GB liberi"
        info = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        tot = int(info["MemTotal"].split()[0]) / 2**20
        av = int(info["MemAvailable"].split()[0]) / 2**20
        return f"{tot:.1f} GB totali, {av:.1f} GB liberi"
    except Exception:  # noqa: BLE001
        return "non rilevata"


def doctor(cfg: DeviceConfig, config_path: str | None) -> int:
    ok = True

    def line(good: bool | None, msg: str) -> None:
        nonlocal ok
        mark = {True: "✔", False: "✖", None: "•"}[good]
        ok = ok and good is not False
        print(f"{mark} {msg}")

    print(f"Jarvis doctor — dispositivo «{cfg.device_id}»")
    line(None, f"Sistema: {platform.system()} {platform.release()} · CPU: {platform.processor() or platform.machine()}"
               f" · {os.cpu_count()} thread · RAM: {_mem_gb()}")
    line(sys.version_info >= (3, 11), f"Python {platform.python_version()} (serve 3.11+)")
    cp = Path(config_path or os.environ.get("JARVIS_CONFIG", "config/device.toml"))
    line(cp.exists() or None, f"Configurazione: {cp}" + ("" if cp.exists() else " assente → uso i default restrittivi"))
    exe = os.environ.get("JARVIS_CHROMIUM_PATH")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            path = exe or p.chromium.executable_path
        line(Path(path).exists(), f"Chromium per Playwright: {path}"
             + ("" if Path(path).exists() else " — esegui: python -m playwright install chromium"))
    except Exception as e:  # noqa: BLE001
        line(False, f"Playwright: {e}")
    v = cfg.voice
    mods = {"faster-whisper": "faster_whisper"}
    if v.stt_engine in mods:
        line(importlib.util.find_spec(mods[v.stt_engine]) is not None,
             f"Trascrizione {v.stt_engine} installata (pip install -e .[voice])")
    else:
        line(None, "Trascrizione disattivata")
    if v.tts_engine == "kokoro":
        line(importlib.util.find_spec("kokoro_onnx") is not None, "kokoro-onnx installato (pip install -e .[tts])")
        for f in (v.kokoro_model, v.kokoro_voices):
            line(Path(f).exists(), f"Modello Kokoro {f} (python -m jarvis models)")
    else:
        line(None, f"Risposta vocale: {v.tts_engine}")
    for name, argv in cfg.allowed_apps.items():
        found = shutil.which(argv[0]) or Path(argv[0]).exists()
        line(bool(found) or None, f"App «{name}»: {argv[0]}" + ("" if found else " non trovata nel PATH"))
    if cfg.work_dir:
        line(Path(cfg.work_dir).is_dir(), f"Cartella di lavoro: {cfg.work_dir}")
    m = cfg.model
    if m.enabled:
        line(cfg.permission("model.chat") != "deny", "permesso model.chat abilitato")
        for p in m.providers:
            key = f", chiave {p.api_key_env} {'presente' if os.environ.get(p.api_key_env) else 'MANCANTE'}" if p.api_key_env else ""
            line(None, f"Modello «{p.name}»: {p.base_url} ({p.model}){key}{' · A PAGAMENTO' if p.paid else ''}")
    else:
        line(None, "Modelli (livelli 2-3) disattivati")
    print("Tutto pronto." if ok else "Ci sono problemi da risolvere (✖).")
    return 0 if ok else 1
