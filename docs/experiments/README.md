# Strategy Lab experiments

The harness can run a preregistered plan, resume it, and write a Strength Report.
The generation-7 audit is complete: [report and reproduction](./generation-7-vs-value/README.md).
Generation 7 won 12 of 2,000 games against three `ValueFunctionPlayer` opponents and loses under
the preregistered rule. The settlement/city experiment remains unrun.

## Generation 7 versus ValueFunctionPlayer

Plan: [`.scratch/strategy-lab/plans/08-generation-7.json`](../../.scratch/strategy-lab/plans/08-generation-7.json)

500 games in each Seat, seeds 20000–21999, four search simulations, no exploration,
against three `ValueFunctionPlayer` opponents. The decision rule is in
[`.scratch/strategy-lab/issues/08-audit-generation-7.md`](../../.scratch/strategy-lab/issues/08-audit-generation-7.md).

```bash
uv run catan-coach lab run .scratch/strategy-lab/plans/08-generation-7.json \
  --out data/experiments/generation-7-vs-value
uv run catan-coach lab report data/experiments/generation-7-vs-value \
  --json docs/experiments/generation-7-vs-value/report.json \
  --markdown docs/experiments/generation-7-vs-value/report.md
```

Run this only from a clean tree. Do not stop early or change the model from the result.
Model adoption stays on the calibration harness.

## Settlement and city preferences

Plans:

- [`.scratch/strategy-lab/plans/09-reference.json`](../../.scratch/strategy-lab/plans/09-reference.json)
- [`.scratch/strategy-lab/plans/09-settlement.json`](../../.scratch/strategy-lab/plans/09-settlement.json)
- [`.scratch/strategy-lab/plans/09-city.json`](../../.scratch/strategy-lab/plans/09-city.json)

Search is zero. Each plan is 1,000 games per Seat from base seed 30000.
Compare with `--seed 20261109`. The analysis rules are in
[`.scratch/strategy-lab/issues/09-run-settlement-city-intervention.md`](../../.scratch/strategy-lab/issues/09-run-settlement-city-intervention.md).
These games are not comparable to the four-simulation audit above.
