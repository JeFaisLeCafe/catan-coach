# Spec: Local Play

**Status:** ready-for-agent

## Problem Statement

Catan Coach can analyze a saved Catanatron game, but there is no convenient way to create one.
The command line is not a playable board, and generated self-play games do not answer the personal
question: "How did the bots play against me, and where did I go wrong?"

A physical game is also valuable evidence, but today it cannot be recorded faithfully. Replaying
it requires controlling every Seat and entering the random outcomes that happened at the table,
rather than allowing a computer engine to roll different dice or draw different cards.

Finally, the current analyzer returns one immediate model estimate. Chess analysis gets more useful
the longer it runs; Catan Coach should also turn additional thinking time into a progressively
refined Analysis, while being honest about Catan's dice, hidden information, and multiplayer tree.

## Solution

Run a local browser game on the same pinned Catanatron engine used by the analyzer.

The game supports:

- human-versus-bot play with autosave, resume, and replay;
- an in-game Challenge Mode / Coach Mode toggle;
- a Table Recorder where one operator controls every Seat and supplies real-world random outcomes;
- a whole-game Blunder Report;
- immediate model Analysis followed by optional Progressive Analysis, either continuous until
  stopped or limited by a time budget chosen before it starts.

The pinned Catanatron React UI is the starting point. Catan Coach owns the adapted presentation,
HTTP interface, Analysis, and persistence; Catanatron remains a pinned engine dependency.

## User Stories

1. As a player, I want one local command to open a clickable Catan board in my browser.
2. As a player, I want to play one Seat against two or three bots.
3. As a player, I want each game autosaved after every Ply so closing the browser loses nothing.
4. As a player, I want to resume an unfinished game and replay a finished one.
5. As a player, I want to switch between Challenge Mode and Coach Mode during a game without
   changing the Position or invalidating the game.
6. As a player, I want Challenge Mode to hide live Analysis so I can measure my unaided play.
7. As a player, I want Coach Mode to show the recommended Actions, Win Probability, Loss, and
   reasons for the current Position.
8. As a player, I want the completed game reviewed as a timeline of my decisions, ordered by Loss.
9. As a player, I want forced Actions excluded from mistake counts.
10. As a player, I want to choose an Analysis budget such as 1, 5, 30, or 120 seconds.
11. As a player, I want an Analysis to improve while I leave it running and to stop immediately
    when the Position changes.
12. As a player, I want to see how much work supports the current result: simulations, explored
    nodes, elapsed time, and uncertainty.
13. As a player, I want to stop a continuous Analysis and keep the best completed result.
14. As a recorder, I want to control every Seat from one device.
15. As a recorder, I want to enter the physical dice result, development-card draw, stolen
    resource, and other hidden random outcomes so the recorded Position remains faithful.
16. As a recorder, I want to switch the visible Seat perspective before entering private Actions.
17. As a recorder, I want invalid physical-game input rejected with a useful explanation rather
    than silently corrupting the record.
18. As a sceptic, I want the immediate calibrated model estimate visually distinguished from the
    deeper search estimate.

## Implementation Decisions

### One engine

Catanatron is the only rules engine. The old `catan-game` and `catan-ai` repositories are not
runtime dependencies: their Position and Action models differ from the model's Catanatron
Observation layout.

### Local browser application

The pinned Catanatron UI provides the initial board, Action controls, Seat perspective, and replay
interaction. Its upstream limitation of one human Seat is removed in Table Recorder mode.

`uv run catan-coach play` starts a local server, uses a persistent local SQLite file, and opens the
browser. No account, cloud service, or internet connection is required after setup.

The server sends only a Seat's Observation during human-versus-bot play. Table Recorder explicitly
allows the operator to change perspective; spectator view is visibly labelled because it reveals
all hands.

### Game modes

Human-versus-bot and Table Recorder are game-creation choices. Challenge Mode and Coach Mode are a
presentation toggle that may change at any time:

- Challenge Mode hides current-Position Analysis. It does not stop recording information required
  for post-game review.
- Coach Mode shows Analysis and permits Progressive Analysis.

Changing this toggle is not a Ply and is not written to the game action log.

### Recording physical randomness

Normal games let Catanatron produce dice, development cards, steals, and other random outcomes.
Table Recorder instead submits a validated Action plus its externally observed result. The engine
applies that result through an Action record, preserving the same replay format used by generated
games. Unknown hidden outcomes must be entered before the recorded game can advance.

### Progressive Analysis

The current GBDT ranking is the immediate result. Deeper work uses stochastic tree search with the
trained model as the leaf evaluator:

- chance outcomes are sampled according to the engine;
- opponent Actions use search policy rather than pretending every opponent cooperates;
- work is accumulated in batches and snapshots are streamed to the browser;
- the tree is cancelled when the Position changes;
- completed Position results are cached locally.

Catan has no honest equivalent of chess's single depth number. The interface reports simulations,
nodes, elapsed time, effective horizon, and confidence intervals. A representative continuation
may be shown, but it is not presented as a forced line.

Two Search Budgets use the same engine:

- **Timed:** stop after the selected wall-clock duration.
- **Continuous:** continue until stopped or the Position changes.

Bot Search Budget and Presentation Delay are separate settings. The upstream 300 ms pause is only
Presentation Delay; the upstream fixed 100-simulation MCTS endpoint is replaced rather than used as
the product's Analysis.

### Whole-game review

The Blunder Report analyzes the Position before each non-forced human Action, compares the played
Action to the best Action, and presents decisions by Loss. It links every row to the replayed board
at that Ply. The report records the model version and Search Budget so results remain traceable.

## Testing Decisions

- Engine-touching game flows use small games or reduced victory targets and carry the `engine`
  marker.
- Browser tests cover creating a game, clicking a legal Action, toggling Challenge/Coach, resuming,
  replaying, and switching Table Recorder perspective.
- Table Recorder tests use fixed dice and hidden outcomes and assert that replay reconstructs the
  same Position.
- Progressive Analysis tests use a deterministic tiny search tree and fake clock, asserting
  monotonic work, timed stopping, explicit stopping, Position-change cancellation, and streamed
  snapshots without depending on exact probabilities.
- Blunder Report tests use a stub analyzer with hand-written Loss values.
- One end-to-end smoke test plays a short browser game against bots, persists it, resumes it, and
  opens its review.

## Out of Scope

- Remote multiplayer, accounts, matchmaking, and cloud saves.
- Mobile-native or desktop-native packaging; the local browser is the application.
- Import from Colonist or other third-party sites.
- Replacing Catanatron or modifying its upstream repository.
- Claiming that a finite stochastic search has solved a Catan Position.
