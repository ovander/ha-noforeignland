"""Switch: Sharing on/off (SPEC §9.10, OD-44)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NflEntity
from .uploader import NflConfigEntry, Uploader


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SharingSwitch(entry.runtime_data)])


class SharingSwitch(NflEntity, SwitchEntity):
    """Off: nothing is logged or sent. Its state is kept with the buffer, across restarts."""

    _attr_icon = "mdi:share-variant"

    def __init__(self, uploader: Uploader) -> None:
        super().__init__(uploader, "sharing")

    @property
    def is_on(self) -> bool:
        return self.uploader.sharing

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.uploader.async_set_sharing(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.uploader.async_set_sharing(False)
