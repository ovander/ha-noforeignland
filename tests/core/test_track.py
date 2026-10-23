"""U-NFL-01…05, 08: sampling filters, outliers, keepalive, buffer (TEST HA-SAIL-TEST-001 §3.11).

Positions by hand: at 43.5° N one metre north is 1 / 111 195 ° of latitude
(earth radius 6 371 km, as `distance_m`).
"""

import math

import pytest

from custom_components.noforeignland.track import (
    Buffer,
    Decision,
    Point,
    SamplingConfig,
    decide,
    distance_m,
)

CFG = SamplingConfig()
DEG_PER_M = 180 / (math.pi * 6_371_000)  # degrees of latitude per metre
T0 = 1_790_000_000.0
START = Point(T0, 43.5, 7.25)


def north(metres: float, seconds: float) -> Point:
    return Point(T0 + seconds, 43.5 + metres * DEG_PER_M, 7.25)


def test_distance_by_hand():
    assert distance_m(START, north(1000, 60)) == pytest.approx(1000, abs=1e-6)


def test_u_nfl_01_sampling_filters():
    assert decide(START, north(79, 60), 3.0, CFG) == Decision.TOO_CLOSE
    assert decide(START, north(81, 60), 3.0, CFG) == Decision.KEEP
    assert decide(START, north(81, 60), 1.4, CFG) == Decision.TOO_SLOW
    # No SOG: 200 m in 60 s is 3.33 m/s = 6.48 kn
    assert decide(START, north(200, 60), None, CFG) == Decision.KEEP
    # No SOG, 81 m in 120 s: 0.675 m/s = 1.31 kn, too slow
    assert decide(START, north(81, 120), None, CFG) == Decision.TOO_SLOW
    assert decide(START, Point(T0 + 60, 91.0, 7.25), 3.0, CFG) == Decision.INVALID
    assert decide(START, Point(T0 + 60, 43.5, 181.0), 3.0, CFG) == Decision.INVALID
    assert decide(START, Point(T0 + 60, math.nan, 7.25), 3.0, CFG) == Decision.INVALID
    # The first point is always kept; a point at the same time never is
    assert decide(None, START, None, CFG) == Decision.KEEP
    assert decide(START, Point(T0, 43.6, 7.25), 3.0, CFG) == Decision.STALE


def test_u_nfl_02_outlier():
    # 4 km in 60 s: 66.7 m/s, above 50 m/s
    assert decide(START, north(4000, 60), 6.0, CFG) == Decision.OUTLIER
    # 2.9 km in 60 s: 48 m/s, kept
    assert decide(START, north(2900, 60), 94.0, CFG) == Decision.KEEP


def test_u_nfl_03_keepalive():
    still = Point(T0 + 6 * 3600 - 60, 43.5, 7.25)
    assert decide(START, still, 0.0, CFG) == Decision.TOO_CLOSE
    assert decide(START, Point(T0 + 6 * 3600, 43.5, 7.25), 0.0, CFG) == Decision.KEEPALIVE
    assert Decision.KEEPALIVE.kept and Decision.KEEP.kept and not Decision.TOO_SLOW.kept


def test_u_nfl_04_buffer_thinning():
    buffer = Buffer(10, [Point(T0 + i, 43.5, 7.25) for i in range(10)])
    buffer.add(Point(T0 + 10, 43.5, 7.25))
    # Oldest half 0…4: 0, 2, 4 kept; 5…9 untouched; then the new point
    assert [p.t - T0 for p in buffer.points] == [0, 2, 4, 5, 6, 7, 8, 9, 10]
    assert buffer.thinned == 2
    with pytest.raises(ValueError):
        Buffer(1)


def test_u_nfl_04_long_passage_keeps_its_shape():
    buffer = Buffer(100)
    for i in range(1000):
        buffer.add(Point(T0 + i, 43.5, 7.25))
    times = [p.t - T0 for p in buffer.points]
    assert len(buffer) <= 100
    assert times == sorted(times)
    assert times[0] == 0 and times[-1] == 999  # the start and the end of the passage
    assert len(buffer) + buffer.thinned == 1000


def test_u_nfl_05_chunks():
    buffer = Buffer(10_000, [Point(T0 + i, 43.5, 7.25) for i in range(2500)])
    chunks = buffer.chunks(1000)
    assert [len(c) for c in chunks] == [1000, 1000, 500]
    assert chunks[0][0].t == T0 and chunks[2][-1].t == T0 + 2499
    buffer.drop_first(1000)
    assert len(buffer) == 1500 and buffer.points[0].t == T0 + 1000


def test_u_nfl_08_round_trip_after_partial_send():
    buffer = Buffer(100, [Point(T0 + i, 43.5 + i / 1000, 7.25) for i in range(5)])
    buffer.drop_first(2)
    restored = Buffer.from_list(100, buffer.to_list())
    assert restored.points == buffer.points
    assert [p.t - T0 for p in restored.points] == [2, 3, 4]


def test_u_nfl_08_smaller_capacity_thins_the_stored_buffer():
    rows = [[T0 + i, 43.5, 7.25] for i in range(10)]
    restored = Buffer.from_list(6, rows)
    assert len(restored) <= 6 and restored.points[-1].t == T0 + 9
