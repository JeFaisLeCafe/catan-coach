# 04 — Record a physical game

**What to build:** Table Recorder mode, where one operator controls every Seat and enters the
random outcomes observed in a physical game.

**Blocked by:** 01 (Open a local game in the browser)

**Status:** ready-for-agent

- [ ] Game creation offers Table Recorder separately from human-versus-bot play
- [ ] Every Seat is manual and no bot advances automatically
- [ ] The operator can switch among Seat perspectives and an explicitly labelled spectator view
- [ ] The active Seat can enter its legal Action through the same board controls as normal play
- [ ] Dice results are entered rather than generated
- [ ] Development-card draws, stolen resources, and other hidden random outcomes are entered when
      required
- [ ] External outcomes are validated against the Position and engine inventories
- [ ] Invalid input explains what is inconsistent and does not advance the Ply
- [ ] Save, resume, and replay preserve the externally supplied outcomes exactly
- [ ] A round-trip test records fixed outcomes and reconstructs an identical Position
