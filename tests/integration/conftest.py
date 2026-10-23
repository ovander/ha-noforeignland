"""Fixtures for the functional tests in the Home Assistant harness (TEST §4.10).

noforeignland is always `aioclient_mock`: no real network. Time moves with the harness's
freezer and `async_fire_time_changed`, never with real sleeps.
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from tests.helpers import Boat


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let the harness load custom_components/noforeignland."""


@pytest.fixture
def boat(hass: HomeAssistant, freezer: object) -> Boat:
    b = Boat(hass, freezer)
    b.publish()
    return b
