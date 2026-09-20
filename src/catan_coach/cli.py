"""Command-line analysis of a saved game at a Ply."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from catan_coach.domain.analysis import Analysis


def format_analysis(analysis: Analysis, model_name: str, png_path: Path) -> str:
    lines = [
        f"Model: {model_name}",
        f"Win Probability for Seat {analysis.seat.name}",
        "",
    ]
    if analysis.is_forced:
        row = analysis.ranked[0]
        lines.extend(
            [
                f"Only legal Action: {row.action.label}",
                f"Win Probability {row.win_probability:.3f} (not a choice)",
                "",
            ]
        )
    else:
        lines.append(f"{'Action':<40} {'Win Probability':>16} {'Loss':>8}")
        lines.extend(
            f"{row.action.label:<40} {row.win_probability:>16.3f} {row.loss:>8.3f}"
            for row in analysis.ranked
        )
        lines.append("")
    lines.append(f"Position written to {png_path}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="catan-coach")
    parser.add_argument("game", type=Path)
    parser.add_argument("ply", type=int)
    args = parser.parse_args(argv)
    path = args.game
    if not path.is_file():
        print(f"No saved game at {path}", file=sys.stderr)
        return 1

    from catan_coach.domain.analysis import analyze
    from catan_coach.engine.features import public_vp_indices
    from catan_coach.engine.persist import position_at_ply, read_game
    from catan_coach.models.baselines import VictoryPointShareModel

    try:
        position = position_at_ply(read_game(path), args.ply)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    model = VictoryPointShareModel(public_vp_indices(position.num_players))
    analysis = analyze(position, model)
    png_path = path.with_name(f"{path.stem}-ply-{args.ply}.png")
    position.write_png(png_path)
    print(format_analysis(analysis, model.name, png_path))
    return 0
