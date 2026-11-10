# Generation-7 audit: replay correction before publication

Two completed attempts exposed a harness defect during fresh-process replay checks. Neither
attempt supports the preregistered strength conclusion:

| Attempt | Candidate wins / completed | Hash seed | Replay |
| --- | ---: | --- | --- |
| Original | 2 / 2,000 | not fixed | failed |
| Fixed hash only | 8 / 2,000 | 0 | failed on the second replayed seed |

Both had zero dropped games or technical failures, but neither was reproducible across interpreter
processes. Their raw artifacts are retained locally under
`data/experiments/generation-7-vs-value-unfixed-hash/` and
`data/experiments/generation-7-vs-value-fixed-hash-only/`. These exploratory counts are disclosed
for completeness; they are excluded from the final decision and are not independent replications.

Catanatron creates some legal Action lists from sets. Its `ValueFunctionPlayer` chooses the first
Action on an exact tie, while our search samples from the supplied Action order. Python's string
hash seed and the process-specific hash of `None` in maritime trade tuples can change those lists.
Fixing `PYTHONHASHSEED` alone therefore does not suffice.

The correction sorts legal Actions by the existing Action label before handing them to experiment
players, and sorts search Action labels before seeded sampling. It changes no model, probability
map, search budget, preferences, game rules, seed range, or analysis rule. Baseline ties now have
an explicit stable order. A regression compares complete documents for four real model/search
games across fresh interpreter processes, different hash seeds, and serial versus parallel play.

The existing [preregistered plan](../../.scratch/strategy-lab/plans/08-generation-7.json) will be run
again only after this correction passes the full checks and review and is committed. The new run
must start from a clean tree, play all 2,000 games without inspecting interim wins, verify stored
games against fresh-process replays, and publish any result under the original decision rules.
The earlier outcomes were not used to select or tune any strategic setting. This note is committed
before the corrected run starts.
