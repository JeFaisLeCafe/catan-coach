# 02 — Schedule a league

**What to build:** a pure `domain/` league plan and schedule (see spec, "Schedule").

**Blocked by:** none

**Status:** ready-for-agent

- [ ] League plan: name, Entrants (2 to 12, distinct names), games per Entrant, base seed, rules,
      map policy; JSON round-trip
- [ ] Schedule: all `C(n,4)` tables, four Seat rotations each sharing one board seed, repeated in
      blocks until the declared games per Entrant are reached
- [ ] Every Entrant plays every Seat equally often; tests assert it for n = 4, 5, 7
- [ ] Deterministic: same plan, same schedule, same pairing keys
