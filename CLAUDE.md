# CLAUDE.md — ha-noforeignland

Standing instructions for Claude Code in this repository.

## Sources of truth

This integration is component C-15 of Vigie, phase P8. Its specification and tests live in
the Vigie repository and win over this code:

- SPEC `docs/HA-SAIL-SPEC-001.md` §9.10 (decisions OD-28, OD-41…OD-44) in `ovander/ha-vigie`;
- the noforeignland API contract `docs/NFL-TRACK-API-001.md` (X-12) in the same repository;
- TEST `docs/HA-SAIL-TEST-001.md` §3.11 (U-NFL), §4.10 (F-NFL), E-25, E-26.

Work packages, issues and the P8 milestone are tracked in `ovander/ha-vigie`; PRs here
reference them as `ovander/ha-vigie#N`. Spec or test changes go to the Vigie repository in
the same work package.

## Hard rules

- **Clean room.** noforeignland's SignalK plugin (`nfl-signalk`, MIT) is a reference for
  behaviour only (X-12); no code copied.
- **Keys (OD-45).** noforeignland's key for this integration is built in
  (`protocol.BUILTIN_INTEGRATION_KEY`), as noforeignland's SignalK plugin ships its own; add
  it only once noforeignland has issued it and agreed to its publication. Never use the
  SignalK plugin's key (X-12 §4.1). The boat key and any override are never committed,
  never logged, always redacted from diagnostics.
- **No test send.** Nothing goes to noforeignland outside the send schedule: a point on the
  public map cannot be deleted (X-12 OD-5). Tests mock noforeignland (`aioclient_mock`);
  the only live checks are E-25 (a test boat) and E-26, run by the owner.
- **At most once.** A point leaves the buffer only after a 2xx, and the buffer is saved at
  once (X-12 §7).
- **Layering.** `track.py` and `protocol.py` are pure Python: no `homeassistant` import;
  `tests/core/test_protocol.py` enforces it. `mypy --strict` on them.
- **Never weaken a gate**: no lower coverage threshold, no `# type: ignore` / `noqa` without
  a one-line justification, no skipped test without an issue reference.

## Conventions

- Python 3.13 in CI; pure modules also run on 3.12. Home Assistant 2026.2.0 minimum.
- ruff, line length 100. asyncio only on the HA side; never block the event loop.
- Entities: `has_entity_name`, translation keys, unique IDs `{entry_id}_{key}`, no polling.
  Every user-visible string in `strings.json`, `translations/en.json` and `fr.json`.
- Tests carry the TEST ID in their name (`test_u_nfl_04_…`); time moves with the harness's
  freezer, never real sleeps.
- Gate before every push, identical to CI:

```bash
ruff check . && ruff format --check . && mypy
pytest --cov --cov-report=term-missing --cov-fail-under=90
```

- Branches `feat/…`, `fix/…`, `docs/…`; Conventional Commits; PRs to `main`, never push to
  `main`. Release: tag `vX.Y.Z` (pre-release `vX.Y.Z-beta.N`), the owner's call.
