# Catan Coach

A tool for getting better at Settlers of Catan. Given a Position, it scores every legal
Action by Win Probability so you can see what you should have played and by how much.

## Language

### The game

**Position**:
A complete game state that play can resume from, including whose turn it is.
_Avoid_: state, board, situation

**Ply**:
One Action taken by one player. Positions within a game are addressed by ply number.
_Avoid_: move, step

**Turn**:
Everything one player does between rolling and ending. Contains several Plies.

**Action**:
One legal move available in a Position.

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
