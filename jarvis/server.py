"""API locale + UI minimale. Solo loopback; ogni chiamata richiede il token di sessione
incluso nella pagina (protegge da CSRF e da altri siti aperti nel browser)."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from jarvis import __version__
from jarvis.config import DeviceConfig
from jarvis.core.orchestrator import Orchestrator
from jarvis.memory.vault import VaultError

LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "[::1]"]


class CommandIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ConfirmIn(BaseModel):
    action_hash: str
    approve: bool


def create_app(cfg: DeviceConfig, orch: Orchestrator, token: str | None = None,
               allowed_hosts: list[str] | None = None) -> FastAPI:
    token = token or secrets.token_urlsafe(24)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
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
