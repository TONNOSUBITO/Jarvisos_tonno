"""API locale + UI minimale. Solo loopback; ogni chiamata richiede il token di sessione
incluso nella pagina (protegge da CSRF e da altri siti aperti nel browser)."""

from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from jarvis import __version__
from jarvis.config import DeviceConfig
from jarvis.core.orchestrator import Orchestrator
from jarvis.audio.base import AudioError, VoiceUnavailable, wav_to_float32
from jarvis.memory.vault import VaultError
from jarvis.tools.permissions import Decision

MAX_AUDIO_BYTES = 4 * 1024 * 1024

LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "[::1]"]


class CommandIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class NoteIn(BaseModel):
    content: str = Field(max_length=200_000)


class MetricIn(BaseModel):
    name: str = Field(pattern=r"^[a-z_]{1,32}$")
    value: float


class ConfirmIn(BaseModel):
    action_hash: str
    approve: bool


def _preload(orch: Orchestrator) -> None:
    """Carica STT/TTS locali in background; gli errori restano visibili al primo uso."""
    for comp in (orch.stt, orch.tts):
        loader = getattr(comp, "_load", None)
        if loader and getattr(comp, "local", True):
            try:
                loader()
            except Exception as e:  # noqa: BLE001
                logging.getLogger("jarvis").warning("Precaricamento %s fallito: %s", comp.name, e)


def create_app(cfg: DeviceConfig, orch: Orchestrator, token: str | None = None,
               allowed_hosts: list[str] | None = None) -> FastAPI:
    token = token or secrets.token_urlsafe(24)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if cfg.voice.preload:
            asyncio.get_running_loop().run_in_executor(None, _preload, orch)
        yield
        await orch.stop()  # chiude browser e attività alla chiusura

    app = FastAPI(title="Jarvis", version=__version__, docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or LOOPBACK_HOSTS)
    page = files("jarvis").joinpath("web/index.html").read_text(encoding="utf-8")

    def auth(x_jarvis_token: str = Header(default="")) -> None:
        if not secrets.compare_digest(x_jarvis_token, token):
            raise HTTPException(401, "token mancante o errato")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return page.replace("__JARVIS_TOKEN__", token).replace("__DEVICE_ID__", cfg.device_id)

    @app.post("/api/command", dependencies=[Depends(auth)])
    async def command(body: CommandIn) -> dict:
        return orch.submit(body.text).to_dict()

    @app.get("/api/state", dependencies=[Depends(auth)])
    async def state() -> dict:
        tasks = sorted(orch.tasks.values(), key=lambda t: t.created_at, reverse=True)[:20]
        return {"device_id": cfg.device_id, "tasks": [t.to_dict() for t in tasks]}

    @app.post("/api/tasks/{task_id}/confirm", dependencies=[Depends(auth)])
    async def confirm(task_id: str, body: ConfirmIn) -> dict:
        if not orch.confirm(task_id, body.action_hash, body.approve):
            raise HTTPException(409, "conferma non valida, scaduta o già usata")
        return {"ok": True}

    @app.post("/api/stop", dependencies=[Depends(auth)])
    async def stop_all() -> dict:
        return {"stopped": await orch.stop()}

    @app.post("/api/tasks/{task_id}/stop", dependencies=[Depends(auth)])
    async def stop_one(task_id: str) -> dict:
        if task_id not in orch.tasks:
            raise HTTPException(404, "attività inesistente")
        return {"stopped": await orch.stop(task_id)}

    @app.get("/api/info", dependencies=[Depends(auth)])
    async def info() -> dict:
        v = cfg.voice
        tts_name = orch.tts.name if orch.tts else ("browser" if v.tts_engine == "browser" else "none")
        return {
            "device_id": cfg.device_id, "version": __version__,
            "stt": orch.stt.name if orch.stt else "none",
            "tts": tts_name, "tts_local": bool(orch.tts is None or orch.tts.local),
            "speak_replies": v.speak_replies, "max_audio_s": v.max_audio_s,
            "model": "attivo" if orch.agent and orch.policy.decide("model.chat") is not Decision.DENY else "disattivato",
            "spesa_eur": round(orch.budget.spent_eur, 6) if orch.budget else 0.0,
            "budget_eur": cfg.limits.budget_eur,
        }

    @app.post("/api/voice", dependencies=[Depends(auth)])
    async def voice(request: Request) -> dict:
        body = await request.body()  # solo in memoria, mai su disco
        if len(body) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "audio troppo grande")
        try:
            audio = wav_to_float32(body, cfg.voice.max_audio_s)
        except AudioError as e:
            raise HTTPException(400, str(e))
        if orch.stt is None:
            raise HTTPException(503, "trascrizione non configurata ([voice] stt_engine)")
        return orch.submit(audio=audio).to_dict()

    @app.post("/api/tts", dependencies=[Depends(auth)])
    async def tts(body: SpeakIn) -> Response:
        if orch.tts is None:
            return Response(status_code=204)  # la UI usa la sintesi del browser
        if not orch.tts.local and orch.policy.decide("tts.cloud") is Decision.DENY:
            raise HTTPException(403, "TTS cloud non autorizzato (permesso tts.cloud)")
        try:
            audio = await orch.tts.synthesize(body.text)
        except VoiceUnavailable as e:
            raise HTTPException(503, str(e))
        orch.audit.write("tts", engine=orch.tts.name, chars=len(body.text), local=orch.tts.local)
        return Response(audio, media_type=orch.tts.content_type)

    @app.post("/api/tasks/{task_id}/metric", dependencies=[Depends(auth)])
    async def metric(task_id: str, body: MetricIn) -> dict:
        t = orch.tasks.get(task_id)
        if t is None:
            raise HTTPException(404, "attività inesistente")
        t.metrics[body.name] = round(body.value, 1)
        orch.audit.write("metric", task=task_id, name=body.name, value=body.value)
        return {"ok": True}

    @app.get("/api/memory", dependencies=[Depends(auth)])
    async def memory() -> dict:
        return {"facts": orch.memory.facts() if orch.memory else []}

    @app.put("/api/vault/note", dependencies=[Depends(auth)])
    async def vault_update(path: str, body: NoteIn) -> dict:
        try:
            orch.vault.update(path, body.content)
        except VaultError as e:
            raise HTTPException(400, str(e))
        return {"updated": path}

    @app.get("/api/vault", dependencies=[Depends(auth)])
    async def vault_list() -> dict:
        return {"notes": orch.vault.list_notes()}

    @app.get("/api/vault/note", dependencies=[Depends(auth)])
    async def vault_read(path: str) -> dict:
        try:
            return {"path": path, "content": orch.vault.read(path)}
        except (VaultError, FileNotFoundError) as e:
            raise HTTPException(404, str(e))

    @app.delete("/api/vault/note", dependencies=[Depends(auth)])
    async def vault_delete(path: str) -> dict:
        try:
            orch.vault.delete(path)
        except VaultError as e:
            raise HTTPException(404, str(e))
        return {"deleted": path}

    return app
