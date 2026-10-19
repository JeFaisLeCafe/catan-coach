import pytest

from catan_coach.domain.analysis import Contribution
from catan_coach.domain.position import Action, Seat
from catan_coach.domain.prediction import FeatureMatrix
from catan_coach.domain.review import Decision, review_decisions
from tests.test_analysis import ScriptedPosition, StubModel, observation

BEST = Action("BUILD_SETTLEMENT 8")
PLAYED = Action("BUILD_SETTLEMENT 3")
ONLY = Action("ROLL")
BLUE = Seat("BLUE")


def decision(ply: int, played: Action, outcomes: dict[Action, float]) -> Decision:
    return Decision(
        ply=ply,
        played=played,
        position=ScriptedPosition(
            BLUE,
            {action: observation(value) for action, value in outcomes.items()},
        ),
    )


class ExplainingModel(StubModel):
    def explain(self, features: FeatureMatrix) -> tuple[tuple[Contribution, ...], ...]:
        probabilities = self.predict(features)
        return tuple(
            (Contribution("production", float(probability) - 0.5),) for probability in probabilities
        )


def test_review_grades_loss_and_skips_forced_actions() -> None:
    model = ExplainingModel(
        {
            (1.0,): 0.50,
            (2.0,): 0.40,
            (3.0,): 0.495,
            (4.0,): 0.45,
            (5.0,): 0.30,
            (6.0,): 0.20,
        }
    )
    decisions = [
        decision(4, BEST, {BEST: 1.0, PLAYED: 2.0}),
        decision(8, PLAYED, {BEST: 1.0, PLAYED: 3.0}),
        decision(12, PLAYED, {BEST: 1.0, PLAYED: 4.0}),
        decision(16, PLAYED, {BEST: 1.0, PLAYED: 5.0}),
        decision(20, ONLY, {ONLY: 6.0}),
    ]

    reviewed = review_decisions(decisions, model)

    assert [row.ply for row in reviewed] == [4, 8, 12, 16]
    assert [row.grade for row in reviewed] == ["best", "near-tie", "mistake", "blunder"]
    blunder = reviewed[-1]
    assert blunder.played == PLAYED.label
    assert blunder.best == BEST.label
    assert blunder.seat == "BLUE"
    assert blunder.win_probability == 0.30
    assert blunder.loss == 0.20
    assert blunder.reasons == (Contribution("production", -0.20),)


def test_review_rejects_a_played_action_that_was_not_legal() -> None:
    model = StubModel({(1.0,): 0.5, (2.0,): 0.4})

    with pytest.raises(ValueError, match="not legal"):
        review_decisions(
            [decision(1, ONLY, {BEST: 1.0, PLAYED: 2.0})],
            model,
        )
