# noforeignland tracking

A Home Assistant integration that shares your boat's track on
[noforeignland](https://www.noforeignland.com), so friends and family can follow you.
Positions logged while the boat has no internet are kept and sent when the connection
returns: the track has no gap. Companion of [Vigie](https://github.com/ovander/ha-vigie),
but it works with any `device_tracker` that has a latitude and longitude.

> **Status: in development (P8).** Built and tested against a simulated noforeignland; the
> first real sends wait for noforeignland's integration key. Not released yet.

## What it does

- **Logs** your boat's position once a minute at most, only when the boat has moved 80 m
  and goes faster than 1.5 kn, plus one point a day when it stays put, so noforeignland
  keeps showing the boat as active. Impossible jumps (GPS glitches) are dropped.
- **Keeps** the points in Home Assistant's storage, through restarts and power cuts. When
  the buffer is full (10 000 points, about a week under way), every second old point is
  dropped rather than the oldest ones, so a long passage keeps its shape.
- **Sends** them every 10 minutes, oldest first. A point leaves the buffer only once
  noforeignland has accepted it, so nothing is sent twice. Without internet, it waits.
- If noforeignland **refuses** a key, sending stops, the points are kept and Home
  Assistant shows a repair notice.

Entities: a **Sharing** switch (off: nothing is logged or sent, for example in your home
port), **Status** (`ok`, `waiting`, `rejected`, `paused`), **Buffered points**, **Last
point logged** and **Last send**.

Points already on noforeignland cannot be deleted: switch *Sharing* off before you go
somewhere that should stay private.

## Requirements

- Home Assistant 2026.2.0 or later, with HACS.
- A position: for example [Vigie](https://github.com/ovander/ha-vigie)'s
  `device_tracker.<boat>`.
- Two keys:
  - your **boat API key**: on noforeignland's website, *Account → Settings → Boat tracking
    → API Key*;
  - an **integration key** for this integration, from noforeignland
    (`support@noforeignland.com`).

## Installation

Not released yet. Once it is: HACS → ⋮ → *Custom repositories* →
`https://github.com/ovander/ha-noforeignland`, type **Integration**; download
*noforeignland tracking*, restart Home Assistant, then *Settings → Devices & services →
Add integration → noforeignland tracking*: pick the boat's position and enter the two
keys. Nothing is sent during setup.

The options (⋮ → *Configure*) change how often a position is checked, the minimum move and
speed, the stationary point's interval, how often to send and the buffer size.

## Specification

[HA-SAIL-SPEC-001 §9.10](https://github.com/ovander/ha-vigie/blob/main/docs/HA-SAIL-SPEC-001.md),
the API contract
[NFL-TRACK-API-001](https://github.com/ovander/ha-vigie/blob/main/docs/NFL-TRACK-API-001.md)
and tests
[HA-SAIL-TEST-001 §3.11, §4.10](https://github.com/ovander/ha-vigie/blob/main/docs/HA-SAIL-TEST-001.md),
in the Vigie repository.

## License

Apache-2.0. Not affiliated with noforeignland.
