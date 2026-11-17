# 04 — Run and resume a league from the CLI

**What to build:** `catan-coach arena run <plan> --out <dir> [--workers N] [--allow-dirty]`,
reusing the Strategy Lab store, worker pool, and validity rules.

**Blocked by:** 02

**Status:** resolved

- [x] Each scheduled game stores all four Entrants by Seat, winner, and Behavior Profiles per Seat
- [x] Interrupting and re-running resumes without replaying finished games
- [x] Refuses a dirty tree unless `--allow-dirty`
- [x] Resume test on a tiny league gives an identical store

**Notes:** A league directory holds `league.json` (frozen plan + source provenance) beside the
Strategy Lab `games/` and `failures/` folders; each game file is named by its game id
(`c{cycle}-b{block}-r{rotation}`). The plan file uses the `LeaguePlan` JSON shape; model and
sidecar paths are relative to the plan file, and hashes are computed when absent and checked when
declared.
