"""Reference models the learned one has to beat.

`Constant` is the no-information floor. `VictoryPointShare` is the
obvious-information bar: it knows only the public score. A learned model that
cannot beat it has learned nothing beyond "who is ahead".

Both are pure. Feature positions are injected rather than looked up, so these
are testable without the engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from catan_coach.domain.prediction import FeatureMatrix, Probabilities


def _validate(features: FeatureMatrix) -> FeatureMatrix:
    matrix = np.asarray(features, dtype=np.float64)
    if matrix.ndim != 2:
        raise ValueError(f"expected a 2-D feature matrix, got shape {matrix.shape}")
    return matrix


@dataclass(frozen=True, slots=True)
class ConstantModel:
    """Always predicts an equal share of the table."""

    num_players: int

    def __post_init__(self) -> None:
        if self.num_players < 2:
            raise ValueError("num_players must be at least 2")

    @property
    def name(self) -> str:
        return f"constant(1/{self.num_players})"

    def predict(self, features: FeatureMatrix) -> Probabilities:
        matrix = _validate(features)
        return np.full(matrix.shape[0], 1.0 / self.num_players, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class VictoryPointShareModel:
    """Softmax over public victory points.

    `public_vp_indices[0]` must be the perspective player's column; the rest are
    opponents, in any order. `temperature` is deliberately unfitted - this is a
    bar to clear, not a candidate.
    """

    public_vp_indices: Sequence[int]
    temperature: float = 2.0

    def __post_init__(self) -> None:
        if len(self.public_vp_indices) < 2:
            raise ValueError("need the perspective player plus at least one opponent")
        if self.temperature <= 0.0:
            raise ValueError("temperature must be positive")

    @property
    def name(self) -> str:
        return f"vp-share(T={self.temperature})"

    def predict(self, features: FeatureMatrix) -> Probabilities:
        matrix = _validate(features)
        vps = matrix[:, list(self.public_vp_indices)] / self.temperature
        stabilised = np.exp(vps - vps.max(axis=1, keepdims=True))
        return np.asarray(stabilised[:, 0] / stabilised.sum(axis=1), dtype=np.float64)
