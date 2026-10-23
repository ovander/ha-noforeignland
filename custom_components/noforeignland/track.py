"""Which positions to log, and the buffer that keeps them until sent (SPEC §9.10; X-12 §8).

Pure Python, no Home Assistant import (SPEC NFR-02, CLAUDE.md): the HA side feeds it
positions and times and stores what `Buffer.to_list` returns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

EARTH_RADIUS_M = 6_371_000.0
M_PER_NM = 1852.0


@dataclass(frozen=True)
class Point:
    """A logged position: epoch seconds (UTC), decimal degrees N/E positive."""

    t: float
    lat: float
    lon: float


@dataclass(frozen=True)
class SamplingConfig:
    """X-12 §8.1 defaults, but a stationary point every 6 h, not 24 h (OD-43, amended)."""

    min_move_m: float = 80.0
    min_speed_kn: float = 1.5
    max_velocity_ms: float = 50.0
    keepalive_s: float = 6 * 3600.0


class Decision(StrEnum):
    KEEP = "keep"
    KEEPALIVE = "keepalive"
    INVALID = "invalid"
    STALE = "stale"
    OUTLIER = "outlier"
    TOO_CLOSE = "too_close"
    TOO_SLOW = "too_slow"

    @property
    def kept(self) -> bool:
        return self in (Decision.KEEP, Decision.KEEPALIVE)


def valid(lat: float, lon: float) -> bool:
    return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def distance_m(a: Point, b: Point) -> float:
    """Equirectangular distance, as the reference client (X-12 §8.1); exact enough below 20 km."""
    mean_lat = math.radians((a.lat + b.lat) / 2)
    dx = math.radians(b.lon - a.lon) * math.cos(mean_lat)
    dy = math.radians(b.lat - a.lat)
    return EARTH_RADIUS_M * math.hypot(dx, dy)


def decide(
    last: Point | None, candidate: Point, sog_kn: float | None, cfg: SamplingConfig
) -> Decision:
    """Keep `candidate` after `last` (the last logged point)?

    `sog_kn` is the source's speed over ground when it has one; otherwise the speed is the
    distance from the last point over the time between them.
    """
    if not valid(candidate.lat, candidate.lon):
        return Decision.INVALID
    if last is None:
        return Decision.KEEP
    dt = candidate.t - last.t
    if dt <= 0:
        return Decision.STALE
    moved = distance_m(last, candidate)
    if moved / dt > cfg.max_velocity_ms:
        return Decision.OUTLIER
    if dt >= cfg.keepalive_s:
        return Decision.KEEPALIVE
    if moved < cfg.min_move_m:
        return Decision.TOO_CLOSE
    speed = sog_kn if sog_kn is not None else moved / dt * 3600 / M_PER_NM
    if speed < cfg.min_speed_kn:
        return Decision.TOO_SLOW
    return Decision.KEEP


class Buffer:
    """Points not sent yet, oldest first, bounded by thinning (X-12 §8.5, R-1)."""

    def __init__(self, capacity: int, points: list[Point] | None = None) -> None:
        if capacity < 2:
            raise ValueError("capacity must be at least 2")
        self.capacity = capacity
        self.points: list[Point] = list(points or [])
        self.thinned = 0  # points dropped by thinning, for diagnostics

    def __len__(self) -> int:
        return len(self.points)

    def add(self, point: Point) -> None:
        """Append; when full, drop every second point of the oldest half first."""
        while len(self.points) >= self.capacity:
            half = len(self.points) // 2
            kept = self.points[:half:2]
            self.thinned += half - len(kept)
            self.points = kept + self.points[half:]
        self.points.append(point)

    def chunks(self, size: int) -> list[list[Point]]:
        """The buffer in requests of at most `size` points, oldest first (X-12 OD-2)."""
        return [self.points[i : i + size] for i in range(0, len(self.points), size)]

    def drop_first(self, count: int) -> None:
        """Forget the `count` oldest points: they were accepted (X-12 §7)."""
        del self.points[:count]

    def to_list(self) -> list[list[float]]:
        return [[p.t, p.lat, p.lon] for p in self.points]

    @classmethod
    def from_list(cls, capacity: int, rows: list[list[float]]) -> Buffer:
        buffer = cls(capacity, [Point(float(t), float(lat), float(lon)) for t, lat, lon in rows])
        # A smaller capacity set in the options thins what was stored
        while len(buffer.points) > capacity:
            half = len(buffer.points) // 2
            kept = buffer.points[:half:2]
            buffer.thinned += half - len(kept)
            buffer.points = kept + buffer.points[half:]
        return buffer
