# Changelog

All notable changes to this project are documented here. Format: Keep a Changelog;
versioning: SemVer.

## [Unreleased]

## [0.1.0-beta.1] - 2026-10-23

First beta. Tested against a simulated noforeignland only: the first real sends wait for
noforeignland's integration key. Install it to check the setup and the entities; nothing is
sent before a position is logged and the send time comes.

### Added
- First version (ovander/ha-vigie#93): shares a `device_tracker`'s positions on
  noforeignland. Logs a point when the boat has moved 80 m above 1.5 kn (one a minute at
  most, one every 6 hours when stationary), keeps the points through restarts and internet
  outages, and sends them once an hour, oldest first, each point once. *Sharing* switch;
  *Status*, *Buffered points*, *Last point logged* and *Last send* sensors; a repair notice
  when noforeignland refuses a key; diagnostics with the keys redacted. English and French.

[Unreleased]: https://github.com/ovander/ha-noforeignland/compare/v0.1.0-beta.1...HEAD
[0.1.0-beta.1]: https://github.com/ovander/ha-noforeignland/releases/tag/v0.1.0-beta.1
