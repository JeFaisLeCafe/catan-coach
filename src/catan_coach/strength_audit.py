"""Report whether generation 7 beats three ValueFunctionPlayer seats.

    uv run python -m catan_coach.strength_audit \\
        --out data/experiments/generation-7-vs-value --model model.txt --games 2000

Seeds run from 20000. A seed that already has a JSON file is not replayed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catan_coach.domain.dice import summarize_rolls
from catan_coach.domain.strength import (
    BASE_SEED,
    GameRecord,
    format_strength_report,
    game_record_from_json,
    strength_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit generation 7 against ValueFunctionPlayer.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("model.txt"))
    parser.add_argument("--base-seed", type=int, default=BASE_SEED)
    parser.add_argument("--games", type=int)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.report_only:
        if args.games is None:
            parser.error("--games is required")
        from catan_coach.engine.strength_audit import play_audit

        play_audit(
            args.out,
            model_path=args.model,
            games=args.games,
            base_seed=args.base_seed,
        )
    print(report_directory(args.out), end="")
    return 0


def report_directory(output_dir: Path | str) -> str:
    """Read stored games and print the strength answer. Does not play."""
    records = load_records(Path(output_dir))
    extreme = 0
    unavailable = 0
    for record in records:
        if record.rolls is None:
            unavailable += 1
            continue
        if summarize_rolls(record.rolls).extreme_twelves:
            extreme += 1
    return format_strength_report(
        strength_report(records),
        extreme_games=extreme,
        dice_unavailable=unavailable,
    )


def load_records(output_dir: Path) -> tuple[GameRecord, ...]:
    if not output_dir.is_dir():
        raise ValueError(f"no audit directory at {output_dir}")
    records: list[GameRecord] = []
    for path in sorted(output_dir.glob("*.json")):
        record = game_record_from_json(json.loads(path.read_text(encoding="utf-8")))
        if path.stem != str(record.seed):
            raise ValueError(f"{path.name} does not match seed {record.seed}")
        records.append(record)
    records.sort(key=lambda record: record.seed)
    seeds = [record.seed for record in records]
    if len(seeds) != len(set(seeds)):
        raise ValueError("audit directory has two games for one seed")
    return tuple(records)


if __name__ == "__main__":
    raise SystemExit(main())
