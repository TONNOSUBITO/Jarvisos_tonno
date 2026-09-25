"""Browser dedicato via Playwright (profilo separato, mai quello personale).

Il testo delle pagine è restituito come dato NON fidato: non viene mai
interpretato come comando dal router o dall'orchestratore.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import socket
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

from jarvis.config import BrowserConfig
from jarvis.tools.base import Tool, ToolResult


class UrlNotAllowed(Exception):
    pass


def check_url(url: str, cfg: BrowserConfig) -> str:
    if "://" not in url:
        if re.match(r"^[a-zA-Z][\w+.\-]*:(?!\d)", url):  # javascript:, data:, mailto: …
            raise UrlNotAllowed("Schema non ammesso")
        url = "https://" + url
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise UrlNotAllowed(f"Schema non ammesso: {u.scheme}")
    host = (u.hostname or "").lower()
    if not host:
        raise UrlNotAllowed("URL senza host")
    if cfg.allowed_domains and not any(host == d or host.endswith("." + d) for d in cfg.allowed_domains):
        raise UrlNotAllowed(f"Dominio fuori allowlist: {host}")
    if not cfg.allow_local_network and _is_local(host):
        raise UrlNotAllowed(f"Indirizzo di rete locale bloccato: {host}")
    return url


def _is_local(host: str) -> bool:
    if host in ("localhost",) or host.endswith(".local") or host.endswith(".localhost"):
        return True
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            ips = [ipaddress.ip_address(i[4][0]) for i in socket.getaddrinfo(host, None)]
        except OSError:
            return False  # non risolvibile: lo scoprirà il browser
    return any(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved for ip in ips)


class BrowserSession:
    """Unica istanza Chromium condivisa tra i tool web. Avvio pigro."""

    def __init__(self, cfg: BrowserConfig, profile_dir: Path):
        self.cfg = cfg
        self.profile_dir = profile_dir
        self._pw = None
        self._ctx = None
        self._page = None
        self._lock = asyncio.Lock()

    async def page(self):
        async with self._lock:
            if self._page is None or self._page.is_closed():
                from playwright.async_api import async_playwright

                if self._pw is None:
                    self._pw = await async_playwright().start()
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                kwargs: dict[str, Any] = {"headless": self.cfg.headless}
                exe = os.environ.get("JARVIS_CHROMIUM_PATH")
                if exe:
                    kwargs["executable_path"] = exe
                self._ctx = await self._pw.chromium.launch_persistent_context(
                    str(self.profile_dir), accept_downloads=False, **kwargs)
                self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
            return self._page

    async def close(self) -> None:
        async with self._lock:
            if self._ctx is not None:
                try:
                    await self._ctx.close()
                except Exception:
                    pass
            if self._pw is not None:
                try:
                    await self._pw.stop()
                except Exception:
                    pass
            self._pw = self._ctx = self._page = None


class WebSearchTool(Tool):
    name = "web.search"
    capability = "web.search"
    description = "Cerca sul web e restituisce titoli e URL dei primi risultati."
    parameters = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    def __init__(self, session: BrowserSession):
        self.s = session

    async def run(self, args: dict[str, Any]) -> ToolResult:
        cfg = self.s.cfg
        url = check_url(cfg.search_url.replace("{q}", quote_plus(args["query"])), cfg)
        page = await self.s.page()
        await page.goto(url, wait_until="domcontentloaded")
        links = page.locator(cfg.result_selector)
        n = min(await links.count(), cfg.max_results)
        results = []
        for i in range(n):
            a = links.nth(i)
            href = await a.get_attribute("href") or ""
            title = (await a.inner_text()).strip()
            if href:
                results.append({"title": title[:200], "url": urljoin(page.url, href)})
        if not results:
            body = (await page.locator("body").inner_text()).lower()
            blocked = any(w in body for w in ("captcha", "anomaly", "robot", "unusual traffic", "traffico insolito"))
            why = ("il motore di ricerca ha mostrato un controllo anti-robot: risolvilo tu nella finestra di Jarvis"
                   if blocked else f"pagina cambiata? selettore «{cfg.result_selector}» senza risultati")
            return ToolResult(False, f"Nessun risultato per «{args['query']}»: {why}. La pagina resta aperta.",
                              {"blocked": blocked})
        return ToolResult(True, f"Cercato «{args['query']}»: {len(results)} risultati",
                          {"results": results}, verified=True,
                          untrusted_text="\n".join(r["title"] for r in results))

    def preview(self, args: dict[str, Any]) -> str:
        return f"Cercare sul web: «{args.get('query')}»"


class WebOpenTool(Tool):
    name = "web.open"
    capability = "web.open"
    description = "Apre un URL nel browser dedicato; restituisce titolo e inizio del testo (dato non fidato)."
    parameters = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}

    def __init__(self, session: BrowserSession):
        self.s = session

    async def run(self, args: dict[str, Any]) -> ToolResult:
        url = check_url(args["url"], self.s.cfg)
        page = await self.s.page()
        await page.goto(url, wait_until="domcontentloaded")
        # anche dopo redirect il dominio finale deve rispettare le regole
        check_url(page.url, self.s.cfg)
        title = (await page.title()).strip()
        text = (await page.locator("body").inner_text())[: self.s.cfg.max_page_chars]
        return ToolResult(True, f"Aperta pagina «{title or page.url}»",
                          {"url": page.url, "title": title}, verified=bool(title or text),
                          untrusted_text=text)

    def preview(self, args: dict[str, Any]) -> str:
        return f"Aprire nel browser dedicato: {args.get('url')}"

    async def stop(self) -> None:
        await self.s.close()
