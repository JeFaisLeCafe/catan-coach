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
2. **Narrative** — an LLM (Claude, through the Anthropic SDK) receives only `facts.json`. It
   selects and orders **claims** (structured references to facts) and writes connecting prose.
   Code, not the LLM, renders every number and every causal sentence from the cited fact. The
   report renders without the narrative if the LLM is unavailable or validation fails.

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

- **Expansion vs upgrade** — post-setup settlements and cities per game, and the first post-setup
  build category (the only order the Behavior Profile records).
- **Awards** — Longest Road and Largest Army ownership rate; knights played.
- **Opening** — opening pips, distinct resources, adjacent port.
- **Development cards** — cards bought per game.
- **Trading** — offers, acceptances, completed and maritime trades.
- **Tempo** — Turns to win in won games.

New Behavior Profile fields (robber targets, resource production share) are follow-ups, not part
of this spec.

### Claim classes

- `descriptive` — a habit's rate or a difference between Entrants. Rendered with association
  language ("tends to", "in its wins").
- `interventional` — a paired Intervention comparison. Each such fact carries `valid` (the
  comparison passed its validity rules), `manipulation_check` (passed or failed), and
  `supported_direction` (`increase`, `decrease`, or `none`): a direction is set only when the
  comparison is valid, the check passed, the 95% interval excludes zero, and the attrition bound
  keeps the sign (issue 07's rules). Only a fact with a direction renders a causal sentence:
  "In this simulator, preferring {subject} {increased|decreased} the win rate by {value}
  ({interval})." Otherwise it renders "no reliable effect was shown".
- `strength` — ratings and win rates.

A **claim** is `{fact_id, template}`, where the template is one of a fixed set allowed for that
fact's class. The validator checks: every fact id exists; each template is allowed for its fact;
every section id is in the fixed set; every free-prose string contains no digits, percentages, or causal verbs ("causes", "improves", "makes you
win", "leads to", …). Because numbers and causal wording come only from rendered claims, prose
cannot attach a number or a cause to the wrong fact.

### Narrative step

- Input: `facts.json` and a fixed prompt committed in the repo. No raw games.
- Output: JSON sections `{section, paragraphs:[{prose_before, claims:[{fact_id, template}],
  prose_after}]}`. `section` is one of a fixed set of ids (ladder, head-to-head, one per theme,
  interventions); code renders its title. Every string the LLM writes is free prose and passes the
  same validation.
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
- Validator tests: an unknown fact id, a template not allowed for its fact, a digit or causal verb
  in prose, or a causal template on an interventional fact without a direction is rejected; a
  correct narrative passes and renders its numbers from facts.
- Narrative step tested with a fake client; no network in tests.
- HTML test: the page renders every fact id that a chart or citation references; no external URLs.

## Out of Scope

- Coaching UI inside the local app (later, once reports prove useful).
- Advice about human play; every claim is labelled as simulator evidence.
- Video or slide output.

## Further Notes

The first report is built from Arena league 1 and the issue-09 settlement/city Intervention.
