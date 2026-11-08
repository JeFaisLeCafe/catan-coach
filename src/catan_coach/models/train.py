"""Train a Win Probability model on a Corpus and compare it to the Baselines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np

from catan_coach.domain.calibration import (
    CalibrationReport,
    brier_skill_score,
    calibration_report,
    format_report,
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


def train(corpus: Corpus, *, seed: int = 0) -> GbdtModel:
    mask = corpus.splits == TRAIN
    if not np.any(mask):
        raise ValueError("Corpus has no train games")
    return train_matrix(
        np.asarray(corpus.observations[mask], dtype=np.float64),
        np.asarray(corpus.won[mask], dtype=np.float64),
        seed=seed,
    )


def train_matrix(
    features: np.ndarray, won: np.ndarray, *, seed: int = 0, name: str = "gbdt"
) -> GbdtModel:
    if features.shape[0] == 0:
        raise ValueError("Corpus has no train games")
    params = dict(_PARAMS)
    params["seed"] = seed
    booster = lgb.train(
        params,
        lgb.Dataset(features, label=won, free_raw_data=True),
        num_boost_round=_NUM_BOOST_ROUND,
    )
    return GbdtModel(booster, name=name)


def compare_to_baselines(
    model: WinProbabilityModel,
    corpus: Corpus,
    *,
    constant: WinProbabilityModel,
    vp_share: WinProbabilityModel,
    installed: WinProbabilityModel | None = None,
) -> BaselineComparison:
    features, outcomes = _validation(corpus)
    return compare_matrix(
        model,
        features,
        outcomes,
        constant=constant,
        vp_share=vp_share,
        installed=installed,
    )


def compare_matrix(
    model: WinProbabilityModel,
    features: np.ndarray,
    outcomes: np.ndarray,
    *,
    constant: WinProbabilityModel,
    vp_share: WinProbabilityModel,
    installed: WinProbabilityModel | None = None,
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
) -> BaselineComparison:
    if outcomes.shape[0] == 0:
        raise ValueError("Corpus has no validation games")
    outcomes = np.asarray(outcomes, dtype=np.float64)
    model_report = calibration_report(predicted, outcomes)
    constant_report = calibration_report(constant_predicted, outcomes)
    vp_report = calibration_report(vp_predicted, outcomes)
    skill_vs_constant = brier_skill_score(model_report.brier_score, constant_report.brier_score)
    skill_vs_vp_share = brier_skill_score(model_report.brier_score, vp_report.brier_score)
    installed_result_name = None
    beats_installed = None
    ece_better_than_installed = None
    skill_vs_installed = None
    if installed_predicted is not None and installed_name is not None:
        installed_report = calibration_report(installed_predicted, outcomes)
        installed_result_name = installed_name
        skill_vs_installed = brier_skill_score(
            model_report.brier_score, installed_report.brier_score
        )
        beats_installed = skill_vs_installed > 0.0
        ece_better_than_installed = (
            model_report.expected_calibration_error < installed_report.expected_calibration_error
        )
    return BaselineComparison(
        model_report=model_report,
        constant_report=constant_report,
        vp_share_report=vp_report,
        model_name=model_name,
        constant_name=constant_name,
        vp_share_name=vp_name,
        beats_constant=skill_vs_constant > 0.0,
        beats_vp_share=skill_vs_vp_share > 0.0,
        ece_better_than_vp_share=(
            model_report.expected_calibration_error < vp_report.expected_calibration_error
        ),
        skill_vs_constant=skill_vs_constant,
        skill_vs_vp_share=skill_vs_vp_share,
        installed_name=installed_result_name,
        beats_installed=beats_installed,
        ece_better_than_installed=ece_better_than_installed,
        skill_vs_installed=skill_vs_installed,
    )


def format_comparison(comparison: BaselineComparison, *, corpus_path: str, n_games: int) -> str:
    lines = [
        f"Corpus: {corpus_path}  games: {n_games}",
        format_report(comparison.constant_report, comparison.constant_name),
        format_report(comparison.vp_share_report, comparison.vp_share_name),
        format_report(comparison.model_report, comparison.model_name),
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
    return "\n".join(lines)


def clears_adoption(comparison: BaselineComparison) -> bool:
    """True when a candidate may replace the installed model.

    Brier skill is the adoption score. Calibration error stays in the report
    and is repaired by a monotone map rather than used as a veto.
    """
    return (
        comparison.beats_constant
        and comparison.beats_vp_share
        and comparison.beats_installed is True
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
