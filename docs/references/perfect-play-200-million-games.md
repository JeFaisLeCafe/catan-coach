# Perfect Play: 200 million simulated Catan games

Primary source: [The Best Catan Strategy, Tested on 200 Million Games](https://www.youtube.com/watch?v=3XLDKvhrIjk),
by [Perfect Play](https://www.youtube.com/@PerfectPlaySim).

The public video page and transcript do not identify downloadable code, raw results, or the source
of the cited 41,000-game comparison. Those figures are therefore creator-reported and cannot yet
be independently reproduced from linked artifacts.

## What the project does

The simulator turns six familiar plans into constrained players: Ore-Wheat-Sheep, Road Builder,
Port Trader, Biggest Numbers, Knight Army, and All Five. A Regular player provides an everyday
baseline. A parameter search finds strong settings within each plan's fixed rule, while a Tuned
player has no plan constraint.

The reported tournament covers every four-player table composed of four different plan players:
35 tables with 500,000 games each. Further experiments put each plan against three Tuned players,
change the trading regime, test three-player games, and ablate individual Tuned-player habits.
The simulator uses randomized boards with no adjacent 6 and 8, and a deliberately limited trading
rule: mutually useful one-for-one trades, with no trades to a player about to win.

The strongest presentation is not the headline tournament. It is the sequence of controlled
comparisons:

- remove a habit from the Tuned player;
- add the same habit to the Regular player;
- repeat against tables of different strength;
- report the change in win rate;
- compare selected aggregate patterns with 41,000 real online games.

This produces claims a player can act on: settlements before cities, pursue Longest Road, prefer
goals that are nearly affordable, ask for trades, avoid overvaluing ports during placement, and
place the robber where it causes concrete harm.

## Reported results

These are results inside the video's simulator, not universal Catan laws.

- Knight Army and All Five are effectively tied among the constrained plans.
- The unconstrained Tuned player wins 60.5% against three Regular players.
- Port Trader finishes last; forcing frequent port starts reduces the Tuned player's win rate.
- Making the Tuned player prefer cities before settlements costs roughly 6–15 percentage points
  depending on the table; giving settlement priority to the Regular player materially helps it.
- Pursuing Longest Road, preferring nearly affordable goals, and initiating trades each produce
  substantial gains in the reported ablations.
- Random robber placement is very costly.
- Against stronger opponents, most plans degrade sharply while Knight Army and All Five remain
  near a fair 25% share.
- Homogeneous simulated players create a first-seat edge absent from the real-game comparison.
  Adding noise to placement evaluation removes that edge, suggesting that population diversity
  matters to external validity.

## What Catan Coach should take from it

### 1. Explain decisions through interventions

Feature contributions say what influenced one prediction, but they do not prove a strategic habit
is beneficial. Add a separate counterfactual layer that changes one policy tendency and measures
the resulting win-rate difference across many games. Keep this distinct from Action-level Win
Probability and label it as simulation evidence.

### 2. Turn whole-game review into a strategy profile

The video's output is memorable because it names recurring habits. A Blunder Report can aggregate
decisions into interpretable themes:

- expansion before upgrades;
- progress toward Longest Road and Largest Army;
- resource diversity and production;
- affordability of the chosen goal;
- trade initiation and acceptance;
- robber impact;
- port opportunity cost.

Each theme should link back to the exact Plies that support it. This preserves the current
evidence-first design instead of assigning a vague player archetype.

### 3. Evaluate across a population, not only mirror matches

Self-play by four copies of one model can teach artifacts shared by that model. Future Corpora and
bot evaluation should mix policy versions, search strengths, controlled noise, and simple strategy
profiles. Report results by opponent population and Seat.

### 4. Add robustness scenarios to model adoption

Brier calibration remains the adoption gate. A separate strategy harness should test whether
recommendations remain useful across:

- three and four players;
- weak and strong opponents;
- different trading regimes;
- varied boards and Seat orders;
- deterministic versus noisy placement preferences.

This does not replace held-out Calibration; it catches policy-specific blind spots.

### 5. Use real games as an external-validity check

The video's most important caveat is the mismatch between homogeneous simulation and human games.
Table Recorder is therefore the right next product step. It creates a first-party stream of real
Positions and outcomes that can be compared with self-play without pretending those games are a
large representative dataset.

Start with descriptive checks—Seat results, build order, awards, trade frequency, robber targets,
and resource coverage—before using recorded games for training.

## What not to copy

- Do not turn the reported heuristics into hard-coded coaching rules.
- Do not present simulator win-rate differences as causal facts about human play.
- Do not replace calibrated Action ranking with fixed archetypes.
- Do not treat 200 million games as 200 million independent strategic observations when all games
  come from a small family of policies.
- Do not hide trading and negotiation limitations; they materially change which plan performs
  best in the video itself.

## Roadmap consequence

Build Table Recorder next, then add an evidence-linked Strategy Profile on top of recorded and
browser-played games. In parallel, define a population evaluation harness before generating the
next model generation.
