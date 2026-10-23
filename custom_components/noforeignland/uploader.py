"""Samples the source tracker, keeps the buffer and sends it (SPEC HA-SAIL-SPEC-001 §9.10).

One uploader per config entry. The buffer lives in Home Assistant's storage and is saved
on every change, so a restart or a power cut loses nothing (X-12 §8.5, R-1); a point leaves
it only after noforeignland accepted it, so nothing is sent twice (X-12 §7).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from .const import (
    CONF_BOAT_KEY,
    CONF_CAPACITY,
    CONF_INTEGRATION_KEY,
    CONF_KEEPALIVE_H,
    CONF_MIN_MOVE_M,
    CONF_MIN_SPEED_KN,
    CONF_SAMPLE_S,
    CONF_SEND_MIN,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
    STATUS_OK,
    STATUS_PAUSED,
    STATUS_REJECTED,
    STATUS_WAITING,
)
from .protocol import ATTEMPTS, CHUNK_POINTS, TIMEOUT_S, URL, Outcome, classify, form, headers
from .track import Buffer, Decision, Point, SamplingConfig, decide

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1

type NflConfigEntry = ConfigEntry[Uploader]


def buffer_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


def option(entry: ConfigEntry, key: str) -> float:
    return float(entry.options.get(key, DEFAULTS[key]))


class Uploader:
    """The sampling, the buffer and the sending of one boat."""

    def __init__(self, hass: HomeAssistant, entry: NflConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.source: str = entry.data[CONF_SOURCE]
        self.cfg = SamplingConfig(
            min_move_m=option(entry, CONF_MIN_MOVE_M),
            min_speed_kn=option(entry, CONF_MIN_SPEED_KN),
            keepalive_s=option(entry, CONF_KEEPALIVE_H) * 3600,
        )
        self.buffer = Buffer(int(option(entry, CONF_CAPACITY)))
        self.store = buffer_store(hass, entry.entry_id)
        self.sharing = True
        self.last_point: Point | None = None
        self.last_send: datetime | None = None
        self.rejected: str | None = None
        self.failing = False  # the last send could not reach noforeignland
        self.version = "0"
        self.counters = {
            "logged": 0,
            "sent": 0,
            "outliers": 0,
            "sends_ok": 0,
            "sends_retried": 0,
            "sends_failed": 0,
            "sends_rejected": 0,
        }
        self.last_error: str | None = None
        self._source_ok = True
        self._sending = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._listeners: list[Callable[[], None]] = []

    # Lifecycle

    async def async_start(self) -> None:
        self.version = str((await async_get_integration(self.hass, DOMAIN)).version or "0")
        stored = await self.store.async_load()
        if stored:
            capacity = int(option(self.entry, CONF_CAPACITY))
            self.buffer = Buffer.from_list(capacity, stored.get("points", []))
            last = stored.get("last")
            self.last_point = Point(*last) if last else None
            self.sharing = bool(stored.get("sharing", True))
            sent = stored.get("last_send")
            self.last_send = datetime.fromisoformat(sent) if sent else None
        # A reload is how the owner says the keys were fixed
        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
        self._unsubs = [
            async_track_time_interval(
                self.hass,
                self._async_sample,
                timedelta(seconds=option(self.entry, CONF_SAMPLE_S)),
                name=f"{DOMAIN} sample",
            ),
            async_track_time_interval(
                self.hass,
                self._async_send,
                timedelta(minutes=option(self.entry, CONF_SEND_MIN)),
                name=f"{DOMAIN} send",
            ),
        ]

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        await self._async_save()

    @property
    def issue_id(self) -> str:
        return f"rejected_{self.entry.entry_id}"

    # State for the entities

    @property
    def status(self) -> str:
        if self.rejected is not None:
            return STATUS_REJECTED
        if not self.sharing:
            return STATUS_PAUSED
        if self.failing and len(self.buffer):
            return STATUS_WAITING
        return STATUS_OK

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def async_set_sharing(self, on: bool) -> None:
        """OD-44: off, nothing is logged or sent; the buffer keeps what it has."""
        self.sharing = on
        await self._async_save()
        self._notify()

    # Sampling

    def _now(self) -> float:
        return datetime.now(UTC).timestamp()

    def _position(self) -> tuple[float, float, float | None] | None:
        state = self.hass.states.get(self.source)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        lat = state.attributes.get(ATTR_LATITUDE)
        lon = state.attributes.get(ATTR_LONGITUDE)
        if not isinstance(lat, int | float) or not isinstance(lon, int | float):
            return None
        sog = state.attributes.get("sog")
        return float(lat), float(lon), float(sog) if isinstance(sog, int | float) else None

    async def _async_sample(self, _now: datetime | None = None) -> None:
        if not self.sharing:
            return
        position = self._position()
        if position is None:
            if self._source_ok:  # one line per outage, not one a minute
                _LOGGER.info("No position from %s: nothing logged until it returns", self.source)
                self._source_ok = False
            return
        if not self._source_ok:
            _LOGGER.info("Position from %s is back", self.source)
            self._source_ok = True
        lat, lon, sog = position
        candidate = Point(self._now(), lat, lon)
        decision = decide(self.last_point, candidate, sog, self.cfg)
        if decision == Decision.OUTLIER:
            self.counters["outliers"] += 1
        if not decision.kept:
            return
        self.buffer.add(candidate)
        self.last_point = candidate
        self.counters["logged"] += 1
        await self._async_save()
        self._notify()

    # Sending

    async def _async_send(self, _now: datetime | None = None) -> None:
        if not self.sharing or self.rejected is not None or not len(self.buffer):
            return
        if self._sending.locked():
            return
        async with self._sending:
            session = async_get_clientsession(self.hass)
            for chunk in self.buffer.chunks(CHUNK_POINTS):
                if not await self._async_send_chunk(session, chunk):
                    break
            self._notify()

    async def _async_send_chunk(self, session: aiohttp.ClientSession, chunk: list[Point]) -> bool:
        data = self.entry.data
        body = form(data[CONF_BOAT_KEY], chunk, self.version)
        for attempt in range(1, ATTEMPTS + 1):
            try:
                async with asyncio.timeout(TIMEOUT_S * attempt):
                    response = await session.post(
                        URL, data=body, headers=headers(data[CONF_INTEGRATION_KEY])
                    )
                    async with response:
                        answer = classify(response.status, await response.text())
            except (aiohttp.ClientError, TimeoutError) as err:
                answer = classify(None, None)
                self.last_error = type(err).__name__
            if answer.outcome == Outcome.SENT:
                self.buffer.drop_first(len(chunk))
                self.last_send = datetime.now(UTC)
                self.failing = False
                self.counters["sent"] += len(chunk)
                self.counters["sends_ok"] += 1
                await self._async_save()  # at once: a 2xx is never repeated (X-12 §7)
                return True
            if answer.outcome == Outcome.REJECTED:
                self._reject(answer.message or "rejected")
                return False
            self.last_error = answer.message or self.last_error
            if attempt < ATTEMPTS:
                self.counters["sends_retried"] += 1
        if not self.failing:
            _LOGGER.info("noforeignland not reachable: %d points kept", len(self.buffer))
        self.failing = True
        self.counters["sends_failed"] += 1
        return False

    def _reject(self, message: str) -> None:
        """A key or the request was refused: stop until the entry is reloaded (§9.10)."""
        self.rejected = message
        self.last_error = message
        self.counters["sends_rejected"] += 1
        _LOGGER.warning("noforeignland refused the track: %s; sending stopped", message)
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self.issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="rejected",
            translation_placeholders={"title": self.entry.title, "message": message},
        )

    # Storage

    async def _async_save(self) -> None:
        last = self.last_point
        await self.store.async_save(
            {
                "points": self.buffer.to_list(),
                "last": None if last is None else [last.t, last.lat, last.lon],
                "sharing": self.sharing,
                "last_send": None if self.last_send is None else self.last_send.isoformat(),
            }
        )
