"""Controllo su internet vero: ricerca DuckDuckGo con la config predefinita.
Non fa parte dei test (dipende da un sito esterno); in CI è non bloccante."""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jarvis.config import BrowserConfig  # noqa: E402
from jarvis.tools.browser import BrowserSession, WebOpenTool, WebSearchTool  # noqa: E402


async def main() -> int:
    s = BrowserSession(BrowserConfig(headless=True), Path(tempfile.mkdtemp()))
    try:
        r = await WebSearchTool(s).run({"query": "documentazione python"})
        print(r.summary, r.data.get("results", [])[:3])
        if not r.ok:
            return 1
        o = await WebOpenTool(s).run({"url": r.data["results"][0]["url"]})
        print(o.summary)
        return 0 if o.ok else 1
    finally:
        await s.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
