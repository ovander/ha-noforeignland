"""noforeignland tracking — share a boat's track on noforeignland (SPEC HA-SAIL-SPEC-001 §9.10).

Home Assistant is imported inside the entry points or for type checking only: importing
any sub-module runs this file first, and the pure modules (`track.py`, `protocol.py`) must
not pull in Home Assistant (NFR-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant

    from .uploader import NflConfigEntry

PLATFORMS: list[Platform | str] = ["sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: NflConfigEntry) -> bool:
    """Restore the buffer, start sampling and sending."""
    from .uploader import Uploader

    uploader = Uploader(hass, entry)
    await uploader.async_start()
    entry.runtime_data = uploader
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NflConfigEntry) -> bool:
    unloaded: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: NflConfigEntry) -> None:
    """Entry deleted: forget its buffer."""
    from .uploader import buffer_store

    await buffer_store(hass, entry.entry_id).async_remove()


async def _reload(hass: HomeAssistant, entry: NflConfigEntry) -> None:
    """Options or keys changed: start again with them (a rejection is cleared)."""
    await hass.config_entries.async_reload(entry.entry_id)
