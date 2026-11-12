"""Gradient-boosted trees implementing the Win Probability port."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import lightgbm as lgb
import numpy as np

from catan_coach.domain.analysis import Contribution
from catan_coach.domain.prediction import FeatureMatrix, Probabilities
from catan_coach.domain.probability_map import ProbabilityMap
from catan_coach.domain.reasons import top_contributions


class GbdtModel:
    def __init__(
        self,
        booster: lgb.Booster,
        name: str = "gbdt",
        feature_names: Sequence[str] | None = None,
        probability_map: ProbabilityMap | None = None,
    ) -> None:
        self._booster = booster
        self._name = name
        self._feature_names = tuple(feature_names) if feature_names is not None else None
        self._probability_map = probability_map

    @property
    def name(self) -> str:
        return self._name

    @property
    def width(self) -> int:
        return int(self._booster.num_feature())

    @property
    def probability_map(self) -> ProbabilityMap | None:
        return self._probability_map

    def with_probability_map(self, probability_map: ProbabilityMap) -> GbdtModel:
        return GbdtModel(
            self._booster,
            name=self._name,
            feature_names=self._feature_names,
            probability_map=probability_map,
        )

    def without_probability_map(self) -> GbdtModel:
        return GbdtModel(self._booster, name=self._name, feature_names=self._feature_names)

    def predict(self, features: FeatureMatrix) -> Probabilities:
        matrix = self._aligned(features)
        predicted = np.clip(np.asarray(self._booster.predict(matrix), dtype=np.float64), 0.0, 1.0)
        if self._probability_map is None:
            return predicted
        return self._probability_map.apply(predicted)

    def explain(self, features: FeatureMatrix) -> tuple[tuple[Contribution, ...], ...]:
        matrix = self._aligned(features)
        if self._feature_names is None:
            return tuple(() for _ in range(matrix.shape[0]))
        raw = np.asarray(self._booster.predict(matrix, pred_contrib=True), dtype=np.float64)
        names = self._feature_names
        if len(names) > matrix.shape[1]:
            names = names[: matrix.shape[1]]
        if raw.shape[1] - 1 != len(names):
            raise ValueError("Observation names do not match the trained model")
        return tuple(top_contributions(row[:-1], names) for row in raw)

    def _aligned(self, features: FeatureMatrix) -> np.ndarray:
        """Keep the prefix this booster was trained on.

        Observation columns are appended, so a wider matrix is still scored
        by an older model. A narrower matrix cannot be.
        """
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2:
            raise ValueError(f"expected a 2-D feature matrix, got shape {matrix.shape}")
        trained = self.width
        columns = int(matrix.shape[1])
        if columns < trained:
            raise ValueError(
                f"feature matrix has {columns} columns but the model expects {trained}"
            )
        if columns > trained:
            return matrix[:, :trained]
        return matrix

    def save(self, path: Path | str) -> None:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(dest))
        write_probability_map(dest, self._probability_map)

    @classmethod
    def load(
        cls,
        path: Path | str,
        name: str = "gbdt",
        feature_names: Sequence[str] | None = None,
    ) -> GbdtModel:
        dest = Path(path)
        booster = lgb.Booster(model_file=str(dest))
        sidecar = calibration_sidecar(dest)
        probability_map = None
        if sidecar.is_file():
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            probability_map = ProbabilityMap.from_json_knots(payload["knots"])
        return cls(
            booster,
            name=name,
            feature_names=feature_names,
            probability_map=probability_map,
        )


def calibration_sidecar(path: Path | str) -> Path:
    dest = Path(path)
    return dest.with_name(f"{dest.stem}.calibration.json")


def write_probability_map(path: Path | str, probability_map: ProbabilityMap | None) -> None:
    """Store knots beside the LightGBM file. The tree file is not rewritten."""
    sidecar = calibration_sidecar(path)
    if probability_map is None:
        sidecar.unlink(missing_ok=True)
        return
    sidecar.write_text(
        json.dumps({"knots": probability_map.to_json_knots()}) + "\n",
        encoding="utf-8",
    )
