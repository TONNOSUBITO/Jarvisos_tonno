import json

import pytest

from jarvis.config import DeviceConfig, load_config
from jarvis.tools.audit import AuditLog, contains_secret, redact
from jarvis.tools.permissions import Decision, PermissionPolicy, action_hash


def test_unknown_capability_denied():
    p = PermissionPolicy(DeviceConfig())
    assert p.decide("email.send") is Decision.DENY
    assert p.decide("shell.exec") is Decision.DENY
    assert p.decide("notes.save") is Decision.CONFIRM
    assert p.decide("web.search") is Decision.ALLOW


def test_confirmation_is_single_use_and_bound():
    p = PermissionPolicy(DeviceConfig())
    h = action_hash("t1", "notes.save", {"title": "a"})
    assert h != action_hash("t1", "notes.save", {"title": "b"})
    assert not p.consume_confirmation(h, "sbagliato")
    assert p.consume_confirmation(h, h)
    assert not p.consume_confirmation(h, h)


def test_config_rejects_shell_and_bad_modes(tmp_path):
    f = tmp_path / "d.toml"
    f.write_text('[permissions]\n"shell.exec" = "auto"\n')
    with pytest.raises(ValueError):
        load_config(f)
    f.write_text('[permissions]\n"web.open" = "sempre"\n')
    with pytest.raises(ValueError):
        load_config(f)
    f.write_text('[device]\ndevice_id = "fisso"\n[apps]\ncalc = ["calc.exe"]\n[limits]\nmax_steps = 3\n')
    c = load_config(f)
    assert c.device_id == "fisso" and c.allowed_apps == {"calc": ["calc.exe"]} and c.limits.max_steps == 3


def test_example_config_is_valid():
    c = load_config("config/device.example.toml")
    assert c.permission("shell.exec") == "deny"


def test_redaction(tmp_path):
    s = "chiave sk-abcdefghijklmnop1234 e password=segreta e Bearer abcdefghijklmnopqrstu"
    r = redact(s)
    assert "sk-abc" not in r and "segreta" not in r and "abcdefghijklmnopqrstu" not in r
    assert contains_secret(s) and not contains_secret("comprare il latte")
    log = AuditLog(tmp_path / "a.jsonl", "dev")
    log.write("x", args={"token": "token=xyz123"})
    rec = json.loads((tmp_path / "a.jsonl").read_text())
    assert "xyz123" not in json.dumps(rec) and rec["device"] == "dev"
