# 02 — Load a Position from a saved game at a chosen Ply

**What to build:** Save a game to disk and get it back losslessly, and reach any Ply within it so
that a Position from the middle of a game can be handed to the analyzer.

Use the engine's existing full-fidelity serialization and its recorded Action log. Do not invent a
new position format.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A finished game can be written to a file and read back
- [ ] A restored game produces an identical Observation to the original for the same Seat
- [ ] Any Ply in a saved game can be reached, yielding a Position ready to analyze
- [ ] Requesting Ply zero yields the opening Position; requesting the final Ply yields the Position
      just before the game ended
- [ ] Requesting a Ply beyond the end of the game fails with a message naming the valid range,
      rather than silently returning the last Position
- [ ] The Seat to act at the requested Ply is recoverable from the loaded Position
- [ ] Round-trip behaviour is covered by tests marked as engine-touching
