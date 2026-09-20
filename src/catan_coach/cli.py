"""Command-line analysis of a saved game, and Corpus generation."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from catan_coach.domain.analysis import Analysis
from catan_coach.domain.corpus import DEFAULT_VALIDATION_FRACTION, format_summary

_ANALYZE = "analyze"
_CORPUS = "corpus"
_SUBCOMMANDS = {_ANALYZE, _CORPUS}


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
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] not in _SUBCOMMANDS and not args_list[0].startswith("-"):
        args_list = [_ANALYZE, *args_list]

    parser = argparse.ArgumentParser(prog="catan-coach")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(_ANALYZE, help="rank Actions in a saved game at a Ply")
    analyze_parser.add_argument("game", type=Path)
    analyze_parser.add_argument("ply", type=int)

    corpus_parser = subparsers.add_parser(_CORPUS, help="generate a Corpus of self-play games")
    corpus_parser.add_argument("--games", type=int, required=True)
    corpus_parser.add_argument("--out", type=Path, required=True)
    corpus_parser.add_argument("--stride", type=int, default=12)
    corpus_parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    corpus_parser.add_argument("--seed", type=int, default=0)
    corpus_parser.add_argument(
        "--validation-fraction",
        type=float,
        default=DEFAULT_VALIDATION_FRACTION,
    )

    args = parser.parse_args(args_list)
    if args.command == _CORPUS:
        return _run_corpus(args)
    return _run_analyze(args)


def _run_analyze(args: argparse.Namespace) -> int:
    path: Path = args.game
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


def _run_corpus(args: argparse.Namespace) -> int:
    from catan_coach.engine.corpus import generate_corpus

    summary = generate_corpus(
        args.out,
        n_games=args.games,
        ply_stride=args.stride,
        seed=args.seed,
        workers=args.workers,
        validation_fraction=args.validation_fraction,
    )
    print(format_summary(summary))
    return 0
