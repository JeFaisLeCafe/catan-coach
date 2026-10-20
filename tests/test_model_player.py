"""The model chooses a legal Action, the same one Analysis ranks first."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catanatron.game import Game  # noqa: E402
from catanatron.models.player import Color, SimplePlayer  # noqa: E402

from catan_coach.domain.analysis import analyze  # noqa: E402
from catan_coach.engine.features import public_vp_indices  # noqa: E402
from catan_coach.engine.model_player import WinProbabilityPlayer  # noqa: E402
from catan_coach.engine.position import EnginePosition, action_label  # noqa: E402
from catan_coach.models.baselines import VictoryPointShareModel  # noqa: E402


def test_opening_choice_matches_the_analysis() -> None:
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    game = Game([SimplePlayer(color) for color in colors], seed=1)
    model = VictoryPointShareModel(public_vp_indices(4))
    seat = game.state.current_color()
    chosen = WinProbabilityPlayer(seat, model).decide(game, game.playable_actions)

    assert chosen in game.playable_actions
    assert action_label(chosen) == analyze(EnginePosition(game), model).ranked[0].action.label
