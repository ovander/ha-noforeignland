"""Every user-visible string in English and French (CLAUDE.md; F-NFL-02)."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "noforeignland"


def flatten(data: object, prefix: str = "") -> dict[str, str]:
    if isinstance(data, dict):
        out: dict[str, str] = {}
        for key, value in data.items():
            out.update(flatten(value, f"{prefix}.{key}" if prefix else key))
        return out
    assert isinstance(data, str), prefix
    return {prefix: data}


def load(name: str) -> dict[str, str]:
    return flatten(json.loads((ROOT / name).read_text(encoding="utf-8")))


def test_same_keys_and_placeholders_everywhere():
    strings = load("strings.json")
    for lang in ("en", "fr"):
        other = load(f"translations/{lang}.json")
        assert other.keys() == strings.keys(), lang
        for key, text in other.items():
            assert text.strip(), (lang, key)
            assert re.findall(r"\{(\w+)\}", text) == re.findall(r"\{(\w+)\}", strings[key]), key
    assert load("translations/en.json") == strings
