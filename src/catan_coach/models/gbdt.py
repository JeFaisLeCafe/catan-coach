"""Gradient-boosted trees implementing the Win Probability port."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import lightgbm as lgb
import numpy as np

from catan_coach.domain.analysis import Contribution
from catan_coach.domain.prediction import FeatureMatrix, Probabilities
from catan_coach.domain.reasons import top_contributions


class GbdtModel:
    def __init__(
        self,
        booster: lgb.Booster,
        name: str = "gbdt",
        feature_names: Sequence[str] | None = None,
    ) -> None:
        self._booster = booster
        self._name = name
        self._feature_names = tuple(feature_names) if feature_names is not None else None

    @property
    def name(self) -> str:
        return self._name

    def predict(self, features: FeatureMatrix) -> Probabilities:
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2:
            raise ValueError(f"expected a 2-D feature matrix, got shape {matrix.shape}")
        predicted = np.asarray(self._booster.predict(matrix), dtype=np.float64)
        return np.clip(predicted, 0.0, 1.0)

    def explain(self, features: FeatureMatrix) -> tuple[tuple[Contribution, ...], ...]:
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2:
            raise ValueError(f"expected a 2-D feature matrix, got shape {matrix.shape}")
        if self._feature_names is None:
            return tuple(() for _ in range(matrix.shape[0]))
        raw = np.asarray(self._booster.predict(matrix, pred_contrib=True), dtype=np.float64)
        names = self._feature_names
        if raw.shape[1] - 1 != len(names):
            raise ValueError("Observation names do not match the trained model")
        return tuple(top_contributions(row[:-1], names) for row in raw)

    def save(self, path: Path | str) -> None:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(dest))

    @classmethod
    def load(
        cls,
        path: Path | str,
        name: str = "gbdt",
        feature_names: Sequence[str] | None = None,
    ) -> GbdtModel:
        booster = lgb.Booster(model_file=str(path))
        return cls(booster, name=name, feature_names=feature_names)
