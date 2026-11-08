# References

Primary sources relevant to Catan Coach. A source is listed because it can change a design or
evaluation decision, not merely because it also uses AI.

## Strategy simulation and presentation

- [Perfect Play: 200 million simulated Catan games](./perfect-play-200-million-games.md) — the
  supplied video, its limitations, and the strongest ideas to adopt: controlled policy ablations,
  population testing, and evidence-linked strategy profiles.
- [`catan-game`](https://github.com/JeFaisLeCafe/catan-game) — the earlier local TypeScript engine
  should remain reference-only, but its typed event stream and statistics reducer provide a useful
  vocabulary: resources gained/lost, builds, robber actions, trades, awards, and turn boundaries.
  Reuse those concepts over Catanatron action logs rather than introducing a second rules engine.
- [Catan Companion](https://github.com/jeremymaignan/catan-companion) — a player-facing board
  companion with production, scarcity, port, robber, and placement summaries. Its value is the
  legibility of concrete board statistics; its hand-written recommendations should not replace
  calibrated Win Probability.
- [Catan-Simulator](https://github.com/williamaredal/Catan-Simulator) — exposes sortable aggregate
  outcomes such as resources spent, build counts, awards, and decision histories. These are useful
  candidates for Catan Coach's whole-game Strategy Profile.

## Search and learned play

- Szita, Chaslot, and Spronck,
  [Monte-Carlo Tree Search in Settlers of Catan](https://doi.org/10.1007/978-3-642-12993-3_3)
  (ACG 2009) — adapts MCTS to multiplayer stochastic Catan and shows the value of domain knowledge
  in both rollout policy and tree statistics. It supports the current model-guided progressive
  search design, while its small match samples are not a modern strength benchmark.
- Zhao et al.,
  [Playing Catan with Cross-dimensional Neural Network](https://arxiv.org/abs/2008.07079)
  (2020) — represents Catan's vertices, edges, tiles, and global values in compatible network
  components and reports stronger reinforcement learning than its JSettlers baseline. It is most
  relevant if the current tabular model reaches a measured ceiling; it is not evidence to replace
  the GBDT before then.
- [Catanatron](https://github.com/bcollazo/catanatron) and its
  [data/ML documentation](https://docs.catanatron.com/advanced/data-and-machine-learning) — the
  project's pinned engine and a source of simulation hooks, Parquet game output, bots, and
  reproducible benchmarks.

## Trading and human interaction

- Cuayáhuitl et al.,
  [Strategic Dialogue Management via Deep Reinforcement Learning](https://arxiv.org/abs/1511.08099)
  (2015) — learns Catan offer and response policies and reports a 53% win rate against three fixed
  bots, versus 27% for its supervised baseline. It confirms that trade policy deserves its own
  evaluation rather than being inferred from a position evaluator alone.
- [STAC corpus](https://www.irit.fr/STAC/corpus.html) — 45 human online Catan games with strategic
  chat, negotiation, dialogue-act, discourse, and situated game-event annotations. It is small and
  tied to another engine/protocol, but it is the strongest public source found for studying how
  human bargaining differs from deterministic bot trades.

## Human-game external validity

- [Colonist.io 2024 summary](https://blog.colonist.io/colonist-io-2024-summary/) — Colonist reports
  45.2 million games in 2024 and 600 GB of stored game data. The underlying event data is not
  publicly provided, so this establishes that a valuable comparison corpus exists, not that Catan
  Coach can train on it.
- [Bo Peng interview](https://blog.colonist.io/bo-peng-interview/) — useful expert hypotheses, such
  as placement importance and Ore-Wheat-Sheep preferences, to test in simulation. Expert advice is
  a source of experiments, not ground truth.

## Consequences for the roadmap

1. Build Table Recorder so real games can enter the same lossless replay and review pipeline.
2. Add an evidence-linked Strategy Profile over a game, aggregating exact Plies into understandable
   habits without turning them into fixed rules.
3. Evaluate future models against a population of policies, strengths, Seats, boards, player
   counts, and trading regimes in addition to the held-out calibration gate.
4. Treat negotiation as a separate policy problem. Keep the current bounded trade heuristic
   explicit until it beats baselines through its own harness.
5. Investigate external imports or partnerships only with permission and a documented data
   license; do not scrape proprietary human-game logs into the Corpus.
