# 05 — Report a league

**What to build:** `catan-coach arena report <dir> --json ... --markdown ...` with the ladder,
intervals, head-to-head matrix, Seat effects, attrition, provenance, and per-Entrant Behavior
Profiles.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] Ladder ordered by Rating with 95% intervals and expected win rate
- [ ] Head-to-head matrix with block-bootstrap intervals
- [ ] Per-Entrant Behavior Profile means with block-bootstrap intervals, split by wins and losses,
      and Turns in won games
- [ ] Validity line using the Strategy Lab rules
- [ ] Byte-identical regeneration; JSON and Markdown agree
- [ ] The JSON is the input contract for the Strategy Report
