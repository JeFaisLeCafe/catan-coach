# 02 — Schedule a league

**What to build:** a pure `domain/` league plan and schedule (see spec, "Schedule").

**Blocked by:** none

**Status:** ready-for-agent

- [ ] League plan: name, Entrants (4 to 12, distinct names), cycles (≥ 1), base seed, rules, map
      policy; JSON round-trip; fewer than four Entrants is rejected
- [ ] Schedule: each cycle plays every `C(n,4)` combination as one block of four cyclic Seat
      rotations sharing one board seed; each block has its own seed
- [ ] Every Entrant plays `C(n-1,3)` games per Seat per cycle; tests assert it for n = 4, 5, 7
- [ ] Each scheduled game has a unique game id (block id + rotation), never the seed alone
- [ ] Deterministic: same plan, same schedule, same pairing keys
