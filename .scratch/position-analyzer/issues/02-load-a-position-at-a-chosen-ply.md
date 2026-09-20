# 02 — Load a Position from a saved game at a chosen Ply

**What to build:** Save a game to disk and get it back losslessly, and reach any Ply within it so
that a Position from the middle of a game can be handed to the analyzer.

Use the engine's existing full-fidelity serialization and its recorded Action log. Do not invent a
new position format.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] A finished game can be written to a file and read back
- [x] A restored game produces an identical Observation to the original for the same Seat
- [x] Any Ply in a saved game can be reached, yielding a Position ready to analyze
- [x] Requesting Ply zero yields the opening Position; requesting the final Ply yields the Position
      just before the game ended
- [x] Requesting a Ply beyond the end of the game fails with a message naming the valid range,
      rather than silently returning the last Position
- [x] The Seat to act at the requested Ply is recoverable from the loaded Position
- [x] Round-trip behaviour is covered by tests marked as engine-touching

## Comments

`write_game` / `read_game` / `position_at_ply` live in `engine/persist.py` and use catanatron's
JSON document plus the Action log. Valid plies are `0` to `len(action_records) - 1`.

Replay restores the board from recorded dice and steals. It cannot restore the live RNG: catanatron
bots evaluate by executing on copies that share the stream, and that consumption is not in the log.
After replay, the Position is reseeded from `(seed, ply)` so ROLL lookahead is deterministic.
