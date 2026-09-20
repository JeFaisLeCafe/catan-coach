"""Rank the legal Actions in a Position by Win Probability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from catan_coach.domain.position import Action, Position, Seat
from catan_coach.domain.prediction import FeatureMatrix, WinProbabilityModel


@dataclass(frozen=True, slots=True)
class Contribution:
    label: str
    delta: float


@dataclass(frozen=True, slots=True)
class RankedAction:
    action: Action
    win_probability: float
    loss: float
    reasons: tuple[Contribution, ...] = ()


@dataclass(frozen=True, slots=True)
class Analysis:
    seat: Seat
    ranked: tuple[RankedAction, ...]

    @property
    def is_forced(self) -> bool:
        return len(self.ranked) == 1


@runtime_checkable
class ExplainingModel(WinProbabilityModel, Protocol):
    def explain(self, features: FeatureMatrix) -> tuple[tuple[Contribution, ...], ...]: ...


def analyze(position: Position, model: WinProbabilityModel) -> Analysis:
    """Score every legal Action in one batched call to `model`.

    Actions that share a Win Probability are ordered by Action label
    (ascending) so the ranking is total and reproducible.
    """
    actions = position.legal_actions()
    observations = np.vstack([position.observation_after(action) for action in actions])
    win_probabilities = model.predict(observations)
    explanations: tuple[tuple[Contribution, ...], ...]
    if isinstance(model, ExplainingModel):
        explanations = model.explain(observations)
        if len(explanations) != len(actions):
            raise ValueError("explain() must return one reason list per Action")
    else:
        explanations = tuple(() for _ in actions)
    by_label = {
        action.label: (float(probability), reasons)
        for action, probability, reasons in zip(
            actions, win_probabilities, explanations, strict=True
        )
    }
    best = max(probability for probability, _ in by_label.values())
    ranked = sorted(
        (
            RankedAction(
                action=action,
                win_probability=by_label[action.label][0],
                loss=best - by_label[action.label][0],
                reasons=by_label[action.label][1],
            )
            for action in actions
        ),
        key=lambda row: (-row.win_probability, row.action.label),
    )
    return Analysis(seat=position.seat_to_act, ranked=tuple(ranked))
