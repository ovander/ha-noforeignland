# Changelog

All notable changes to this project are documented here. Format: Keep a Changelog;
versioning: SemVer.

## [Unreleased]

### Added
- First version (ovander/ha-vigie#93): shares a `device_tracker`'s positions on
  noforeignland. Logs a point when the boat has moved 80 m above 1.5 kn (one a minute at
  most, one every 6 hours when stationary), keeps the points through restarts and internet
  outages, and sends them once an hour, oldest first, each point once. *Sharing* switch;
  *Status*, *Buffered points*, *Last point logged* and *Last send* sensors; a repair notice
  when noforeignland refuses a key; diagnostics with the keys redacted. English and French.
