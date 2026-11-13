# Catan Coach

A tool for getting better at Settlers of Catan. Given a Position, it scores every legal
Action by Win Probability so you can see what you should have played and by how much.

## Language

### The game

**Position**:
A complete game state that play can resume from, including whose turn it is.
_Avoid_: state, board, situation

**Action**:
One legal choice a Position offers, whether or not anyone plays it.

**Ply**:
The one Action a Seat actually plays. Positions within a game are addressed by ply number.
_Avoid_: move, step

**Turn**:
Everything one player does between rolling and ending. Contains several Plies.

**Setup**:
The placements before the first roll. Each Seat places two settlements and two roads.

**Pip**:
One dot on a number token: one of the 36 ways two dice can roll that number. A 6 or an 8 is 5 pips; a 2 or a 12 is 1. The desert has none.

**Opening pips**:
The pips on the numbered tiles touching the two Setup settlements. A tile touching both settlements counts twice.

**Distinct resources**:
How many different resource types those two settlements touch. The same resource on two tiles counts once.

**Adjacent port**:
Either Setup settlement touching a port.

**Post-setup build**:
A settlement, city, or road placed after Setup. The two Setup settlements and two Setup roads are excluded, so a post-setup settlement count of 0.20 means almost no third settlement was built.

**Seat**:
A player's place at the table. Seat order confers an advantage, so a Win Probability is
always stated for a given Seat.
_Avoid_: colour, player number

### What the model may see

**Observation**:
The Seat-perspective view of a Position: everything a person in that Seat could legitimately
know. Excludes opponents' specific cards; includes their hand counts.
_Avoid_: features, state vector, sample

### Evaluation

**Win Probability**:
The chance a given Seat wins from a Position under strong play. The project's single unit of
evaluation.
_Avoid_: score, evaluation, centipawns, value

**Analysis**:
The ranked set of Win Probabilities for every legal Action in a Position.

**Loss**:
The best Action's Win Probability minus the chosen Action's. The cost of a mistake, in
percentage points. Named by analogy with chess centipawn loss.
_Avoid_: regret (already means something else in reinforcement learning), delta, error

**Blunder**:
An Action whose Loss exceeds a threshold.

### Knowing whether it works

**Calibration**:
The agreement between predicted Win Probability and observed win frequency. Positions called
70% should be won about 70% of the time. The project's correctness criterion.

**Discrimination**:
The ability to separate winning Positions from losing ones. Distinct from Calibration: a model
that always predicts the base rate is perfectly calibrated and entirely useless.

**Corpus**:
A set of self-play games, each sampled Position labelled with the Seat that eventually won.
_Avoid_: dataset, training data

**Baseline**:
A deliberately simple model that a real model must beat before it is believed.

### Playing and recording

**Challenge Mode**:
Live play with Analysis hidden. The completed game can still be reviewed afterward.

**Coach Mode**:
Live play with Analysis visible. A game may switch between Challenge Mode and Coach Mode
without changing its Position or history.

### Thinking

**Search Budget**:
The computation an Analysis may spend, expressed as elapsed time or simulations. Unlike a
Presentation Delay, more Search Budget can improve the Analysis.

**Progressive Analysis**:
An Analysis published immediately and then revised as more Search Budget is spent. It stops when
its Position changes, its time budget expires, or the player stops it.

**Presentation Delay**:
A minimum visual pause before showing a completed bot Action. It performs no computation and does
not improve an Analysis.

### Learning from many games

**Policy**:
The rule a Seat uses to choose an Action. A model estimates Win Probability; a Policy turns those
estimates, search results, and any explicit preferences into play.
_Avoid_: AI (too broad), model (a Policy may use a model but is not the model)

**Strategy Experiment**:
A reproducible set of games that compares Policies under a declared Seat schedule, board seeds,
opponent population, and rules. Its independent samples are games, not Positions.
_Avoid_: benchmark (unless referring only to runtime), simulation (one implementation technique)

**Intervention**:
One declared change to a Policy used to test a strategic hypothesis, such as increasing its
preference for settlements without changing anything else.
_Avoid_: feature importance (describes a predictor, not a change in play)

**Behavior Profile**:
Descriptive measurements of how a Policy or Seat played across games: build order, awards, trades,
robber use, production, and similar observable habits. A Behavior Profile describes association;
it does not by itself establish that a habit caused wins.
_Avoid_: play style (too vague), strategy (implies intent or causality)

**Opponent Population**:
The declared mix of Policies and strengths faced in a Strategy Experiment. A result against one
Opponent Population is not assumed to transfer to another.

**Arena**:
A league in which a declared field of Entrants plays a balanced schedule of mixed four-player
tables, producing a Rating for each.
_Avoid_: tournament (suggests a knockout), bracket

**Entrant**:
One named, frozen Policy taking part in an Arena. The same model at two Search Budgets is two
Entrants.

**Rating**:
An Entrant's fitted strength from every Arena game it played, with Seat effects removed, stated
with a 95% interval. A gap inside the intervals is not a ranking.
_Avoid_: Elo (the display scale borrows Elo's units, not its update rule)

**Champion**:
The installed model, as the Policy a candidate must beat to replace it.

**Champion Challenge**:
A preregistered Strategy Experiment of a candidate against three Champion Seats. Passing it, with
the calibration gate, promotes the candidate.

**Strategy Profile**:
A Behavior Profile summarised into named themes (expansion vs upgrade, awards, opening, trading,
tempo) for one Entrant across its games. Descriptive, like the Behavior Profile it comes from.

**Strategy Report**:
A readable page built from computed facts, with an optional narrative in which every number cites a
fact.
