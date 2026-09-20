"""Rank the legal Actions in a Position by Win Probability."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from catan_coach.domain.position import Action, Position, Seat
from catan_coach.domain.prediction import WinProbabilityModel


@dataclass(frozen=True, slots=True)
class RankedAction:
    action: Action
    win_probability: float
    loss: float


@dataclass(frozen=True, slots=True)
class Analysis:
    seat: Seat
    ranked: tuple[RankedAction, ...]

    @property
    def is_forced(self) -> bool:
        return len(self.ranked) == 1


def analyze(position: Position, model: WinProbabilityModel) -> Analysis:
    """Score every legal Action in one batched call to `model`.

    Actions that share a Win Probability are ordered by Action label
    (ascending) so the ranking is total and reproducible.
    """
    actions = position.legal_actions()
    observations = np.vstack([position.observation_after(action) for action in actions])
    win_probabilities = model.predict(observations)
    best = float(np.max(win_probabilities))
    ranked = sorted(
        (
            RankedAction(
                action=action,
                win_probability=float(probability),
                loss=best - float(probability),
            )
            for action, probability in zip(actions, win_probabilities, strict=True)
        ),
        key=lambda row: (-row.win_probability, row.action.label),
    )
    return Analysis(seat=position.seat_to_act, ranked=tuple(ranked))
