"""U-NFL-06, 07, 09: request, answers, key format (TEST HA-SAIL-TEST-001 §3.11; X-12 §3–§6)."""

import json
import subprocess
import sys

import pytest

from custom_components.noforeignland.protocol import (
    URL,
    Answer,
    Outcome,
    classify,
    form,
    headers,
    integration_key,
    is_integration_key,
)
from custom_components.noforeignland.track import Point

KEY = "0f8fad5b-d9cb-469f-a165-70867728950e"


def test_u_nfl_06_request():
    points = [Point(1_761_037_200.0, 43.5012, 3.9241), Point(1_761_037_260.0, 43.5021, 3.9268)]
    body = form(" boat-key ", points, "0.1.0")
    # X-12 §5.2's example
    assert body == {
        "boatApiKey": "boat-key",
        "timestamp": "1761037260000",
        "track": "[[1761037200000,43.5012,3.9241],[1761037260000,43.5021,3.9268]]",
        "pluginVersion": "ha-noforeignland/0.1.0",
    }
    assert json.loads(body["track"])[0] == [1761037200000, 43.5012, 3.9241]
    assert headers(KEY) == {"X-NFL-API-Key": KEY, "Accept-Encoding": "identity"}
    assert URL == "https://www.noforeignland.com/home/api/v1/boat/tracking/track"
    with pytest.raises(ValueError):
        form("boat-key", [], "0.1.0")


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (200, '{"status":"ok"}', Answer(Outcome.SENT)),
        (200, "<html>truncated", Answer(Outcome.SENT)),  # stored anyway: never resend
        (200, "", Answer(Outcome.SENT)),
        (
            200,
            '{"status":"error","message":"Invalid boat API key"}',
            Answer(Outcome.REJECTED, "Invalid boat API key"),
        ),
        (
            401,
            '{"status":"error","message":"Unauthorized"}',
            Answer(Outcome.REJECTED, "Unauthorized"),
        ),
        (403, "Forbidden", Answer(Outcome.REJECTED, "HTTP 403")),
        (302, None, Answer(Outcome.REJECTED, "HTTP 302")),
        (503, "busy", Answer(Outcome.RETRY, "HTTP 503")),
        (None, None, Answer(Outcome.RETRY)),  # network error or timeout
        (200, '["status","error"]', Answer(Outcome.SENT)),
    ],
)
def test_u_nfl_07_answers(status, body, expected):
    assert classify(status, body) == expected


def test_u_nfl_09_built_in_key_and_override(monkeypatch):
    """OD-45: the owner's override, else the built-in key, else none."""
    monkeypatch.setattr("custom_components.noforeignland.protocol.BUILTIN_INTEGRATION_KEY", "")
    assert integration_key(None) is None
    assert integration_key("  ") is None
    assert integration_key(f" {KEY} ") == KEY
    built_in = "11111111-2222-3333-4444-555555555555"
    monkeypatch.setattr(
        "custom_components.noforeignland.protocol.BUILTIN_INTEGRATION_KEY", built_in
    )
    assert integration_key(None) == built_in
    assert integration_key("") == built_in
    assert integration_key(KEY) == KEY


def test_u_nfl_09_integration_key_format():
    assert is_integration_key(KEY)
    assert is_integration_key(f" {KEY.upper()} ")
    assert not is_integration_key("")
    assert not is_integration_key("my-key")
    assert not is_integration_key(KEY[:-1])


@pytest.mark.parametrize(
    "module",
    ["custom_components.noforeignland.track", "custom_components.noforeignland.protocol"],
)
def test_pure_module_does_not_import_homeassistant(module):
    code = (
        f"import sys, {module}\n"
        "bad = [m for m in sys.modules if m.split('.')[0] == 'homeassistant']\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
