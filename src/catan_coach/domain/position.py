"""A Position and the Actions a Seat may take from it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

Observation = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Seat:
    name: str


@dataclass(frozen=True, slots=True)
class Action:
    label: str


@runtime_checkable
class Position(Protocol):
    """A complete game state that play can resume from."""

    @property
    def seat_to_act(self) -> Seat: ...

    def legal_actions(self) -> tuple[Action, ...]: ...

    def observation_after(self, action: Action) -> Observation: ...
