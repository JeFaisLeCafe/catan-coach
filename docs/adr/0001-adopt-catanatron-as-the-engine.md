# Adopt Catanatron as the game engine

Four previous attempts at this project (`catanai`, `catanai2`, `catan-game`, `catan-ai`) each
built their own Catan engine and died before producing a competent AI; the engine is tractable,
satisfying work that always needs one more rule, and it consumed the entire budget every time.
We therefore depend on [Catanatron](https://github.com/bcollazo/catanatron) rather than writing
a fifth engine, and accept a third-party dependency in exchange for full player-to-player
trading, a benchmarked bot ladder, sub-second full games, and a feature extractor.

Bots run **in-process in Python**. Catanatron also offers a language-agnostic stdio bot
protocol, which would have let us write TypeScript, but a stdio bot only receives the current
state and its legal actions — it cannot simulate forward, so it can never do tree search or
rollouts. Lookahead requires living in the same process as the engine.

## Consequences

`src/catan_coach/engine/` is the only package permitted to import catanatron. Swapping engines
later means rewriting that adapter; the domain, calibration harness, and analyzer are unaffected.
The Corpus and any trained model are tied to catanatron's exact feature layout and would have to
be regenerated.
