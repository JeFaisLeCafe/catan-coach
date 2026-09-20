"""Train a Win Probability model on a Corpus and compare it to the Baselines."""

from __future__ import annotations

from dataclasses import dataclass

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


def train(corpus: Corpus, *, seed: int = 0) -> GbdtModel:
    mask = corpus.splits == TRAIN
    if not np.any(mask):
        raise ValueError("Corpus has no train games")
    features = np.asarray(corpus.observations[mask], dtype=np.float64)
    won = np.asarray(corpus.won[mask], dtype=np.float64)
    params = dict(_PARAMS)
    params["seed"] = seed
    booster = lgb.train(
        params,
        lgb.Dataset(features, label=won, free_raw_data=False),
        num_boost_round=_NUM_BOOST_ROUND,
    )
    return GbdtModel(booster)


def compare_to_baselines(
    model: WinProbabilityModel,
    corpus: Corpus,
    *,
    constant: WinProbabilityModel,
    vp_share: WinProbabilityModel,
) -> BaselineComparison:
    features, outcomes = _validation(corpus)
    model_report = calibration_report(model.predict(features), outcomes)
    constant_report = calibration_report(constant.predict(features), outcomes)
    vp_report = calibration_report(vp_share.predict(features), outcomes)
    skill_vs_constant = brier_skill_score(model_report.brier_score, constant_report.brier_score)
    skill_vs_vp_share = brier_skill_score(model_report.brier_score, vp_report.brier_score)
    return BaselineComparison(
        model_report=model_report,
        constant_report=constant_report,
        vp_share_report=vp_report,
        model_name=model.name,
        constant_name=constant.name,
        vp_share_name=vp_share.name,
        beats_constant=skill_vs_constant > 0.0,
        beats_vp_share=skill_vs_vp_share > 0.0,
        ece_better_than_vp_share=(
            model_report.expected_calibration_error < vp_report.expected_calibration_error
        ),
        skill_vs_constant=skill_vs_constant,
        skill_vs_vp_share=skill_vs_vp_share,
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
    return "\n".join(lines)


def _verdict(passed: bool, model_name: str, baseline_name: str, metric: str) -> str:
    if passed:
        return f"{model_name} beats {baseline_name} on {metric}"
    return f"{model_name} does not beat {baseline_name} on {metric}"


def _validation(corpus: Corpus) -> tuple[np.ndarray, np.ndarray]:
    mask = corpus.splits == VALIDATION
    if not np.any(mask):
        raise ValueError("Corpus has no validation games")
    return (
        np.asarray(corpus.observations[mask], dtype=np.float64),
        np.asarray(corpus.won[mask], dtype=np.float64),
    )
