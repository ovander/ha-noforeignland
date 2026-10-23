"""Diagnostics download (SPEC §9.10): options and counters, both keys redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_BOAT_KEY, CONF_INTEGRATION_KEY
from .uploader import NflConfigEntry

TO_REDACT = {CONF_BOAT_KEY, CONF_INTEGRATION_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NflConfigEntry
) -> dict[str, Any]:
    uploader = entry.runtime_data
    last = uploader.last_point
    return {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "status": uploader.status,
        "sharing": uploader.sharing,
        "buffered_points": len(uploader.buffer),
        "thinned_points": uploader.buffer.thinned,
        "last_point_time": None if last is None else last.t,
        "last_send": None if uploader.last_send is None else uploader.last_send.isoformat(),
        "last_error": uploader.last_error,
        "counters": dict(uploader.counters),
        "version": uploader.version,
    }
