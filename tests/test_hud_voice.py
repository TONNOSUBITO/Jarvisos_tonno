"""HUD: la risposta vocale parte dalla prima frase (API finte, Chromium reale)."""

import json
from pathlib import Path

import numpy as np
from playwright.async_api import async_playwright

from jarvis.audio.base import float32_to_wav
from jarvis.core.state import Task

HTML = (Path(__file__).parents[1] / "jarvis" / "web" / "index.html").read_text(encoding="utf-8")
WAV = float32_to_wav(np.zeros(1600, np.float32), 16000)  # 0,1 s di silenzio
RESULT = "Ciao. Oggi a Roma c'è il sole e fanno ventidue gradi. Domani pioverà per tutto il giorno."
TASK = {**Task(command="meteo").to_dict(), "status": "completato", "result": RESULT, "report": RESULT,
        "route": "regole locali"}


async def run_page(wav, after_first=None):
    """Invia un comando dalla UI; restituisce i testi chiesti a /api/tts ed eventuali errori JS."""
    tts_texts = []

    async def handle(route):
        url, req = route.request.url, route.request
        if url.endswith("/api/tts"):
            tts_texts.append(json.loads(req.post_data)["text"])
            return await route.fulfill(status=200, body=wav, content_type="audio/wav")
        if url.endswith("/api/command"):
            return await route.fulfill(json=TASK)
        if "/api/state" in url:
            return await route.fulfill(json={"tasks": [TASK]})
        if "/api/info" in url:
            return await route.fulfill(json={"speak_replies": True, "tts": "kokoro", "stt": "none", "model": "-",
                                             "provider": "", "spesa_eur": 0, "budget_eur": 0, "ram_gb": None})
        if "/api/vault" in url:
            return await route.fulfill(json={"notes": []})
        if "/api/memory" in url:
            return await route.fulfill(json={"facts": []})
        if url.rstrip("/").endswith("jarvis.test"):
            return await route.fulfill(body=HTML, content_type="text/html")
        return await route.fulfill(json={})

    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        pg = await b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(e))
        await pg.route("http://jarvis.test/**", handle)
        await pg.goto("http://jarvis.test/")
        await pg.wait_for_timeout(300)
        await pg.fill("#cmd", "meteo")
        await pg.press("#cmd", "Enter")
        for _ in range(100):
            if tts_texts and after_first:
                await after_first(pg)
                after_first = None
            if len(tts_texts) >= 3:
                break
            await pg.wait_for_timeout(50)
        chip = await pg.inner_text("#route")
        await b.close()
    return tts_texts, errors + ([] if chip == "capito da: regole locali" else [f"chip: {chip!r}"])


async def test_speech_starts_with_first_sentence_and_queues_the_rest():
    tts_texts, errors = await run_page(WAV)
    assert not errors
    assert tts_texts[0] == "Ciao."                      # parte subito con una frase corta
    assert " ".join(tts_texts) == RESULT                # poi il resto, in ordine, senza perdite
    assert len(tts_texts) == 3


async def test_stop_cancels_the_queued_sentences():
    long_wav = float32_to_wav(np.zeros(32000, np.float32), 16000)  # 2 s: c'è tempo per premere Stop

    async def stop(pg):
        await pg.wait_for_timeout(300)
        await pg.click("#stopAll")

    tts_texts, errors = await run_page(long_wav, stop)
    assert not errors and tts_texts[0] == "Ciao." and len(tts_texts) <= 2  # la terza frase non parte mai
