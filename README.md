# noforeignland tracking

A Home Assistant integration that shares your boat's track on
[noforeignland](https://www.noforeignland.com), so friends and family can follow you.
Positions logged while the boat has no internet are kept and sent when the connection
returns: the track has no gap. Companion of [Vigie](https://github.com/ovander/ha-vigie),
but it works with any `device_tracker` that has a latitude and longitude.

> **Status: beta (P8).** Built and tested against a simulated noforeignland; the first real
> sends wait for noforeignland's integration key, which will then be built in.

## What it does

- **Logs** your boat's position once a minute at most, only when the boat has moved 80 m
  and goes faster than 1.5 kn, plus one point every 6 hours when it stays put, so
  noforeignland keeps showing the boat as active. Impossible jumps (GPS glitches) are dropped.
- **Keeps** the points in Home Assistant's storage, through restarts and power cuts. When
  the buffer is full (10 000 points, about a week under way), every second old point is
  dropped rather than the oldest ones, so a long passage keeps its shape.
- **Sends** them once an hour, oldest first: the track keeps every minute's detail, the map
  is at most an hour late. A point leaves the buffer only once
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
- Your **boat API key**: on noforeignland's website, *Account → Settings → Boat tracking →
  API Key*. That is the only key you enter.

noforeignland's key for this integration is built in, as in noforeignland's own SignalK
plugin. Until noforeignland has issued it, setup asks for one in the optional *Integration
key* field; leave that field empty once a release includes it.

## Installation

1. HACS → ⋮ → *Custom repositories* → `https://github.com/ovander/ha-noforeignland`, type
   **Integration**.
2. Open *noforeignland tracking*, **Download** (only beta versions exist for now: turn on
   *Show beta versions* if HACS offers an older one), then restart Home Assistant.
3. *Settings → Devices & services → + Add integration → noforeignland tracking*: pick the
   boat's position (Vigie's boat is proposed) and enter its API key. Nothing is sent during
   setup.

There is no separate configuration page: everything is in Home Assistant's own screens.

- **Keys:** *Settings → Devices & services → noforeignland tracking → ⋮ → Reconfigure*.
- **Options:** the same page → **Configure**: how often the position is checked (60 s), the
  minimum move (80 m) and speed (1.5 kn), the stationary point (every 6 h), how often to send
  (every 60 min) and the buffer size (10 000 points).

## On a dashboard

The entities go on any dashboard. For example, an *Entities* card (edit a dashboard →
**+ Add card** → *Manual*, then paste; replace `garnet` with your boat's name as it appears
in the entity IDs):

```yaml
type: entities
title: noforeignland
entities:
  - entity: switch.noforeignland_garnet_sharing
  - entity: sensor.noforeignland_garnet_status
  - entity: sensor.noforeignland_garnet_buffered_points
  - entity: sensor.noforeignland_garnet_last_point_logged
  - entity: sensor.noforeignland_garnet_last_send
```

*Sharing* can also be switched by an automation, for example off when the boat enters the
home port's zone.

## Specification

[HA-SAIL-SPEC-001 §9.10](https://github.com/ovander/ha-vigie/blob/main/docs/HA-SAIL-SPEC-001.md),
the API contract
[NFL-TRACK-API-001](https://github.com/ovander/ha-vigie/blob/main/docs/NFL-TRACK-API-001.md)
and tests
[HA-SAIL-TEST-001 §3.11, §4.10](https://github.com/ovander/ha-vigie/blob/main/docs/HA-SAIL-TEST-001.md),
in the Vigie repository.

## License

Apache-2.0. Not affiliated with noforeignland.
