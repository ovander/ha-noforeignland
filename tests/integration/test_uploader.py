"""F-NFL-02…09: the uploader in Home Assistant, noforeignland mocked (TEST §4.10, SPEC §9.10)."""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.noforeignland.const import DOMAIN
from custom_components.noforeignland.diagnostics import async_get_config_entry_diagnostics
from custom_components.noforeignland.protocol import URL
from custom_components.noforeignland.uploader import buffer_store
from tests.helpers import BOAT_KEY, INTEGRATION_KEY, Boat, make_entry

SHARING = "switch.noforeignland_garnet_sharing"
STATUS = "sensor.noforeignland_garnet_status"
BUFFERED = "sensor.noforeignland_garnet_buffered_points"
LAST_POINT = "sensor.noforeignland_garnet_last_point_logged"
LAST_SEND = "sensor.noforeignland_garnet_last_send"


async def setup(hass: HomeAssistant, **options: float):
    """Sends every 10 min unless told otherwise, to keep the scenarios short (default 60)."""
    entry = make_entry(**{"send_minutes": 10, **options})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def sent_tracks(aioclient_mock: AiohttpClientMocker) -> list[list[list[float]]]:
    """The `track` of every request made, in order."""
    tracks = []
    for _method, _url, data, _headers in aioclient_mock.mock_calls:
        body = parse_qs(data) if isinstance(data, str) else {k: [v] for k, v in data.items()}
        tracks.append(json.loads(body["track"][0]))
    return tracks


def state(hass: HomeAssistant, entity_id: str) -> str:
    s = hass.states.get(entity_id)
    assert s is not None, entity_id
    return s.state


async def test_f_nfl_02_entities(hass: HomeAssistant, boat: Boat) -> None:
    entry = await setup(hass)
    assert state(hass, SHARING) == "on"
    assert state(hass, STATUS) == "ok"
    assert state(hass, BUFFERED) == "0"
    assert state(hass, LAST_POINT) == "unknown"
    assert state(hass, LAST_SEND) == "unknown"
    registry = er.async_get(hass)
    ids = {e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert ids == {SHARING, STATUS, BUFFERED, LAST_POINT, LAST_SEND}
    assert hass.states.get(STATUS).attributes["options"] == ["ok", "waiting", "rejected", "paused"]


async def test_f_nfl_03_sends_every_ten_minutes(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, json={"status": "ok"})
    await setup(hass)
    await boat.run(30)
    # A point a minute (6 kn: 185 m a minute); a send every 10 min with what is new. The
    # send at minute 30 runs before that minute's sample, which waits for the next send.
    tracks = sent_tracks(aioclient_mock)
    assert [len(t) for t in tracks] == [9, 10, 10]
    times = [p[0] for t in tracks for p in t]
    assert times == sorted(times) and len(set(times)) == 29
    _method, url, data, headers = aioclient_mock.mock_calls[0]
    assert str(url) == URL
    assert headers["X-NFL-API-Key"] == INTEGRATION_KEY
    assert headers["Accept-Encoding"] == "identity"
    assert data["boatApiKey"] == BOAT_KEY and data["timestamp"] == str(int(tracks[0][-1][0]))
    assert data["pluginVersion"].startswith("ha-noforeignland/")
    assert state(hass, BUFFERED) == "1"
    assert state(hass, STATUS) == "ok"
    assert state(hass, LAST_SEND) != "unknown"
    assert state(hass, LAST_POINT) != "unknown"


async def test_f_nfl_03_defaults_send_hourly_and_six_hourly_point(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    """OD-43 as amended by the owner: a point a minute, sent once an hour; still, every 6 h."""
    aioclient_mock.post(URL, json={"status": "ok"})
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await boat.run(120)
    assert [len(t) for t in sent_tracks(aioclient_mock)] == [59, 60]
    aioclient_mock.clear_requests()
    aioclient_mock.post(URL, json={"status": "ok"})
    boat.sog = 0.0
    await boat.run(6 * 60)
    # The point still waiting from minute 120, then the stationary one at 6 h
    times = [p[0] for t in sent_tracks(aioclient_mock) for p in t]
    assert len(times) == 1
    await boat.run(60)
    assert len([p for t in sent_tracks(aioclient_mock) for p in t]) == 2


async def test_f_nfl_03_still_boat_logs_nothing(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, json={"status": "ok"})
    await setup(hass)
    boat.sog = 0.0
    await boat.run(30)
    # Only the first point; nothing more while stationary (keepalive after 24 h)
    assert [len(t) for t in sent_tracks(aioclient_mock)] == [1]


async def test_f_nfl_04_outage_then_recovery(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    """R-1: two hours offline while moving; everything sent once back, in order, once."""
    aioclient_mock.post(URL, exc=aiohttp.ClientConnectionError())
    await setup(hass, buffer_points=10_000)
    await boat.run(120)
    assert state(hass, STATUS) == "waiting"
    assert state(hass, BUFFERED) == "120"
    failed_calls = aioclient_mock.call_count
    assert failed_calls == 12 * 3  # 12 sends, 3 attempts each
    aioclient_mock.clear_requests()
    aioclient_mock.post(URL, json={"status": "ok"})
    await boat.run(10)
    tracks = sent_tracks(aioclient_mock)
    times = [p[0] for t in tracks for p in t]
    assert len(times) == 129 and times == sorted(times) and len(set(times)) == 129
    assert state(hass, BUFFERED) == "1"  # minute 130, sampled after that minute's send
    assert state(hass, STATUS) == "ok"


async def test_f_nfl_04_chunks_of_one_thousand(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, status=503)
    await setup(hass, send_minutes=1440)
    await boat.run(1100)
    assert aioclient_mock.call_count == 0  # no send in this window: daily schedule
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    aioclient_mock.clear_requests()
    aioclient_mock.post(URL, json={"status": "ok"})
    await entry.runtime_data._async_send()
    await hass.async_block_till_done()
    assert [len(t) for t in sent_tracks(aioclient_mock)] == [1000, 100]


async def test_f_nfl_04_retry_on_5xx_then_ok(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, status=503)
    await setup(hass)
    await boat.run(10)
    assert aioclient_mock.call_count == 3
    assert state(hass, STATUS) == "waiting"
    assert state(hass, BUFFERED) == "10"


async def test_f_nfl_05_restart_restores_the_buffer(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker, hass_storage: dict
) -> None:
    entry = make_entry(send_minutes=10)
    rows = [[1_790_000_000.0 + 60 * i, 43.5 + i / 1000, 7.25] for i in range(50)]
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {"points": rows, "last": rows[-1], "sharing": True, "last_send": None},
    }
    entry.add_to_hass(hass)
    aioclient_mock.post(URL, json={"status": "ok"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, BUFFERED) == "50"
    await boat.run(10)
    tracks = sent_tracks(aioclient_mock)
    assert tracks[0][:50] == [[int(r[0] * 1000), r[1], r[2]] for r in rows]


async def test_f_nfl_05_buffer_saved_at_each_point(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker, hass_storage: dict
) -> None:
    aioclient_mock.post(URL, exc=aiohttp.ClientConnectionError())
    entry = await setup(hass)
    await boat.run(3)
    await hass.async_block_till_done()
    store = buffer_store(hass, entry.entry_id)
    data = await store.async_load()
    assert data is not None and len(data["points"]) == 3


async def test_f_nfl_06_rejected(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(
        URL, status=401, json={"status": "error", "message": "Invalid boat API key"}
    )
    entry = await setup(hass)
    await boat.run(10)
    assert aioclient_mock.call_count == 1  # never retried
    status = hass.states.get(STATUS)
    assert status.state == "rejected"
    assert status.attributes["message"] == "Invalid boat API key"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"rejected_{entry.entry_id}")
    assert issue is not None and issue.translation_placeholders["message"] == "Invalid boat API key"
    await boat.run(30)
    assert aioclient_mock.call_count == 1  # stopped until reloaded
    assert state(hass, BUFFERED) == "40"  # still logged and kept
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["last_error"] == "Invalid boat API key"
    # A reload (new keys) clears the issue and sends again
    aioclient_mock.clear_requests()
    aioclient_mock.post(URL, json={"status": "ok"})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"rejected_{entry.entry_id}") is None
    await boat.run(10)
    assert sum(len(t) for t in sent_tracks(aioclient_mock)) == 49  # the 50th after its send
    assert state(hass, STATUS) == "ok"


async def test_f_nfl_06_error_body_on_200(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, json={"status": "error", "message": "Boat not found"})
    await setup(hass)
    await boat.run(10)
    assert state(hass, STATUS) == "rejected"
    assert state(hass, BUFFERED) == "10"


async def test_f_nfl_07_sharing_off(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, exc=aiohttp.ClientConnectionError())
    entry = await setup(hass)
    await boat.run(5)  # 5 points buffered, the send at 10 min not reached
    assert state(hass, BUFFERED) == "5"
    await hass.services.async_call("switch", "turn_off", {"entity_id": SHARING}, blocking=True)
    assert state(hass, STATUS) == "paused"
    calls = aioclient_mock.call_count
    await boat.run(20)
    assert state(hass, BUFFERED) == "5"  # nothing logged
    assert aioclient_mock.call_count == calls  # nothing sent
    # Restored after a restart (reload)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, SHARING) == "off"
    aioclient_mock.clear_requests()
    aioclient_mock.post(URL, json={"status": "ok"})
    await hass.services.async_call("switch", "turn_on", {"entity_id": SHARING}, blocking=True)
    await boat.run(10)
    times = [p[0] for t in sent_tracks(aioclient_mock) for p in t]
    assert len(times) == 14 and times == sorted(times)  # 5 kept while paused, 9 new


async def test_f_nfl_08_diagnostics(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, json={"status": "ok"})
    entry = await setup(hass, send_minutes=5)
    await boat.run(10)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(diagnostics)
    assert BOAT_KEY not in text and INTEGRATION_KEY not in text
    assert diagnostics["data"]["boat_key"] == "**REDACTED**"
    assert diagnostics["data"]["integration_key"] == "**REDACTED**"
    assert diagnostics["options"] == {"send_minutes": 5}
    assert diagnostics["counters"]["logged"] == 10
    assert (
        diagnostics["counters"]["sent"] == 9
    )  # sends at 5 and 10 min, before that minute's sample
    assert diagnostics["counters"]["sends_ok"] == 2
    assert diagnostics["status"] == "ok"


async def test_f_nfl_09_source_unavailable(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker, freezer, caplog
) -> None:
    aioclient_mock.post(URL, json={"status": "ok"})
    await setup(hass)
    for value, attributes in (("unavailable", {}), ("not_home", {"gps_accuracy": 5})):
        hass.states.async_set("device_tracker.garnet", value, attributes)
        for _ in range(15):
            freezer.tick(timedelta(minutes=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
    assert aioclient_mock.call_count == 0
    assert state(hass, BUFFERED) == "0"
    assert caplog.text.count("No position from device_tracker.garnet") == 1  # once per outage
    boat.publish()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, BUFFERED) == "1"
    assert "Position from device_tracker.garnet is back" in caplog.text


async def test_f_nfl_09_outlier_counted(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(URL, json={"status": "ok"})
    entry = await setup(hass)
    await boat.run(1)
    boat.lat += 1.0  # 111 km in a minute
    await boat.run(1)
    assert entry.runtime_data.counters["outliers"] == 1


async def test_unload_and_remove(hass: HomeAssistant, boat: Boat, hass_storage: dict) -> None:
    entry = await setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}" in hass_storage
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}" not in hass_storage


async def test_f_nfl_built_in_key_is_sent(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    """OD-45: no override, the built-in key goes in the header; diagnostics say which."""
    built_in = "11111111-2222-3333-4444-555555555555"
    aioclient_mock.post(URL, json={"status": "ok"})
    with patch("custom_components.noforeignland.protocol.BUILTIN_INTEGRATION_KEY", built_in):
        entry = await setup(hass)
        hass.config_entries.async_update_entry(entry, data={**entry.data, "integration_key": ""})
        await boat.run(10)
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert aioclient_mock.mock_calls[0][3]["X-NFL-API-Key"] == built_in
    assert diagnostics["integration_key_source"] == "built-in"
    assert built_in not in json.dumps(diagnostics)


async def test_f_nfl_no_key_at_all_is_a_rejection(
    hass: HomeAssistant, boat: Boat, aioclient_mock: AiohttpClientMocker
) -> None:
    with patch("custom_components.noforeignland.protocol.BUILTIN_INTEGRATION_KEY", ""):
        entry = await setup(hass)
        hass.config_entries.async_update_entry(entry, data={**entry.data, "integration_key": ""})
        await boat.run(10)
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert aioclient_mock.call_count == 0
    assert state(hass, STATUS) == "rejected"
    assert diagnostics["integration_key_source"] == "none"
