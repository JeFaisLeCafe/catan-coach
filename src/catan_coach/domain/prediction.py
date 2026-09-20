"""The port every win-probability estimator implements."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

FeatureMatrix = NDArray[np.float64]
Probabilities = NDArray[np.float64]


@runtime_checkable
class WinProbabilityModel(Protocol):
    """Estimates P(the perspective player wins) for a batch of positions.

    Batched by design: the analyzer scores every legal action in a position at
    once, which for a learned model is a single forward pass.
    """

    @property
    def name(self) -> str: ...

    def predict(self, features: FeatureMatrix) -> Probabilities: ...
