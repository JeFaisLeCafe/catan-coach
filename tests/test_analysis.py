from __future__ import annotations

import numpy as np
import pytest

from catan_coach.domain.analysis import analyze
from catan_coach.domain.position import Action, Seat
from catan_coach.domain.prediction import FeatureMatrix, Probabilities, WinProbabilityModel
from catan_coach.models.baselines import ConstantModel

SETTLE_PORT = Action("BUILD_SETTLEMENT 3")
SETTLE_HILL = Action("BUILD_SETTLEMENT 7")
END_TURN = Action("END_TURN")
BLUE = Seat("BLUE")


def observation(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float64)


class ScriptedPosition:
    def __init__(self, seat: Seat, outcomes: dict[Action, np.ndarray]) -> None:
        self.seat_to_act = seat
        self._outcomes = dict(outcomes)

    def legal_actions(self) -> tuple[Action, ...]:
        return tuple(self._outcomes)

    def observation_after(self, action: Action) -> np.ndarray:
        return self._outcomes[action]


class StubModel:
    def __init__(self, table: dict[tuple[float, ...], float]) -> None:
        self._table = table

    @property
    def name(self) -> str:
        return "stub"

    def predict(self, features: FeatureMatrix) -> Probabilities:
        matrix = np.asarray(features, dtype=np.float64)
        return np.array([self._table[tuple(row)] for row in matrix], dtype=np.float64)


def three_action_choice() -> tuple[ScriptedPosition, StubModel]:
    position = ScriptedPosition(
        BLUE,
        {
            SETTLE_PORT: observation(1.0),
            SETTLE_HILL: observation(2.0),
            END_TURN: observation(3.0),
        },
    )
    model = StubModel({(1.0,): 0.40, (2.0,): 0.55, (3.0,): 0.20})
    return position, model


class TestAnalyze:
    def test_ranks_every_legal_action_best_first(self) -> None:
        position, model = three_action_choice()

        analysis = analyze(position, model)

        assert [row.action for row in analysis.ranked] == [
            SETTLE_HILL,
            SETTLE_PORT,
            END_TURN,
        ]
        assert [row.win_probability for row in analysis.ranked] == pytest.approx([0.55, 0.40, 0.20])
        assert not analysis.is_forced

    def test_each_action_carries_its_loss_against_the_best(self) -> None:
        position, model = three_action_choice()

        analysis = analyze(position, model)

        assert [row.loss for row in analysis.ranked] == pytest.approx([0.0, 0.15, 0.35])

    def test_a_single_legal_action_is_forced_not_a_choice(self) -> None:
        position = ScriptedPosition(BLUE, {END_TURN: observation(1.0)})
        model = StubModel({(1.0,): 0.31})

        analysis = analyze(position, model)

        assert analysis.is_forced
        assert [row.action for row in analysis.ranked] == [END_TURN]
        assert analysis.ranked[0].loss == pytest.approx(0.0)

    def test_analysing_a_position_does_not_mutate_it(self) -> None:
        position = ScriptedPosition(
            BLUE,
            {
                SETTLE_PORT: observation(1.0),
                SETTLE_HILL: observation(2.0),
            },
        )
        model = StubModel({(1.0,): 0.40, (2.0,): 0.55})
        before = position.legal_actions()

        analyze(position, model)

        assert position.legal_actions() == before
        assert position.seat_to_act == BLUE

    def test_equal_win_probabilities_are_ordered_by_action_label(self) -> None:
        position = ScriptedPosition(
            BLUE,
            {
                END_TURN: observation(1.0),
                SETTLE_PORT: observation(2.0),
            },
        )
        model = StubModel({(1.0,): 0.40, (2.0,): 0.40})

        analysis = analyze(position, model)

        assert [row.action for row in analysis.ranked] == [SETTLE_PORT, END_TURN]
        assert [row.loss for row in analysis.ranked] == pytest.approx([0.0, 0.0])

    def test_win_probability_is_stated_for_the_seat_to_act(self) -> None:
        position = ScriptedPosition(BLUE, {END_TURN: observation(1.0)})
        model = StubModel({(1.0,): 0.31})

        analysis = analyze(position, model)

        assert analysis.seat == BLUE

    def test_accepts_an_existing_baseline_as_the_model(self) -> None:
        position = ScriptedPosition(
            BLUE,
            {
                END_TURN: observation(0.0, 0.0, 0.0, 0.0),
                SETTLE_HILL: observation(1.0, 0.0, 0.0, 0.0),
                SETTLE_PORT: observation(2.0, 0.0, 0.0, 0.0),
            },
        )
        model = ConstantModel(4)
        assert isinstance(model, WinProbabilityModel)

        analysis = analyze(position, model)

        assert [row.action for row in analysis.ranked] == [
            SETTLE_PORT,
            SETTLE_HILL,
            END_TURN,
        ]
        assert [row.win_probability for row in analysis.ranked] == pytest.approx([0.25, 0.25, 0.25])
        assert [row.loss for row in analysis.ranked] == pytest.approx([0.0, 0.0, 0.0])
