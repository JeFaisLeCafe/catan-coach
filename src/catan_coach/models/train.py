"""Train a Win Probability model on a Corpus and compare it to the Baselines."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np

from catan_coach.domain.calibration import (
    CalibrationReport,
    GameBrierInterval,
    brier_skill_score,
    calibration_report,
    format_report,
    game_brier_difference,
    reference_cleared,
)
from catan_coach.domain.corpus import TRAIN, VALIDATION, Corpus
from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.models.gbdt import GbdtModel

_NUM_BOOST_ROUND = 80
_PARAMS: dict[str, object] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "verbosity": -1,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 8,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
}


@dataclass(frozen=True, slots=True)
class PriorComparison:
    """One supplied model the candidate has to clear, besides the two baselines."""

    name: str
    skill: float
    beats: bool
    ece_better: bool
    interval: GameBrierInterval | None = None


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    model_report: CalibrationReport
    constant_report: CalibrationReport
    vp_share_report: CalibrationReport
    model_name: str
    constant_name: str
    vp_share_name: str
    beats_constant: bool
    beats_vp_share: bool
    ece_better_than_vp_share: bool
    skill_vs_constant: float
    skill_vs_vp_share: float
    installed_name: str | None = None
    beats_installed: bool | None = None
    ece_better_than_installed: bool | None = None
    skill_vs_installed: float | None = None
    constant_interval: GameBrierInterval | None = None
    vp_share_interval: GameBrierInterval | None = None
    installed_interval: GameBrierInterval | None = None
    priors: tuple[PriorComparison, ...] = ()


def train(
    corpus: Corpus,
    *,
    seed: int = 0,
    masked_columns: Sequence[int] = (),
) -> GbdtModel:
    mask = corpus.splits == TRAIN
    if not np.any(mask):
        raise ValueError("Corpus has no train games")
    return train_matrix(
        np.asarray(corpus.observations[mask], dtype=np.float64),
        np.asarray(corpus.won[mask], dtype=np.float64),
        seed=seed,
        masked_columns=masked_columns,
    )


def train_matrix(
    features: np.ndarray,
    won: np.ndarray,
    *,
    seed: int = 0,
    name: str = "gbdt",
    masked_columns: Sequence[int] = (),
    rounds: int = _NUM_BOOST_ROUND,
    leaves: int | None = None,
) -> GbdtModel:
    if features.shape[0] == 0:
        raise ValueError("Corpus has no train games")
    training_features = features
    if len(masked_columns) > 0:
        training_features = _mask_columns(features, masked_columns)
    params = dict(_PARAMS)
    params["seed"] = seed
    if leaves is not None:
        params["num_leaves"] = leaves
    if rounds < 1:
        raise ValueError("rounds must be at least 1")
    booster = lgb.train(
        params,
        lgb.Dataset(training_features, label=won, free_raw_data=True),
        num_boost_round=rounds,
    )
    return GbdtModel(booster, name=name)


def _mask_columns(features: np.ndarray, masked_columns: Sequence[int]) -> np.ndarray:
    """Zero columns on a float32 copy so trees never split on them."""
    n_columns = int(features.shape[1])
    columns = tuple(int(column) for column in masked_columns)
    for column in columns:
        if column < 0 or column >= n_columns:
            raise ValueError(f"masked column {column} is outside the {n_columns} training columns")
    masked = np.array(features, dtype=np.float32, copy=True)
    masked[:, columns] = np.float32(0.0)
    return masked


def compare_to_baselines(
    model: WinProbabilityModel,
    corpus: Corpus,
    *,
    constant: WinProbabilityModel,
    vp_share: WinProbabilityModel,
    installed: WinProbabilityModel | None = None,
    priors: Sequence[WinProbabilityModel] = (),
    game_ids: np.ndarray | None = None,
    bootstrap_seed: int = 0,
) -> BaselineComparison:
    """Score `model` on the validation split.

    `priors` are models in addition to `installed`. Pass `game_ids` aligned
    with the validation rows to judge every reference by a game-level 95%
    interval; omit them to keep the row-level point estimate.
    """
    features, outcomes = _validation(corpus)
    return compare_matrix(
        model,
        features,
        outcomes,
        constant=constant,
        vp_share=vp_share,
        installed=installed,
        priors=priors,
        game_ids=game_ids,
        bootstrap_seed=bootstrap_seed,
    )


def compare_matrix(
    model: WinProbabilityModel,
    features: np.ndarray,
    outcomes: np.ndarray,
    *,
    constant: WinProbabilityModel,
    vp_share: WinProbabilityModel,
    installed: WinProbabilityModel | None = None,
    priors: Sequence[WinProbabilityModel] = (),
    game_ids: np.ndarray | None = None,
    bootstrap_seed: int = 0,
) -> BaselineComparison:
    if features.shape[0] == 0:
        raise ValueError("Corpus has no validation games")
    outcomes = np.asarray(outcomes, dtype=np.float64)
    return compare_predictions(
        _predict(model, features),
        outcomes,
        model_name=model.name,
        constant_predicted=_predict(constant, features),
        constant_name=constant.name,
        vp_predicted=_predict(vp_share, features),
        vp_name=vp_share.name,
        installed_predicted=None if installed is None else _predict(installed, features),
        installed_name=None if installed is None else installed.name,
        priors=tuple((prior.name, _predict(prior, features)) for prior in priors),
        game_ids=game_ids,
        bootstrap_seed=bootstrap_seed,
    )


def compare_predictions(
    predicted: np.ndarray,
    outcomes: np.ndarray,
    *,
    model_name: str,
    constant_predicted: np.ndarray,
    constant_name: str,
    vp_predicted: np.ndarray,
    vp_name: str,
    installed_predicted: np.ndarray | None = None,
    installed_name: str | None = None,
    priors: Sequence[tuple[str, np.ndarray]] = (),
    game_ids: np.ndarray | None = None,
    bootstrap_seed: int = 0,
) -> BaselineComparison:
    if outcomes.shape[0] == 0:
        raise ValueError("Corpus has no validation games")
    outcomes = np.asarray(outcomes, dtype=np.float64)
    ids = None if game_ids is None else np.asarray(game_ids, dtype=np.int64).reshape(-1)
    candidate_games, weights = (
        (None, None) if ids is None else _game_briers(predicted, outcomes, ids)
    )
    model_report = calibration_report(predicted, outcomes)
    constant_report = calibration_report(constant_predicted, outcomes)
    vp_report = calibration_report(vp_predicted, outcomes)
    skill_vs_constant = brier_skill_score(model_report.brier_score, constant_report.brier_score)
    skill_vs_vp_share = brier_skill_score(model_report.brier_score, vp_report.brier_score)
    constant_interval = _interval(
        candidate_games, weights, constant_predicted, outcomes, ids, bootstrap_seed
    )
    vp_share_interval = _interval(
        candidate_games, weights, vp_predicted, outcomes, ids, bootstrap_seed
    )
    installed_result_name = None
    beats_installed = None
    ece_better_than_installed = None
    skill_vs_installed = None
    installed_interval = None
    if installed_predicted is not None and installed_name is not None:
        installed_report = calibration_report(installed_predicted, outcomes)
        installed_result_name = installed_name
        skill_vs_installed = brier_skill_score(
            model_report.brier_score, installed_report.brier_score
        )
        installed_interval = _interval(
            candidate_games, weights, installed_predicted, outcomes, ids, bootstrap_seed
        )
        beats_installed = _beats(skill_vs_installed, installed_interval)
        ece_better_than_installed = (
            model_report.expected_calibration_error < installed_report.expected_calibration_error
        )
    prior_comparisons: list[PriorComparison] = []
    for name, prior_predicted in priors:
        prior_values = np.asarray(prior_predicted, dtype=np.float64)
        prior_report = calibration_report(prior_values, outcomes)
        skill = brier_skill_score(model_report.brier_score, prior_report.brier_score)
        gap = _interval(candidate_games, weights, prior_values, outcomes, ids, bootstrap_seed)
        prior_comparisons.append(
            PriorComparison(
                name=name,
                skill=skill,
                beats=_beats(skill, gap),
                ece_better=(
                    model_report.expected_calibration_error
                    < prior_report.expected_calibration_error
                ),
                interval=gap,
            )
        )
    return BaselineComparison(
        model_report=model_report,
        constant_report=constant_report,
        vp_share_report=vp_report,
        model_name=model_name,
        constant_name=constant_name,
        vp_share_name=vp_name,
        beats_constant=_beats(skill_vs_constant, constant_interval),
        beats_vp_share=_beats(skill_vs_vp_share, vp_share_interval),
        ece_better_than_vp_share=(
            model_report.expected_calibration_error < vp_report.expected_calibration_error
        ),
        skill_vs_constant=skill_vs_constant,
        skill_vs_vp_share=skill_vs_vp_share,
        installed_name=installed_result_name,
        beats_installed=beats_installed,
        ece_better_than_installed=ece_better_than_installed,
        skill_vs_installed=skill_vs_installed,
        constant_interval=constant_interval,
        vp_share_interval=vp_share_interval,
        installed_interval=installed_interval,
        priors=tuple(prior_comparisons),
    )


def format_comparison(comparison: BaselineComparison, *, corpus_path: str, n_games: int) -> str:
    lines = [
        f"Corpus: {corpus_path}  games: {n_games}",
        format_report(comparison.constant_report, comparison.constant_name),
        format_report(comparison.vp_share_report, comparison.vp_share_name),
        _report_with_intervals(comparison),
        "",
        (
            f"Discrimination: Brier skill vs {comparison.constant_name} = "
            f"{comparison.skill_vs_constant:+.3f}"
        ),
        (
            f"Discrimination: Brier skill vs {comparison.vp_share_name} = "
            f"{comparison.skill_vs_vp_share:+.3f}"
        ),
        "",
        _verdict(
            comparison.beats_constant,
            comparison.model_name,
            comparison.constant_name,
            "Brier skill",
        ),
        _verdict(
            comparison.beats_vp_share,
            comparison.model_name,
            comparison.vp_share_name,
            "Brier skill",
        ),
        _verdict(
            comparison.ece_better_than_vp_share,
            comparison.model_name,
            comparison.vp_share_name,
            "Calibration error",
        ),
    ]
    if comparison.installed_name is not None and comparison.skill_vs_installed is not None:
        lines.extend(
            [
                "",
                (
                    f"Discrimination: Brier skill vs {comparison.installed_name} = "
                    f"{comparison.skill_vs_installed:+.3f}"
                ),
                _verdict(
                    comparison.beats_installed is True,
                    comparison.model_name,
                    comparison.installed_name,
                    "Brier skill",
                ),
                _verdict(
                    comparison.ece_better_than_installed is True,
                    comparison.model_name,
                    comparison.installed_name,
                    "Calibration error",
                ),
            ]
        )
    for prior in comparison.priors:
        lines.extend(
            [
                "",
                (f"Discrimination: Brier skill vs {prior.name} = {prior.skill:+.3f}"),
                _verdict(prior.beats, comparison.model_name, prior.name, "Brier skill"),
                _verdict(
                    prior.ece_better,
                    comparison.model_name,
                    prior.name,
                    "Calibration error",
                ),
            ]
        )
    return "\n".join(lines)


def clears_adoption(comparison: BaselineComparison) -> bool:
    """True when a candidate may replace the installed model.

    Brier skill is the adoption score. With per-game scores, each reference
    must clear a game-level 95% interval; otherwise the point estimate must
    be positive. Every supplied prior has to clear, including the installed
    model. Calibration error stays in the report and is not a veto.
    """
    return (
        _cleared(comparison.beats_constant, comparison.constant_interval)
        and _cleared(comparison.beats_vp_share, comparison.vp_share_interval)
        and _cleared(comparison.beats_installed, comparison.installed_interval)
        and all(_cleared(prior.beats, prior.interval) for prior in comparison.priors)
    )


def install_candidate(
    candidate: Path,
    installed: Path,
    comparison: BaselineComparison,
) -> bool:
    """Copy `candidate` onto `installed` only when the adoption bars are cleared.

    A failed candidate stays where it was written. The installed file is left
    untouched, including when the two paths are the same.
    """
    if candidate.resolve() == installed.resolve():
        raise ValueError("refusing to replace the installed model with itself")
    if not clears_adoption(comparison):
        return False
    installed.parent.mkdir(parents=True, exist_ok=True)
    installed.write_bytes(candidate.read_bytes())
    _copy_sidecar(candidate, installed)
    return True


def _copy_sidecar(source: Path, dest: Path) -> None:
    from catan_coach.models.gbdt import calibration_sidecar

    src = calibration_sidecar(source)
    dst = calibration_sidecar(dest)
    if src.is_file():
        dst.write_bytes(src.read_bytes())
    elif dst.is_file():
        dst.unlink()


def _cleared(beats: bool | None, interval: GameBrierInterval | None) -> bool:
    if interval is not None:
        return reference_cleared(interval)
    return beats is True


def _beats(skill: float, interval: GameBrierInterval | None) -> bool:
    if interval is None:
        return skill > 0.0
    return reference_cleared(interval)


def _interval(
    candidate_games: np.ndarray | None,
    weights: np.ndarray | None,
    reference_predicted: np.ndarray,
    outcomes: np.ndarray,
    game_ids: np.ndarray | None,
    seed: int,
) -> GameBrierInterval | None:
    if candidate_games is None or weights is None or game_ids is None:
        return None
    reference_games, _ = _game_briers(reference_predicted, outcomes, game_ids)
    return game_brier_difference(candidate_games, reference_games, weights, seed=seed)


def _game_briers(
    predicted: np.ndarray,
    outcomes: np.ndarray,
    game_ids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    scores = np.asarray(predicted, dtype=np.float64).reshape(-1)
    actual = np.asarray(outcomes, dtype=np.float64).reshape(-1)
    ids = np.asarray(game_ids, dtype=np.int64).reshape(-1)
    if scores.shape != actual.shape or scores.shape != ids.shape:
        raise ValueError(
            "predicted, outcomes, and game ids differ in length: "
            f"{scores.size}, {actual.size}, {ids.size}"
        )
    if scores.size == 0:
        raise ValueError("need at least one game")
    order = np.argsort(ids, kind="mergesort")
    ordered_ids = ids[order]
    squared = (scores[order] - actual[order]) ** 2
    boundaries = np.flatnonzero(np.diff(ordered_ids)) + 1
    starts = np.concatenate((np.array([0], dtype=np.int64), boundaries))
    weights = np.diff(np.append(starts, ordered_ids.size)).astype(np.float64)
    return np.add.reduceat(squared, starts) / weights, weights


def _report_with_intervals(comparison: BaselineComparison) -> str:
    text = format_report(comparison.model_report, comparison.model_name)
    intervals = _interval_lines(comparison)
    if not intervals:
        return text
    header, _, rest = text.partition("\n")
    return "\n".join([header, *intervals, rest])


def _interval_lines(comparison: BaselineComparison) -> list[str]:
    paired: list[tuple[str, GameBrierInterval | None]] = [
        (comparison.constant_name, comparison.constant_interval),
        (comparison.vp_share_name, comparison.vp_share_interval),
    ]
    if comparison.installed_name is not None:
        paired.append((comparison.installed_name, comparison.installed_interval))
    paired.extend((prior.name, prior.interval) for prior in comparison.priors)
    return [_format_interval(name, gap) for name, gap in paired if gap is not None]


def _format_interval(name: str, interval: GameBrierInterval) -> str:
    return (
        f"brier difference, candidate minus {name}: {interval.point:+.4f}  "
        f"95% [{interval.lower:+.4f}, {interval.upper:+.4f}]"
    )


def _verdict(passed: bool, model_name: str, baseline_name: str, metric: str) -> str:
    if passed:
        return f"{model_name} beats {baseline_name} on {metric}"
    return f"{model_name} does not beat {baseline_name} on {metric}"


def _predict(model: WinProbabilityModel, features: np.ndarray) -> np.ndarray:
    """Score in batches so a large Corpus is not copied into one float64 block."""
    count = int(features.shape[0])
    batch = 8192
    if count <= batch:
        return model.predict(features)
    return np.concatenate(
        [model.predict(features[start : start + batch]) for start in range(0, count, batch)]
    )


def _validation(corpus: Corpus) -> tuple[np.ndarray, np.ndarray]:
    mask = corpus.splits == VALIDATION
    if not np.any(mask):
        raise ValueError("Corpus has no validation games")
    return (
        np.asarray(corpus.observations[mask], dtype=np.float64),
        np.asarray(corpus.won[mask], dtype=np.float64),
    )
