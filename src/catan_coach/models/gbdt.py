"""Gradient-boosted trees implementing the Win Probability port."""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np

from catan_coach.domain.prediction import FeatureMatrix, Probabilities


class GbdtModel:
    def __init__(self, booster: lgb.Booster, name: str = "gbdt") -> None:
        self._booster = booster
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def predict(self, features: FeatureMatrix) -> Probabilities:
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2:
            raise ValueError(f"expected a 2-D feature matrix, got shape {matrix.shape}")
        predicted = np.asarray(self._booster.predict(matrix), dtype=np.float64)
        return np.clip(predicted, 0.0, 1.0)

    def save(self, path: Path | str) -> None:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(dest))

    @classmethod
    def load(cls, path: Path | str, name: str = "gbdt") -> GbdtModel:
        booster = lgb.Booster(model_file=str(path))
        return cls(booster, name=name)
