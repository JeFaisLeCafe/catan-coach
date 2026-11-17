# 05 — Report a league

**What to build:** `catan-coach arena report <dir> --json ... --markdown ...` with the ladder,
intervals, head-to-head matrix, Seat effects, attrition, provenance, and per-Entrant Behavior
Profiles.

**Blocked by:** 03, 04

**Status:** resolved

- [x] Ladder ordered by Rating with 95% intervals and expected win rate
- [x] Head-to-head matrix with block-bootstrap intervals
- [x] Per-Entrant Behavior Profile means with block-bootstrap intervals, split by wins and losses,
      and Turns in won games
- [x] Validity line using the Strategy Lab rules
- [x] Byte-identical regeneration; JSON and Markdown agree
- [x] The JSON is the input contract for the Strategy Report
