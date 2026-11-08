# Include bounded domestic trades in strong play

Catanatron can execute domestic trades but does not generate offers for bots. Leaving them out
means model self-play, search, and Analysis omit a central legal choice and learn a game where
players never trade.

Catan Coach adds at most ten offers derived from the acting Seat's own hand and immediate build
shortfalls. Opponent hands remain hidden. Offers are ranked using the proposer's hypothetical
post-trade hand; responders compare accepting with refusing from their own perspective. The same
Action set and resolved-hand evaluation are used by self-play, search, CLI Analysis, Coach Mode,
and game review.

## Consequences

This supersedes the Position Analyzer spec's exclusion of player-to-player trade strategy. It is
bounded heuristics, not open-ended negotiation: counteroffers, table talk, opponent modelling, and
multi-offer bargaining remain out of scope.

Catanatron's incomplete reply transitions are adapted inside `engine/`, preserving the engine
seam. Tests must cover every responder Seat, resolved-hand probabilities, and explanations for the
probability actually displayed.
