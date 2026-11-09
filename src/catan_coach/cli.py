"""Command-line analysis of a saved game, and Corpus generation."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from catan_coach.domain.analysis import Analysis
from catan_coach.domain.corpus import DEFAULT_VALIDATION_FRACTION, Corpus, format_summary
from catan_coach.domain.prediction import WinProbabilityModel

if TYPE_CHECKING:
    from catan_coach.models.gbdt import GbdtModel
    from catan_coach.models.train import BaselineComparison

_ANALYZE = "analyze"
_CORPUS = "corpus"
_TRAIN = "train"
_ADOPT = "adopt"
_CALIBRATE = "calibrate"
_REPORT = "report"
_PLAY = "play"
_LAB = "lab"
_SUBCOMMANDS = {_ANALYZE, _CORPUS, _TRAIN, _ADOPT, _CALIBRATE, _REPORT, _PLAY, _LAB}


_NEAR_TIE_LOSS = 0.01


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
        lines.append(f"{'Action':<40} {'Win Probability':>16} {'Loss (pp)':>10}")
        for row in analysis.ranked:
            line = f"{row.action.label:<40} {row.win_probability:>16.3f} {row.loss * 100:>10.1f}"
            if row.reasons:
                labels = ", ".join(
                    f"{reason.label} {reason.delta * 100:+.1f}" for reason in row.reasons
                )
                line = f"{line}  {labels}"
            lines.append(line)
        lines.append("")
        if len(analysis.ranked) > 1:
            lead = analysis.ranked[1].loss * 100
            if analysis.ranked[1].loss <= _NEAR_TIE_LOSS:
                lines.append(
                    f"The top Action leads by {lead:.1f} points of Win Probability (near-tie)."
                )
            else:
                lines.append(f"The top Action leads by {lead:.1f} points of Win Probability.")
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
    analyze_parser.add_argument(
        "--model",
        type=Path,
        default=Path("model.txt"),
        help="trained model to use when --baseline is not set",
    )
    analyze_parser.add_argument(
        "--baseline",
        choices=("vp-share", "constant"),
        help="score with a Baseline instead of the trained model",
    )

    corpus_parser = subparsers.add_parser(_CORPUS, help="generate a Corpus of self-play games")
    corpus_parser.add_argument("--games", type=int, required=True)
    corpus_parser.add_argument("--out", type=Path, required=True)
    corpus_parser.add_argument("--stride", type=int, default=12)
    corpus_parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    corpus_parser.add_argument("--seed", type=int, default=0)
    corpus_parser.add_argument(
        "--players",
        choices=("value", "model"),
        default="value",
        help="who plays the games: the value-function bot, or a saved model",
    )
    corpus_parser.add_argument(
        "--model",
        type=Path,
        help="saved model used when --players model",
    )
    corpus_parser.add_argument(
        "--validation-fraction",
        type=float,
        default=DEFAULT_VALIDATION_FRACTION,
    )

    train_parser = subparsers.add_parser(_TRAIN, help="train a Win Probability model on a Corpus")
    train_parser.add_argument("--corpus", type=Path, action="append", required=True)
    train_parser.add_argument("--out", type=Path, required=True)
    train_parser.add_argument("--seed", type=int, default=0)
    train_parser.add_argument(
        "--installed",
        type=Path,
        help="also require the candidate to beat this model; the file is not replaced",
    )

    adopt_parser = subparsers.add_parser(
        _ADOPT,
        help="train a candidate and replace the installed model only if it wins",
    )
    adopt_parser.add_argument("--corpus", type=Path, action="append", required=True)
    adopt_parser.add_argument("--installed", type=Path, required=True)
    adopt_parser.add_argument("--candidate", type=Path, required=True)
    adopt_parser.add_argument("--seed", type=int, default=0)

    calibrate_parser = subparsers.add_parser(
        _CALIBRATE,
        help="fit a monotone map and replace the installed model only if Brier clears",
    )
    calibrate_parser.add_argument("--model", type=Path, required=True)
    calibrate_parser.add_argument("--corpus", type=Path, action="append", required=True)
    calibrate_parser.add_argument("--installed", type=Path, required=True)
    calibrate_parser.add_argument("--out", type=Path, required=True)
    calibrate_parser.add_argument("--seed", type=int, default=0)

    report_parser = subparsers.add_parser(_REPORT, help="report a model against the Baselines")
    report_parser.add_argument("--corpus", type=Path, required=True)
    report_parser.add_argument("--model", type=Path, required=True)

    play_parser = subparsers.add_parser(_PLAY, help="play Catan in a local browser")
    play_parser.add_argument("--host", default="127.0.0.1")
    play_parser.add_argument("--port", type=int, default=5001)
    play_parser.add_argument("--no-browser", action="store_true")

    lab_parser = subparsers.add_parser(_LAB, help="run a Strategy Lab experiment")
    lab_commands = lab_parser.add_subparsers(dest="lab_command", required=True)
    lab_run = lab_commands.add_parser("run", help="play or resume a plan")
    lab_run.add_argument("plan", type=Path)
    lab_run.add_argument("--out", type=Path, required=True)
    lab_run.add_argument("--workers", type=int, default=1)
    lab_run.add_argument("--allow-dirty", action="store_true")
    lab_report = lab_commands.add_parser("report", help="summarize a finished or partial run")
    lab_report.add_argument("experiment", type=Path)
    lab_report.add_argument("--json", type=Path)
    lab_report.add_argument("--markdown", type=Path)
    lab_compare = lab_commands.add_parser("compare", help="compare preference variants")
    lab_compare.add_argument("reference", type=Path)
    lab_compare.add_argument("variants", type=Path, nargs="+")
    lab_compare.add_argument("--seed", type=int, default=0)
    lab_compare.add_argument("--json", type=Path)
    lab_compare.add_argument("--markdown", type=Path)

    args = parser.parse_args(args_list)
    if args.command == _LAB:
        return _run_lab(args)
    if args.command == _CORPUS:
        return _run_corpus(args)
    if args.command == _TRAIN:
        return _run_train(args)
    if args.command == _ADOPT:
        return _run_adopt(args)
    if args.command == _CALIBRATE:
        return _run_calibrate(args)
    if args.command == _REPORT:
        return _run_report(args)
    if args.command == _PLAY:
        return _run_play(args)
    return _run_analyze(args)


def _run_lab(args: argparse.Namespace) -> int:
    from catan_coach.engine.experiment_store import PlanMismatch
    from catan_coach.engine.lab import DirtyWorktree, compare_dirs, report_dir, run_plan

    try:
        if args.lab_command == "run":
            return run_plan(args.plan, args.out, workers=args.workers, allow_dirty=args.allow_dirty)
        if args.lab_command == "report":
            return report_dir(args.experiment, json_path=args.json, markdown_path=args.markdown)
        return compare_dirs(
            args.reference,
            args.variants,
            seed=args.seed,
            json_path=args.json,
            markdown_path=args.markdown,
        )
    except (DirtyWorktree, PlanMismatch, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


def _run_analyze(args: argparse.Namespace) -> int:
    path: Path = args.game
    if not path.is_file():
        print(f"No saved game at {path}", file=sys.stderr)
        return 1

    from catan_coach.engine.features import feature_names, public_vp_indices
    from catan_coach.engine.persist import position_at_ply, read_game
    from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel
    from catan_coach.models.gbdt import GbdtModel

    try:
        position = position_at_ply(read_game(path), args.ply)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    n_players = position.num_players
    if args.baseline == "constant":
        model: WinProbabilityModel = ConstantModel(n_players)
    elif args.baseline == "vp-share":
        model = VictoryPointShareModel(public_vp_indices(n_players))
    elif args.model.is_file():
        model = GbdtModel.load(args.model, feature_names=feature_names(n_players))
    else:
        print(f"No trained model at {args.model}; using vp-share", file=sys.stderr)
        model = VictoryPointShareModel(public_vp_indices(n_players))

    analysis = position.analyze(model)
    png_path = path.with_name(f"{path.stem}-ply-{args.ply}.png")
    position.write_png(png_path)
    print(format_analysis(analysis, model.name, png_path))
    return 0


def _run_play(args: argparse.Namespace) -> int:
    from catan_coach.engine.web import run_local_server

    try:
        run_local_server(
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
        )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
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
        players=args.players,
        model_path=args.model,
    )
    print(format_summary(summary))
    return 0


def _run_train(args: argparse.Namespace) -> int:
    installed: WinProbabilityModel | None = None
    if args.installed is not None:
        loaded = _installed_model(args.installed)
        if isinstance(loaded, int):
            return loaded
        installed = loaded
    try:
        model, comparison, n_games = _fit_mixture(args.corpus, args.seed, installed)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    model.save(args.out)
    print(f"Wrote {args.out}")
    return _emit_comparison(
        comparison,
        args.corpus,
        n_games,
        require_installed=args.installed is not None,
    )


def _run_adopt(args: argparse.Namespace) -> int:
    from catan_coach.models.gbdt import GbdtModel
    from catan_coach.models.train import install_candidate

    if args.candidate.resolve() == args.installed.resolve():
        print("refusing to write the candidate over the installed model", file=sys.stderr)
        return 1
    if not args.installed.is_file():
        print(f"No trained model at {args.installed}", file=sys.stderr)
        return 1
    try:
        model, comparison, n_games = _fit_mixture(
            args.corpus,
            args.seed,
            GbdtModel.load(args.installed, name="installed"),
            model_name="candidate",
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    model.save(args.candidate)
    print(f"Wrote {args.candidate}")
    code = _emit_comparison(comparison, args.corpus, n_games, require_installed=True)
    if code != 0 or not install_candidate(args.candidate, args.installed, comparison):
        print(f"Left {args.installed} unchanged")
        return 1
    print(f"Installed {args.installed}")
    return 0


def _run_calibrate(args: argparse.Namespace) -> int:
    from catan_coach.engine.calibrate import calibrate_model
    from catan_coach.models.train import format_comparison

    if not args.model.is_file():
        print(f"No trained model at {args.model}", file=sys.stderr)
        return 1
    if not args.installed.is_file():
        print(f"No trained model at {args.installed}", file=sys.stderr)
        return 1
    try:
        comparison, fit_games, report_games, installed = calibrate_model(
            args.model,
            args.corpus,
            installed_path=args.installed,
            out=args.out,
            seed=args.seed,
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        f"Map fit on {fit_games} validation games. "
        f"Report is the other {report_games}, which the map did not see."
    )
    print(
        format_comparison(
            comparison,
            corpus_path=" + ".join(str(path) for path in args.corpus),
            n_games=report_games,
        )
    )
    if not installed:
        print(f"Left {args.out} unchanged")
        return 1
    print(f"Installed {args.out}")
    return 0


def _fit_mixture(
    paths: list[Path],
    seed: int,
    installed: WinProbabilityModel | None,
    *,
    model_name: str = "gbdt",
) -> tuple[GbdtModel, BaselineComparison, int]:
    from catan_coach.engine.features import public_vp_indices
    from catan_coach.engine.mixture import materialize_mixture
    from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel
    from catan_coach.models.train import compare_matrix, train_matrix

    data = Path("data")
    data.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=data) as directory:
        mixture = materialize_mixture(paths, Path(directory))
        model = train_matrix(mixture.train_features, mixture.train_won, seed=seed, name=model_name)
        comparison = compare_matrix(
            model,
            mixture.validation_features,
            mixture.validation_won,
            constant=ConstantModel(mixture.n_players),
            vp_share=VictoryPointShareModel(public_vp_indices(mixture.n_players)),
            installed=installed,
        )
        return model, comparison, mixture.n_games


def _emit_comparison(
    comparison: BaselineComparison,
    paths: list[Path],
    n_games: int,
    *,
    require_installed: bool,
) -> int:
    from catan_coach.models.train import clears_adoption, format_comparison

    print(
        format_comparison(
            comparison,
            corpus_path=" + ".join(str(path) for path in paths),
            n_games=n_games,
        )
    )
    passed = comparison.beats_constant and comparison.beats_vp_share
    if require_installed:
        passed = clears_adoption(comparison)
    return 0 if passed else 1


def _run_report(args: argparse.Namespace) -> int:
    from catan_coach.engine.corpus import read_corpus
    from catan_coach.models.gbdt import GbdtModel

    if not args.model.is_file():
        print(f"No trained model at {args.model}", file=sys.stderr)
        return 1
    try:
        corpus = read_corpus(args.corpus)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return _print_comparison(corpus, GbdtModel.load(args.model), args.corpus)


def _installed_model(path: Path) -> WinProbabilityModel | int:
    from catan_coach.models.gbdt import GbdtModel

    if not path.is_file():
        print(f"No trained model at {path}", file=sys.stderr)
        return 1
    return GbdtModel.load(path)


def _comparison(
    corpus: Corpus,
    model: WinProbabilityModel,
    installed: WinProbabilityModel | None,
) -> BaselineComparison:
    from catan_coach.engine.features import public_vp_indices
    from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel
    from catan_coach.models.train import compare_to_baselines

    n_players = len({str(seat) for seat in corpus.seats})
    return compare_to_baselines(
        model,
        corpus,
        constant=ConstantModel(n_players),
        vp_share=VictoryPointShareModel(public_vp_indices(n_players)),
        installed=installed,
    )


def _print_comparison(
    corpus: Corpus,
    model: WinProbabilityModel,
    corpus_paths: Path | list[Path],
    *,
    installed: WinProbabilityModel | None = None,
    require_installed: bool = False,
) -> int:
    from catan_coach.models.train import clears_adoption, format_comparison

    paths = corpus_paths if isinstance(corpus_paths, list) else [corpus_paths]
    try:
        comparison = _comparison(corpus, model, installed)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        format_comparison(
            comparison,
            corpus_path=" + ".join(str(path) for path in paths),
            n_games=corpus.n_games,
        )
    )
    passed = comparison.beats_constant and comparison.beats_vp_share
    if require_installed:
        passed = clears_adoption(comparison)
    return 0 if passed else 1
