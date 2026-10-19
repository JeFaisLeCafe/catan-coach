"""Blunder Report: Loss of each non-forced human Action in a game."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from catan_coach.domain.analysis import Contribution, analyze
from catan_coach.domain.position import Action, Position
from catan_coach.domain.prediction import WinProbabilityModel

# A gap of 1 point of Win Probability is a near-tie, matching the CLI.
NEAR_TIE_LOSS = 0.01
# A Loss above 10 points of Win Probability is a Blunder.
BLUNDER_LOSS = 0.10
IMMEDIATE_SEARCH_BUDGET = "immediate"

Grade = Literal["best", "near-tie", "mistake", "blunder"]


@dataclass(frozen=True, slots=True)
class Decision:
    ply: int
    played: Action
    position: Position


@dataclass(frozen=True, slots=True)
class ReviewedDecision:
    ply: int
    seat: str
    played: str
    best: str
    win_probability: float
    loss: float
    reasons: tuple[Contribution, ...]
    grade: Grade


def grade_loss(loss: float) -> Grade:
    if loss <= 0:
        return "best"
    if loss <= NEAR_TIE_LOSS:
        return "near-tie"
    if loss <= BLUNDER_LOSS:
        return "mistake"
    return "blunder"


def review_decisions(
    decisions: Sequence[Decision],
    model: WinProbabilityModel,
) -> tuple[ReviewedDecision, ...]:
    """Score each decision and drop forced Actions.

    Decisions stay in the order given. A played Action that was not legal is an
    error: the report must not invent a Loss for it.
    """
    reviewed: list[ReviewedDecision] = []
    for decision in decisions:
        analysis = analyze(decision.position, model)
        if analysis.is_forced:
            continue
        played = next(
            (row for row in analysis.ranked if row.action == decision.played),
            None,
        )
        if played is None:
            raise ValueError(
                f"played Action {decision.played.label} is not legal at ply {decision.ply}"
            )
        best = analysis.ranked[0]
        reviewed.append(
            ReviewedDecision(
                ply=decision.ply,
                seat=analysis.seat.name,
                played=played.action.label,
                best=best.action.label,
                win_probability=played.win_probability,
                loss=played.loss,
                reasons=played.reasons,
                grade=grade_loss(played.loss),
            )
        )
    return tuple(reviewed)
