"""Shared test helpers: the source tracker and the config entry (TEST §4.10)."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.noforeignland.const import (
    CONF_BOAT_KEY,
    CONF_INTEGRATION_KEY,
    CONF_SOURCE,
    DOMAIN,
)

SOURCE = "device_tracker.garnet"
BOAT_KEY = "boat-secret-key"
INTEGRATION_KEY = "0f8fad5b-d9cb-469f-a165-70867728950e"
START_LAT, START_LON = 43.5, 7.25
DEG_PER_NM = 1 / 60


def make_entry(**options: float) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Garnet",
        unique_id=SOURCE,
        data={CONF_SOURCE: SOURCE, CONF_BOAT_KEY: BOAT_KEY, CONF_INTEGRATION_KEY: INTEGRATION_KEY},
        options=options,
    )


class Boat:
    """The source tracker: a boat motoring north at `sog` knots from 43.5 N 7.25 E."""

    def __init__(self, hass: HomeAssistant, freezer: object, sog: float = 6.0) -> None:
        self.hass = hass
        self.freezer = freezer
        self.sog = sog
        self.lat = START_LAT

    def publish(self) -> None:
        self.hass.states.async_set(
            SOURCE,
            "not_home",
            {
                "latitude": self.lat,
                "longitude": START_LON,
                "sog": self.sog,
                "friendly_name": "Garnet",
            },
        )

    async def run(self, minutes: int) -> None:
        """Move one minute at a time, letting Home Assistant's timers fire."""
        for _ in range(minutes):
            self.lat += self.sog / 60 * DEG_PER_NM
            self.publish()
            self.freezer.tick(timedelta(minutes=1))  # type: ignore[attr-defined]  # freezer fixture
            async_fire_time_changed(self.hass)
            await self.hass.async_block_till_done()
