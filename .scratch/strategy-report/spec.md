# Spec: Strategy Report

**Status:** ready-for-agent

## Problem Statement

The Strategy Lab and the Arena produce JSON and Markdown that a researcher can audit but a player
cannot read. The Perfect Play video (`docs/references/perfect-play-200-million-games.md`) shows the
missing layer: named Policies, the habits that distinguish them, and controlled comparisons
("settlements before cities: +X points"), presented visually. Its weakness is that none of its
claims can be traced to published data.

Catan Coach needs that readable layer without giving up traceability: every sentence a player
reads must point to a number the harness computed.

## Solution

A **Strategy Report**: a self-contained HTML page generated from Arena and Strategy Lab outputs. It
has two layers with a hard boundary between them.

1. **Facts** — deterministic code computes every number: the ladder, head-to-head, a
   **Strategy Profile** per Entrant, and the Intervention results. Facts are written to
   `facts.json`, each with a stable id, value, interval where one exists, sample size, and source
   artifact.
2. **Narrative** — an LLM (Claude, through the Anthropic SDK) receives only `facts.json` and writes
   short plain-language sections. Every numeric claim must cite a fact id. A validator rejects any
   narrative whose numbers do not match the cited facts, or that states a causal claim not backed
   by an Intervention fact. The report renders without the narrative if the LLM is unavailable or
   validation fails.

Charts are drawn from facts, never from narrative.

## User Stories

1. As a player, I want a one-page report after each league, so that I can see which bot is strongest
   and by how much.
2. As a player, I want each bot's habits described in Catan terms (expands early, rushes cities,
   chases Longest Road), so that I recognise styles I can copy or punish.
3. As a player, I want controlled comparisons shown separately from descriptive habits, so that I
   know which claims are causal inside the simulator and which are only associations.
4. As a player, I want every sentence linked to its number, so that I can check any claim.
5. As a researcher, I want the report reproducible from artifacts, with the narrative cached, so
   that regenerating it does not change it.
6. As a researcher, I want the LLM step optional and swappable, so that the report never depends on
   a network call.

## Implementation Decisions

### Strategy Profile themes

Computed per Entrant from Behavior Profiles across its games, with intervals, split by wins and
losses where useful:

- **Expansion vs upgrade** — post-setup settlements, cities, and which came first.
- **Awards** — Longest Road and Largest Army ownership rate; knights played.
- **Opening** — opening pips, distinct resources, adjacent port.
- **Development cards** — cards bought per game.
- **Trading** — offers, acceptances, completed and maritime trades.
- **Tempo** — Turns to win in won games.

New Behavior Profile fields (robber targets, resource production share) are follow-ups, not part
of this spec.

### Claim classes

- `descriptive` — a habit's rate or a difference between Entrants. Narrative must use association
  language ("tends to", "in its wins").
- `interventional` — a paired Intervention comparison. Narrative may say "in this simulator,
  preferring X changed the win rate by Y", only if the manipulation check passed.
- `strength` — ratings and win rates.

The validator checks: every number in the narrative appears in a cited fact (after rounding as
displayed); causal verbs ("causes", "makes you win", "improves") appear only in sentences citing an
`interventional` fact; no fact id is invented.

### Narrative step

- Input: `facts.json` and a fixed prompt committed in the repo. No raw games.
- Output: JSON sections `{id, title, paragraphs:[{text, cites:[fact ids]}]}`.
- Cached by hash of facts + prompt + model id under the report directory; regeneration reuses the
  cache. `--no-narrative` skips the step.
- The model id is a CLI option with a default pinned at implementation time to the latest Claude
  model; the API key comes from the environment and is never written to artifacts.
- Lives outside `domain/` (it does I/O) and outside `engine/` (no Catanatron).

### Page

Self-contained HTML (inline CSS/JS, no CDN): ladder with interval bars; head-to-head heatmap;
Strategy Profile small multiples per Entrant; Intervention forest plot (difference with interval,
manipulation check marked); narrative beside charts with citation chips that reveal the fact.
Light and dark themes. Written to `<dir>/report.html`.

`catan-coach report-strategy <arena dir> [--interventions <comparison.json> ...] --out <dir>
[--no-narrative] [--model <id>]`.

## Testing Decisions

- Facts are deterministic: byte-identical `facts.json` from the same artifacts.
- Validator tests: a narrative with a wrong number, an uncited number, an invented fact id, or a
  causal verb on a descriptive fact is rejected; a correct one passes.
- Narrative step tested with a fake client; no network in tests.
- HTML test: the page renders every fact id that a chart or citation references; no external URLs.

## Out of Scope

- Coaching UI inside the local app (later, once reports prove useful).
- Advice about human play; every claim is labelled as simulator evidence.
- Video or slide output.

## Further Notes

The first report is built from Arena league 1 and the issue-09 settlement/city Intervention.
