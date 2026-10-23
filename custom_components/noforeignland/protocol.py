"""noforeignland's track endpoint: the request and what its answer means (X-12 §3–§6).

Pure Python, no Home Assistant import. The HA side does the HTTP call with these headers
and this body, then classifies the answer here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from .track import Point

URL = "https://www.noforeignland.com/home/api/v1/boat/tracking/track"
CHUNK_POINTS = 1000  # X-12 OD-2, until noforeignland confirms a limit
ATTEMPTS = 3  # X-12 §8.3: on network errors and 5xx only
TIMEOUT_S = 30.0  # times the attempt number

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def is_integration_key(key: str) -> bool:
    """noforeignland's integration keys are UUIDs (X-12 §4.1)."""
    return bool(_UUID.match(key.strip()))


def headers(integration_key: str) -> dict[str, str]:
    # No gzip: compressed answers have truncated bodies for the reference client (X-12 §3)
    return {"X-NFL-API-Key": integration_key.strip(), "Accept-Encoding": "identity"}


def form(boat_key: str, points: Sequence[Point], version: str) -> dict[str, str]:
    """The form body of one request (X-12 §5): points oldest first, times in epoch ms."""
    if not points:
        raise ValueError("a track needs at least one point")
    track = [[round(p.t * 1000), round(p.lat, 7), round(p.lon, 7)] for p in points]
    return {
        "boatApiKey": boat_key.strip(),
        "timestamp": str(track[-1][0]),
        "track": json.dumps(track, separators=(",", ":")),
        "pluginVersion": f"ha-noforeignland/{version}",
    }


class Outcome(StrEnum):
    SENT = "sent"
    REJECTED = "rejected"
    RETRY = "retry"


@dataclass(frozen=True)
class Answer:
    outcome: Outcome
    message: str | None = None


def classify(status: int | None, body: str | None) -> Answer:
    """`status` None means no answer (network error or timeout)."""
    if status is None or status >= 500:
        return Answer(Outcome.RETRY, None if status is None else f"HTTP {status}")
    message = _message(body)
    if 200 <= status < 300:
        # Any 2xx is stored by noforeignland, even with an unreadable body: never resend it
        if message is not None and _status(body) == "error":
            return Answer(Outcome.REJECTED, message)
        return Answer(Outcome.SENT)
    return Answer(Outcome.REJECTED, message or f"HTTP {status}")


def _json(body: str | None) -> object:
    try:
        return json.loads(body) if body else None
    except ValueError:
        return None


def _status(body: str | None) -> object:
    data = _json(body)
    return data.get("status") if isinstance(data, dict) else None


def _message(body: str | None) -> str | None:
    data = _json(body)
    if isinstance(data, dict) and isinstance(data.get("message"), str):
        return str(data["message"])
    return None
