import io
import os
import wave
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from jarvis.app import build_orchestrator
from jarvis.audio.base import AudioError, MockSTT, MockTTS, float32_to_wav, wav_to_float32
from jarvis.audio.tts import FISH_TTS_URL, FishAudioTTS
from jarvis.core.state import Status
from jarvis.server import create_app

H = {"X-Jarvis-Token": "tok"}


def wav(seconds=1.0, rate=16000, channels=1):
    n = int(seconds * rate)
    data = (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, n)) * 0.3 * 32767).astype("<i2")
    if channels == 2:
        data = np.repeat(data, 2)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data.tobytes())
    return buf.getvalue()


def test_wav_decoding_and_resampling():
    a = wav_to_float32(wav(1.0, 48000, 2))
    assert a.dtype == np.float32 and abs(len(a) - 16000) <= 1 and np.abs(a).max() <= 1.0
    with pytest.raises(AudioError):
        wav_to_float32(wav(2.0), max_seconds=1.0)
    with pytest.raises(AudioError):
        wav_to_float32(b"non audio")
    assert len(wav_to_float32(float32_to_wav(a, 16000))) == len(a)


async def test_voice_task_transcribes_then_executes(cfg, apps):
    stt = MockSTT("apri calcolatrice")
    orch = build_orchestrator(cfg, apps, stt=stt)
    t = orch.submit(audio=np.zeros(16000, dtype=np.float32))
    assert t.status is Status.TRANSCRIBING and t.source == "voce"
    await orch.wait(t.id)
    assert t.status is Status.DONE and t.command == "apri calcolatrice" and apps.launched == [["calc.exe"]]
    assert "stt_ms" in t.metrics and t.metrics["audio_s"] == 1.0


async def test_empty_transcript(cfg, apps):
    orch = build_orchestrator(cfg, apps, stt=MockSTT("  "))
    t = await orch.wait(orch.submit(audio=np.zeros(8000, dtype=np.float32)).id)
    assert t.status is Status.ERROR and "Non ho sentito" in t.result


def client(cfg, apps, **kw):
    orch = build_orchestrator(cfg, apps, **kw)
    return TestClient(create_app(cfg, orch, token="tok", allowed_hosts=["testserver"])), orch


def test_voice_endpoint(cfg, apps):
    c, _ = client(cfg, apps, stt=MockSTT("apri calcolatrice"))
    assert c is not None
    with c:
        assert c.post("/api/voice", content=wav(), headers=H).json()["source"] == "voce"
        assert c.post("/api/voice", content=b"xx", headers=H).status_code == 400
        assert c.post("/api/voice", content=wav(), headers={"X-Jarvis-Token": "no"}).status_code == 401


def test_tts_endpoint_local_and_browser(cfg, apps):
    tts = MockTTS()
    c, _ = client(cfg, apps, tts=tts)
    with c:
        r = c.post("/api/tts", json={"text": "ciao"}, headers=H)
        assert r.status_code == 200 and r.content[:4] == b"RIFF" and tts.spoken == ["ciao"]
    cfg.voice.tts_engine = "browser"
    c, _ = client(cfg, apps)
    with c:
        assert c.post("/api/tts", json={"text": "ciao"}, headers=H).status_code == 204
        info = c.get("/api/info", headers=H).json()
        assert info["tts"] == "browser" and info["model"] == "disattivato"


def test_cloud_tts_needs_permission(cfg, apps):
    fish = FishAudioTTS(api_key="k", transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"RIFF")))
    c, _ = client(cfg, apps, tts=fish)
    with c:
        assert c.post("/api/tts", json={"text": "ciao"}, headers=H).status_code == 403
    cfg.permissions["tts.cloud"] = "auto"
    c, _ = client(cfg, apps, tts=fish)
    with c:
        assert c.post("/api/tts", json={"text": "ciao"}, headers=H).status_code == 200
        assert c.get("/api/info", headers=H).json()["tts_local"] is False


async def test_fish_request_format():
    seen = {}

    def handler(req: httpx.Request):
        seen.update(url=str(req.url), auth=req.headers["authorization"], model=req.headers["model"], body=req.content)
        return httpx.Response(200, content=b"RIFFxxxx")

    out = await FishAudioTTS("s2.1-pro-free", "voce1", api_key="k", transport=httpx.MockTransport(handler)).synthesize("ciao")
    assert out.startswith(b"RIFF") and seen["url"] == FISH_TTS_URL
    assert seen["auth"] == "Bearer k" and seen["model"] == "s2.1-pro-free"
    assert b'"reference_id":"voce1"' in seen["body"].replace(b" ", b"") and b'"format":"wav"' in seen["body"].replace(b" ", b"")


MODELS = Path("data/models")
# In CI dopo l'installer: i modelli DEVONO esserci, niente skip silenziosi.
REQUIRE = os.environ.get("JARVIS_REQUIRE_VOICE_MODELS") == "1"


@pytest.mark.skipif(not REQUIRE and not (MODELS / "kokoro-v1.0.onnx").exists(), reason="modelli voce non scaricati")
async def test_real_roundtrip_kokoro_to_whisper(tmp_path):
    """Integrazione reale (locale): Kokoro dice una frase, faster-whisper la trascrive."""
    if not REQUIRE:
        pytest.importorskip("kokoro_onnx"); pytest.importorskip("faster_whisper")
    from jarvis.audio.stt import FasterWhisperSTT
    from jarvis.audio.tts import KokoroTTS
    from jarvis.routing.router import RuleRouter

    audio = await KokoroTTS(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin")).synthesize(
        "Apri la calcolatrice.")
    text = FasterWhisperSTT("base", MODELS / "whisper").transcribe(wav_to_float32(audio))
    assert RuleRouter().route(text).kind == "open_app", text
