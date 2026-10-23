"""F-NFL-01: config, reconfigure and options flows (TEST §4.10, SPEC §9.10)."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.noforeignland.const import DEFAULTS, DOMAIN
from tests.helpers import BOAT_KEY, INTEGRATION_KEY, SOURCE, Boat, make_entry

USER_INPUT = {"source": SOURCE, "boat_key": BOAT_KEY, "integration_key": INTEGRATION_KEY}


async def test_f_nfl_01_setup_sends_nothing(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garnet"
    assert result["data"] == USER_INPUT
    assert aioclient_mock.call_count == 0  # no test send: it would be public


async def test_f_nfl_01_key_errors(hass: HomeAssistant, boat: Boat) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "boat_key": "  ", "integration_key": "not-a-uuid"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"boat_key": "boat_key", "integration_key": "integration_key"}


async def test_f_nfl_01_one_entry_per_source(hass: HomeAssistant, boat: Boat) -> None:
    make_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_f_nfl_01_proposes_vigies_tracker(hass: HomeAssistant) -> None:
    er.async_get(hass).async_get_or_create(
        "device_tracker",
        "vigie",
        "entry_position",
        translation_key="position",
        suggested_object_id="garnet",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    source = next(k for k in result["data_schema"].schema if k == "source")
    assert source.default() == "device_tracker.garnet"


async def test_reconfigure_keys(hass: HomeAssistant, boat: Boat) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"boat_key": "x", "integration_key": "bad"}
    )
    assert result["errors"] == {"integration_key": "integration_key"}
    new_key = "11111111-2222-3333-4444-555555555555"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"boat_key": "new-boat", "integration_key": new_key}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["boat_key"] == "new-boat" and entry.data["integration_key"] == new_key
    assert entry.data["source"] == SOURCE


async def test_options_defaults_and_change(hass: HomeAssistant, boat: Boat) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults == DEFAULTS
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**DEFAULTS, "send_minutes": 30}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["send_minutes"] == 30
    assert entry.runtime_data.cfg.min_move_m == 80  # reloaded with the options
