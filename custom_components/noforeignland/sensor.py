"""Sensors: status, buffered points, last point logged, last send (SPEC §9.10)."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATUSES
from .entity import NflEntity
from .uploader import NflConfigEntry, Uploader


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    uploader = entry.runtime_data
    async_add_entities(
        [
            StatusSensor(uploader),
            BufferedSensor(uploader),
            LastPointSensor(uploader),
            LastSendSensor(uploader),
        ]
    )


class StatusSensor(NflEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(self, uploader: Uploader) -> None:
        super().__init__(uploader, "status")

    @property
    def native_value(self) -> str:
        return self.uploader.status

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"message": self.uploader.rejected}


class BufferedSensor(NflEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, uploader: Uploader) -> None:
        super().__init__(uploader, "buffered_points")

    @property
    def native_value(self) -> int:
        return len(self.uploader.buffer)


class LastPointSensor(NflEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, uploader: Uploader) -> None:
        super().__init__(uploader, "last_point")

    @property
    def native_value(self) -> datetime | None:
        point = self.uploader.last_point
        return None if point is None else datetime.fromtimestamp(point.t, UTC)


class LastSendSensor(NflEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, uploader: Uploader) -> None:
        super().__init__(uploader, "last_send")

    @property
    def native_value(self) -> datetime | None:
        return self.uploader.last_send
