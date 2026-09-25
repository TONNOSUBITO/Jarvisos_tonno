"""Configurazione per dispositivo.

Ogni PC ha il proprio file TOML locale (non committato): `device_id`, piattaforma,
cartelle autorizzate, app approvate, permessi per capacità e limiti.
I default sono restrittivi: ciò che non è configurato è negato.
"""

from __future__ import annotations

import os
import platform
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

VALID_MODES = {"auto", "confirm", "deny"}

# Capacità note. Il valore è il livello di default se il file non dice nulla.
DEFAULT_PERMISSIONS: dict[str, str] = {
    "app.open": "auto",        # solo app in allowlist
    "web.search": "auto",
    "web.open": "auto",        # lettura pagine in browser dedicato
    "notes.draft": "auto",     # bozza in memoria, nessuna scrittura
    "notes.save": "confirm",   # scrittura su disco: sempre conferma in Fase 1
    "model.chat": "deny",      # nessuna chiamata a modelli per default
    "tts.cloud": "deny",       # invio di testo a TTS esterni (Fish): opt-in esplicito
    "memory.remember": "confirm",
    "memory.list": "auto",
    "memory.forget": "confirm",
    "vault.search": "auto",
    "files.list": "auto",      # solo dentro [device] work_dir
    "files.read": "auto",
    "files.write": "confirm",
    "files.move": "confirm",
    "files.delete": "confirm", # sposta nel cestino, recuperabile
    "shell.exec": "deny",      # non esiste nemmeno un tool: resta negato
}


@dataclass
class Limits:
    task_timeout_s: float = 60.0
    tool_timeout_s: float = 30.0
    confirm_timeout_s: float = 300.0
    max_steps: int = 8
    budget_eur: float = 0.0  # 0 = nessuna spesa consentita


@dataclass
class BrowserConfig:
    headless: bool = False
    # Modello di URL di ricerca: {q} viene sostituito dalla query codificata.
    search_url: str = "https://html.duckduckgo.com/html/?q={q}"
    result_selector: str = "a.result__a"
    allowed_domains: list[str] = field(default_factory=list)  # vuoto = tutti (http/https)
    allow_local_network: bool = False
    max_results: int = 5
    max_page_chars: int = 2000


@dataclass
class VoiceConfig:
    # STT locale: "faster-whisper" (default, misurato più rapido in cloud) | "whispercpp" | "none"
    stt_engine: str = "faster-whisper"
    stt_model: str = "base"          # multilingue; "small" solo se la CPU regge
    stt_language: str = "it"
    # TTS: "kokoro" (locale) | "browser" (speechSynthesis locale) | "fish" (cloud, opt-in) | "none"
    tts_engine: str = "browser"
    tts_voice: str = "if_sara"       # Kokoro: if_sara / im_nicola
    tts_speed: float = 1.0
    kokoro_model: str = "data/models/kokoro-v1.0.onnx"
    kokoro_voices: str = "data/models/voices-v1.0.bin"
    fish_model: str = "s2.1-pro-free"
    fish_reference_id: str = ""      # id voce Fish; vuoto = voce di default del servizio
    speak_replies: bool = True
    preload: bool = True             # carica i modelli voce all'avvio (evita l'attesa al primo comando)
    max_audio_s: float = 30.0        # registrazioni più lunghe vengono rifiutate


@dataclass
class ProviderConfig:
    name: str = "locale"
    base_url: str = ""                      # es. OmniRoute http://127.0.0.1:20128/v1, Ollama http://127.0.0.1:11434/v1
    model: str = ""
    api_key_env: str = ""                   # NOME della variabile in .env, mai la chiave
    paid: bool = False                      # True = può generare costi
    price_in_per_mtok_eur: float = 0.0      # per il contatore spesa (inserito da te)
    price_out_per_mtok_eur: float = 0.0


@dataclass
class ModelConfig:
    enabled: bool = False
    allow_paid: bool = False
    timeout_s: float = 30.0
    agent_tools: bool = True                # livello 3: il modello può proporre azioni con i tool
    allow_private_data: bool = False        # file/memoria/note visibili al modello (se cloud: escono dal PC)
    providers: list[ProviderConfig] = field(default_factory=list)  # in ordine di fallback


@dataclass
class DeviceConfig:
    device_id: str = "dev-cloud"
    platform: str = field(default_factory=lambda: platform.system().lower())
    data_dir: Path = Path("data")
    vault_dir: Path = Path("data/vault")
    work_dir: Path | None = None  # unica cartella in cui Jarvis può gestire file
    app_adapter: str = "mock"  # mock | native
    allowed_apps: dict[str, list[str]] = field(default_factory=dict)
    permissions: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PERMISSIONS))
    limits: Limits = field(default_factory=Limits)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)

    def permission(self, capability: str) -> str:
        mode = self.permissions.get(capability, "deny")
        return mode if mode in VALID_MODES else "deny"


def _section(cls, raw: dict | None):
    raw = raw or {}
    known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"Chiavi sconosciute in [{cls.__name__}]: {sorted(unknown)}")
    return cls(**known)


def _model_section(raw: dict | None) -> ModelConfig:
    raw = dict(raw or {})
    providers = [_section(ProviderConfig, p) for p in raw.pop("providers", [])]
    m = _section(ModelConfig, raw)
    m.providers = providers
    return m


def load_config(path: str | os.PathLike | None = None) -> DeviceConfig:
    path = Path(path or os.environ.get("JARVIS_CONFIG", "config/device.toml"))
    if not path.exists():
        return DeviceConfig()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    perms = dict(DEFAULT_PERMISSIONS)
    for cap, mode in (raw.get("permissions") or {}).items():
        if mode not in VALID_MODES:
            raise ValueError(f"Permesso non valido per {cap}: {mode!r}")
        perms[cap] = mode
    if perms.get("shell.exec") != "deny":
        raise ValueError("shell.exec non è supportato: deve restare 'deny'")
    dev = raw.get("device") or {}
    cfg = DeviceConfig(
        device_id=dev.get("device_id", "dev-local"),
        platform=dev.get("platform", platform.system().lower()),
        data_dir=Path(dev.get("data_dir", "data")),
        vault_dir=Path(dev.get("vault_dir", "data/vault")),
        work_dir=Path(dev["work_dir"]) if dev.get("work_dir") else None,
        app_adapter=dev.get("app_adapter", "mock"),
        allowed_apps={k: list(v) for k, v in (raw.get("apps") or {}).items()},
        permissions=perms,
        limits=_section(Limits, raw.get("limits")),
        browser=_section(BrowserConfig, raw.get("browser")),
        model=_model_section(raw.get("model")),
        voice=_section(VoiceConfig, raw.get("voice")),
    )
    return cfg
