"""Constants (SPEC HA-SAIL-SPEC-001 §9.10, OD-43)."""

from typing import Final

DOMAIN: Final = "noforeignland"

CONF_SOURCE: Final = "source"
CONF_BOAT_KEY: Final = "boat_key"
CONF_INTEGRATION_KEY: Final = "integration_key"

# Options and their defaults: those of noforeignland's own plugin (X-12 §8.1, §8.3)
CONF_SAMPLE_S: Final = "sample_seconds"
CONF_MIN_MOVE_M: Final = "min_move_m"
CONF_MIN_SPEED_KN: Final = "min_speed_kn"
CONF_KEEPALIVE_H: Final = "keepalive_hours"
CONF_SEND_MIN: Final = "send_minutes"
CONF_CAPACITY: Final = "buffer_points"

DEFAULTS: Final[dict[str, float]] = {
    CONF_SAMPLE_S: 60,
    CONF_MIN_MOVE_M: 80,
    CONF_MIN_SPEED_KN: 1.5,
    CONF_KEEPALIVE_H: 24,
    CONF_SEND_MIN: 10,
    CONF_CAPACITY: 10_000,
}

STATUS_OK: Final = "ok"
STATUS_WAITING: Final = "waiting"
STATUS_REJECTED: Final = "rejected"
STATUS_PAUSED: Final = "paused"
STATUSES: Final = [STATUS_OK, STATUS_WAITING, STATUS_REJECTED, STATUS_PAUSED]
