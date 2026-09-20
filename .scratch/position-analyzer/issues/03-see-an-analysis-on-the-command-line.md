# 03 — See an Analysis from the command line, on a rendered board

**What to build:** One command that names a saved game and a Ply and shows me the Analysis: a
readable table of Actions with their Win Probability and Loss, plus a rendered image of the
Position so the Action labels attach to somewhere on the board.

This is the first slice that is usable on its own. It runs with an existing Baseline as its model,
so the numbers will be poor — the point is that the whole path works end to end before any model
is trained.

**Blocked by:** 01 (Rank the Actions in a Position), 02 (Load a Position at a chosen Ply)

**Status:** ready-for-agent

- [ ] A single command takes a saved game and a Ply and prints the ranked Actions with Win
      Probability and Loss
- [ ] The same command writes a PNG of the Position and reports where it was written
- [ ] Rendering is headless: no window opens and the command works over SSH or in CI
- [ ] Which model produced the numbers is stated in the output, so Baseline results are never
      mistaken for trained ones
- [ ] The output makes clear which Seat the Win Probability refers to
- [ ] A Position with one legal Action reports that rather than printing a one-row table
- [ ] Invalid input — a missing file, an out-of-range Ply — produces a readable error, not a
      traceback
- [ ] The command holds no analysis logic of its own; it wires together existing pieces
- [ ] Covered by a smoke test asserting the command runs and produces both outputs
