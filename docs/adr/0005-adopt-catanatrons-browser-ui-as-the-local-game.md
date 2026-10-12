# Adopt Catanatron's browser UI as the local game

The next product slice needs a clickable local Catan game, human-versus-bot play, replay, and a
Table Recorder. Two existing projects look reusable but sit on different sides of the engine seam.

`catan-game` is a clean TypeScript engine with 61 passing tests, but its only interface is a
terminal, its export has no matching import, and `catan-ai` currently has one Random AI whose
match test does not terminate. More importantly, Catan Coach's Corpus, model, legal Actions, and
Observations are tied to Catanatron. Building the local game on `catan-game` would create two rule
engines and require a lossy translation at every Position.

The pinned Catanatron commit already contains a React browser game and Flask game server using the
same engine as Catan Coach. It supports a clickable board, human and bot Seats, legal Actions,
redacted Seat perspectives, persistence, and replay. We will bring that pinned UI into this repo
as presentation code and adapt it, while continuing to consume Catanatron itself as the pinned
engine dependency.

## Consequences

- `src/catan_coach/engine/` remains the only Python package that imports Catanatron.
- Browser code may depend only on Catan Coach's local HTTP interface, never on a second game
  engine.
- Catan Coach owns its adapted UI. Updating the Catanatron git pin does not silently replace it.
- The application remains GPL-3.0-or-later, consistent with ADR 0003 and the upstream UI.
- The old `catan-game` and `catan-ai` repositories are reference material, not dependencies.
