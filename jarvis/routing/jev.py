"""Router Jev (TypeSafe): secondo livello, solo quando le regole non capiscono.

Jev non genera testo: sceglie un'opzione in un insieme chiuso e restituisce la confidenza.
Qui decide l'intento (e l'app, tra quelle approvate); sotto `min_confidence` → `unknown`.
API: https://docs.typesafe.ai/api — prezzo solo sui token in input (docs.typesafe.ai/models).
Il testo del comando esce dal PC verso TypeSafe: per questo è opt-in (`[router] engine`).
"""

from __future__ import annotations

import os
import re

import httpx

from jarvis.providers.base import BudgetMeter
from jarvis.routing.router import Intent, normalize

INTENTS = {
    "open_app": "aprire o avviare un programma del computer",
    "web_search": "cercare informazioni su internet",
    "memory_list": "chiedere cosa Jarvis ricorda dell'utente",
    "files_list": "vedere l'elenco dei file",
    "vault_search": "cercare qualcosa nelle note personali",
    "stop": "fermare o annullare quello che Jarvis sta facendo",
    "domanda": "domanda generale, conversazione o compito articolato",
    "altro": "nessuna delle altre opzioni o frase incomprensibile",
}
_LEAD = re.compile(r"^(?:(?:cerca(?:mi)?|trova(?:mi)?|dimmi|mostra(?:mi)?|voglio sapere|vorrei sapere|"
                   r"informazioni su|nelle (?:mie )?note)\s+)+", re.I)


class JevRouter:
    def __init__(self, cfg, apps: list[str], budget: BudgetMeter, api_key: str,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.cfg = cfg
        self.apps = apps
        self.budget = budget
        self.api_key = api_key
        self.transport = transport

    def _questions(self) -> dict:
        intents = {k: v for k, v in INTENTS.items() if k != "open_app" or self.apps}
        q = {"intento": {"type": "choice", "instructions": "Che cosa chiede l'utente al suo assistente?",
                         "criteria": intents}}
        if self.apps:
            q["app"] = {"type": "choice", "instructions": "Quale di questi programmi vuole aprire l'utente?",
                        "criteria": {a: None for a in self.apps}}
        return q

    async def route_async(self, text: str) -> tuple[Intent, str]:
        """(intento, nota per registro e audit). Qualsiasi problema → unknown."""
        b = self.budget
        if b.limit_eur <= 0 or b.spent_eur >= b.limit_eur:
            return Intent("unknown"), "Jev saltato: budget esaurito o a zero"
        t = normalize(text)
        try:
            async with httpx.AsyncClient(timeout=self.cfg.jev_timeout_s, transport=self.transport) as c:
                r = await c.post(self.cfg.jev_url, headers={"Authorization": f"Bearer {self.api_key}"},
                                 json={"state": t, "model": self.cfg.jev_model, "questions": self._questions()})
            r.raise_for_status()
            body = r.json()
            b.charge(body.get("usage", {}).get("input_tokens", 0) * self.cfg.jev_price_in_per_mtok_eur / 1e6)
            a = body["answers"]["intento"]
            kind, conf = a["choice"], float(a["confidence"])
        except Exception as e:  # noqa: BLE001 — rete, HTTP o risposta malformata: si torna alle regole
            return Intent("unknown"), f"Jev non disponibile: {type(e).__name__}"
        note = f"Jev: {kind} (confidenza {conf:.2f})"
        if conf < self.cfg.jev_min_confidence or kind not in INTENTS or kind in ("domanda", "altro"):
            return Intent("unknown"), note
        if kind == "open_app":
            app = body["answers"].get("app") or {}
            if app.get("choice") not in self.apps or float(app.get("confidence") or 0) < self.cfg.jev_min_confidence:
                return Intent("unknown"), note + ", app incerta"
            return Intent("open_app", {"app": app["choice"]}), note
        if kind in ("web_search", "vault_search"):
            return Intent(kind, {"query": _LEAD.sub("", t).strip() or t}), note
        return Intent(kind), note


def build_jev(cfg, apps: list[str], budget: BudgetMeter) -> JevRouter | None:
    """Solo se attivato in [router], con chiave nel .env e budget > 0."""
    key = os.environ.get(cfg.jev_api_key_env, "")
    if cfg.engine != "rules+jev" or not key or budget.limit_eur <= 0:
        return None
    return JevRouter(cfg, apps, budget, key)
