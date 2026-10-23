"""Base entity: one device per boat, pushed by the uploader (SPEC §9.10)."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .uploader import Uploader


class NflEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, uploader: Uploader, key: str) -> None:
        self.uploader = uploader
        entry = uploader.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"noforeignland {entry.title}",
            manufacturer="noforeignland",
            model="Track uploader",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.uploader.async_add_listener(self.async_write_ha_state))
