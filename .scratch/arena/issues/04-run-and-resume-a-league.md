# 04 — Run and resume a league from the CLI

**What to build:** `catan-coach arena run <plan> --out <dir> [--workers N] [--allow-dirty]`,
reusing the Strategy Lab store, worker pool, and validity rules.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Each scheduled game stores all four Entrants by Seat, winner, and Behavior Profiles per Seat
- [ ] Interrupting and re-running resumes without replaying finished games
- [ ] Refuses a dirty tree unless `--allow-dirty`
- [ ] Resume test on a tiny league gives an identical store
