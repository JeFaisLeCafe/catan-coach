"""Fit a monotone map on held-out games and judge it on the games it did not see."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.domain.probability_map import ProbabilityMap, calibration_half, fit_probability_map
from catan_coach.engine.features import public_vp_indices
from catan_coach.engine.mixture import iter_validation_games, player_count
from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel
from catan_coach.models.gbdt import GbdtModel, write_probability_map
from catan_coach.models.train import (
    BaselineComparison,
    clears_adoption,
    compare_predictions,
)

_PREDICT_BATCH = 8192


@dataclass(frozen=True, slots=True)
class _Halves:
    fit_predicted: np.ndarray
    fit_won: np.ndarray
    fit_games: int
    report_raw: np.ndarray
    report_won: np.ndarray
    report_vp: np.ndarray
    report_installed: np.ndarray
    report_game_ids: np.ndarray
    report_priors: tuple[np.ndarray, ...]
    report_games: int


def calibrate_model(
    model_path: Path | str,
    corpora: Sequence[Path | str],
    *,
    installed_path: Path | str,
    out: Path | str,
    seed: int = 0,
    prior_paths: Sequence[Path | str] = (),
    keep_map: bool = False,
) -> tuple[BaselineComparison, int, int, bool]:
    """Fit the map for `model_path` and copy it onto `out` only if Brier clears.

    Predictions are kept; Observations are dropped after each game. The report
    half supplies one Brier score per game, so each reference must clear a
    game-level 95% interval. `prior_paths` are extra models besides
    `installed_path`; a CLI flag can forward paths here without any other
    change. Returns the untouched-half report, how many games were fit, how
    many were reported, and whether `out` was replaced.

    `keep_map` also writes the fitted map beside `model_path`, whether or not
    Brier clears, so a candidate that fails the gate can still be played. It
    refuses when `model_path` is `out` or the installed model.
    """
    if keep_map:
        candidate = Path(model_path).resolve()
        if candidate in (Path(out).resolve(), Path(installed_path).resolve()):
            raise ValueError("keeping the map would rewrite the installed model's sidecar")
    trees = GbdtModel.load(model_path, name="candidate").without_probability_map()
    installed = GbdtModel.load(installed_path, name="installed")
    prior_models = tuple(GbdtModel.load(path, name=Path(path).stem) for path in prior_paths)
    n_players = player_count(corpora)
    constant = ConstantModel(n_players)
    vp_share = VictoryPointShareModel(public_vp_indices(n_players))
    halves = _score_halves(corpora, trees, installed, vp_share, priors=prior_models, seed=seed)
    mapping = fit_probability_map(halves.fit_predicted, halves.fit_won)
    mapped = trees.with_probability_map(mapping)
    comparison = compare_predictions(
        mapping.apply(halves.report_raw),
        halves.report_won,
        model_name=mapped.name,
        constant_predicted=np.full(halves.report_won.shape[0], 1.0 / n_players),
        constant_name=constant.name,
        vp_predicted=halves.report_vp,
        vp_name=vp_share.name,
        installed_predicted=halves.report_installed,
        installed_name=installed.name,
        priors=tuple(
            (model.name, predicted)
            for model, predicted in zip(prior_models, halves.report_priors, strict=True)
        ),
        game_ids=halves.report_game_ids,
    )
    if keep_map:
        write_probability_map(model_path, mapping)
    replaced = False
    if clears_adoption(comparison):
        _publish(Path(model_path), Path(out), mapping)
        replaced = True
    return comparison, halves.fit_games, halves.report_games, replaced


def _score_halves(
    corpora: Sequence[Path | str],
    trees: WinProbabilityModel,
    installed: WinProbabilityModel,
    vp_share: WinProbabilityModel,
    *,
    priors: Sequence[WinProbabilityModel] = (),
    seed: int,
) -> _Halves:
    fit_predicted: list[np.ndarray] = []
    fit_won: list[np.ndarray] = []
    fit_games: set[int] = set()
    report_raw: list[np.ndarray] = []
    report_won: list[np.ndarray] = []
    report_vp: list[np.ndarray] = []
    report_installed: list[np.ndarray] = []
    report_game_ids: list[np.ndarray] = []
    report_prior_rows: list[list[np.ndarray]] = [[] for _ in priors]
    report_games: set[int] = set()
    next_game = 0
    for game in iter_validation_games(corpora):
        raw = _predict(trees, game.features)
        key = game.corpus_index * 1_000_003 + game.game_id
        if calibration_half(game.game_id, seed=seed, source=game.corpus_index) == "fit":
            fit_predicted.append(raw)
            fit_won.append(game.won)
            fit_games.add(key)
        else:
            report_raw.append(raw)
            report_won.append(game.won)
            report_vp.append(_predict(vp_share, game.features))
            report_installed.append(_predict(installed, game.features))
            report_game_ids.append(np.full(raw.shape[0], next_game, dtype=np.int64))
            for index, prior in enumerate(priors):
                report_prior_rows[index].append(_predict(prior, game.features))
            report_games.add(key)
            next_game += 1
    if not fit_predicted or not report_raw:
        raise ValueError("validation games did not cover both the map fit and the report")
    return _Halves(
        fit_predicted=np.concatenate(fit_predicted),
        fit_won=np.concatenate(fit_won),
        fit_games=len(fit_games),
        report_raw=np.concatenate(report_raw),
        report_won=np.concatenate(report_won),
        report_vp=np.concatenate(report_vp),
        report_installed=np.concatenate(report_installed),
        report_game_ids=np.concatenate(report_game_ids),
        report_priors=tuple(np.concatenate(rows) for rows in report_prior_rows),
        report_games=len(report_games),
    )


def _predict(model: WinProbabilityModel, features: np.ndarray) -> np.ndarray:
    count = int(features.shape[0])
    if count <= _PREDICT_BATCH:
        return np.asarray(model.predict(features), dtype=np.float64)
    return np.concatenate(
        [
            np.asarray(model.predict(features[start : start + _PREDICT_BATCH]), dtype=np.float64)
            for start in range(0, count, _PREDICT_BATCH)
        ]
    )


def _publish(source: Path, dest: Path, mapping: ProbabilityMap) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != dest.resolve():
        shutil.copyfile(source, dest)
    write_probability_map(dest, mapping)
