from __future__ import annotations

import numpy as np
import pytest

from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel

# Toy layout: columns 0..3 are P0..P3 public VPs, column 4 is noise the models must ignore.
VP_COLUMNS = (0, 1, 2, 3)


def positions(*rows: tuple[float, ...]) -> np.ndarray:
    return np.array(rows, dtype=np.float64)


class TestConstantModel:
    def test_satisfies_the_port(self) -> None:
        assert isinstance(ConstantModel(4), WinProbabilityModel)

    def test_predicts_an_equal_share(self) -> None:
        predictions = ConstantModel(4).predict(positions((0,) * 5, (9,) * 5))
        assert predictions == pytest.approx([0.25, 0.25])

    def test_output_length_tracks_input_rows(self) -> None:
        assert ConstantModel(3).predict(np.zeros((7, 5))).shape == (7,)

    def test_rejects_a_one_player_table(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            ConstantModel(1)

    def test_rejects_a_single_vector(self) -> None:
        with pytest.raises(ValueError, match="2-D"):
            ConstantModel(4).predict(np.zeros(5))


class TestVictoryPointShareModel:
    def test_satisfies_the_port(self) -> None:
        assert isinstance(VictoryPointShareModel(VP_COLUMNS), WinProbabilityModel)

    def test_a_level_table_is_an_equal_share(self) -> None:
        model = VictoryPointShareModel(VP_COLUMNS)
        assert model.predict(positions((3, 3, 3, 3, 99))) == pytest.approx([0.25])

    def test_the_leader_is_favoured(self) -> None:
        model = VictoryPointShareModel(VP_COLUMNS)
        leading, trailing = model.predict(positions((8, 3, 3, 3, 0), (3, 8, 3, 3, 0)))
        assert leading > 0.25 > trailing

    def test_probability_rises_monotonically_with_own_score(self) -> None:
        model = VictoryPointShareModel(VP_COLUMNS)
        predictions = model.predict(positions(*[(vp, 4, 4, 4, 0) for vp in range(11)]))
        assert np.all(np.diff(predictions) > 0)

    def test_ignores_columns_outside_the_vp_indices(self) -> None:
        model = VictoryPointShareModel(VP_COLUMNS)
        quiet, loud = model.predict(positions((5, 2, 2, 2, 0), (5, 2, 2, 2, 10_000)))
        assert quiet == pytest.approx(loud)

    def test_stays_a_probability_under_extreme_scores(self) -> None:
        model = VictoryPointShareModel(VP_COLUMNS, temperature=0.01)
        predictions = model.predict(positions((10, 0, 0, 0, 0), (0, 10, 10, 10, 0)))
        assert np.all(np.isfinite(predictions))
        assert np.all((predictions >= 0.0) & (predictions <= 1.0))

    def test_lower_temperature_sharpens_the_call(self) -> None:
        board = positions((7, 4, 4, 4, 0))
        cautious = VictoryPointShareModel(VP_COLUMNS, temperature=5.0).predict(board)
        decisive = VictoryPointShareModel(VP_COLUMNS, temperature=0.5).predict(board)
        assert decisive[0] > cautious[0]

    @pytest.mark.parametrize(
        ("indices", "temperature", "message"),
        [
            ((0,), 2.0, "at least one opponent"),
            (VP_COLUMNS, 0.0, "must be positive"),
            (VP_COLUMNS, -1.0, "must be positive"),
        ],
    )
    def test_rejects_bad_configuration(
        self, indices: tuple[int, ...], temperature: float, message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            VictoryPointShareModel(indices, temperature)
