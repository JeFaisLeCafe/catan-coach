"""Proves the pinned catanatron gives us everything the plan assumes.

PyPI's catanatron is a 2022 snapshot missing most of this, so these tests are
the tripwire for the git pin in pyproject.toml. See docs/adr/0004.
"""

from __future__ import annotations

import numpy as np
import pytest

from catan_coach.domain.calibration import brier_skill_score, calibration_report
from catan_coach.engine.features import (
    feature_matrix,
    feature_names,
    feature_vector,
    index_of,
    public_vp_indices,
)
from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel

Corpus = tuple[np.ndarray, np.ndarray]

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catanatron import Color, Game  # noqa: E402
from catanatron.players.value import ValueFunctionPlayer  # noqa: E402

COLORS = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)
PERSPECTIVE = Color.RED
NUM_PLAYERS = len(COLORS)


def play_out(seed: int) -> Game:
    game = Game([ValueFunctionPlayer(c) for c in COLORS], seed=seed)
    game.play()
    return game


@pytest.fixture(scope="module")
def finished_game() -> Game:
    return play_out(seed=42)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    """Positions sampled across whole games, labelled with the eventual winner."""
    stride, features, outcomes = 12, [], []
    for seed in range(12):
        game = Game([ValueFunctionPlayer(c) for c in COLORS], seed=seed)
        snapshots, ply = [], 0
        while game.winning_color() is None and ply < 3_000:
            if ply % stride == 0:
                snapshots.append(feature_vector(game, PERSPECTIVE))
            game.play_tick()
            ply += 1
        winner = game.winning_color()
        if winner is None:
            continue
        features.extend(snapshots)
        outcomes.extend([float(winner == PERSPECTIVE)] * len(snapshots))
    return np.vstack(features), np.array(outcomes, dtype=np.float64)


class TestTheGitPinDelivers:
    def test_every_module_the_plan_needs_is_importable(self) -> None:
        from catanatron.features import create_sample_vector  # noqa: F401
        from catanatron.gym.envs.pygame_renderer import PygameRenderer  # noqa: F401
        from catanatron.players.minimax import AlphaBetaPlayer  # noqa: F401
        from catanatron.serialization import state_from_json, state_to_json  # noqa: F401

    def test_version_is_the_unreleased_main_not_the_pypi_fossil(self) -> None:
        from importlib.metadata import version

        assert version("catanatron") == "3.3.0"

    def test_player_trading_actions_exist(self) -> None:
        from catanatron.models.enums import ActionType

        for name in ("OFFER_TRADE", "ACCEPT_TRADE", "REJECT_TRADE", "CONFIRM_TRADE"):
            assert hasattr(ActionType, name)


class TestGamesTerminate:
    def test_a_four_player_game_produces_a_winner(self, finished_game: Game) -> None:
        assert finished_game.winning_color() in COLORS

    def test_the_action_log_is_recorded(self, finished_game: Game) -> None:
        assert len(finished_game.state.action_records) > 50

    def test_the_same_seed_replays_identically(self) -> None:
        assert play_out(7).winning_color() == play_out(7).winning_color()


class TestObservationsAreHonest:
    """The feature vector must not leak what a player at the table cannot see."""

    def test_the_perspective_player_sees_their_own_hand(self) -> None:
        names = feature_names(NUM_PLAYERS)
        assert "P0_WHEAT_IN_HAND" in names
        assert "P0_VICTORY_POINT_IN_HAND" in names

    @pytest.mark.parametrize("opponent", [1, 2, 3])
    def test_opponent_hands_are_counts_not_contents(self, opponent: int) -> None:
        names = feature_names(NUM_PLAYERS)
        assert f"P{opponent}_NUM_RESOURCES_IN_HAND" in names
        assert f"P{opponent}_NUM_DEVS_IN_HAND" in names
        leaks = [n for n in names if n.startswith(f"P{opponent}_") and n.endswith("_IN_HAND")]
        assert leaks == [
            f"P{opponent}_NUM_DEVS_IN_HAND",
            f"P{opponent}_NUM_RESOURCES_IN_HAND",
        ], f"opponent hand contents leaked: {leaks}"


class TestFeatureAdapter:
    def test_vector_length_matches_the_declared_ordering(self, finished_game: Game) -> None:
        vector = feature_vector(finished_game, PERSPECTIVE)
        assert vector.shape == (len(feature_names(NUM_PLAYERS)),)
        assert vector.dtype == np.float64

    def test_public_vp_indices_put_the_perspective_player_first(self) -> None:
        indices = public_vp_indices(NUM_PLAYERS)
        assert indices[0] == index_of("P0_PUBLIC_VPS", NUM_PLAYERS)
        assert len(indices) == NUM_PLAYERS
        assert len(set(indices)) == NUM_PLAYERS

    def test_the_winner_reaches_ten_public_points(self, finished_game: Game) -> None:
        winner = finished_game.winning_color()
        vector = feature_vector(finished_game, winner)
        assert vector[index_of("P0_ACTUAL_VPS", NUM_PLAYERS)] >= 10

    def test_matrix_stacks_rows_per_position(self, finished_game: Game) -> None:
        matrix = feature_matrix([(finished_game, c) for c in COLORS])
        assert matrix.shape == (NUM_PLAYERS, len(feature_names(NUM_PLAYERS)))

    def test_unknown_feature_names_fail_loudly(self) -> None:
        with pytest.raises(KeyError, match="no feature named"):
            index_of("P0_NOT_A_FEATURE", NUM_PLAYERS)


class TestSerialisationRoundTrip:
    def test_a_position_survives_json(self, finished_game: Game) -> None:
        from catanatron.serialization import state_from_json, state_to_json

        players = [ValueFunctionPlayer(c) for c in COLORS]
        restored = state_from_json(state_to_json(finished_game), players)
        assert restored.winning_color() == finished_game.winning_color()
        assert np.array_equal(
            feature_vector(restored, PERSPECTIVE),
            feature_vector(finished_game, PERSPECTIVE),
        )


class TestRendering:
    def test_a_board_renders_headlessly_to_an_rgb_array(self, finished_game: Game) -> None:
        from catanatron.gym.envs.pygame_renderer import PygameRenderer

        image = PygameRenderer(render_scale=1.0).render(finished_game)
        assert image.ndim == 3
        assert image.shape[2] == 3
        assert image.dtype == np.uint8


class TestBaselinesOnRealPositions:
    def test_both_baselines_emit_valid_probabilities(self, corpus: Corpus) -> None:
        features, _ = corpus
        for model in (ConstantModel(NUM_PLAYERS), VictoryPointShareModel(public_vp_indices(4))):
            predictions = model.predict(features)
            assert predictions.shape == (features.shape[0],)
            assert np.all((predictions >= 0.0) & (predictions <= 1.0))

    def test_knowing_the_score_beats_knowing_nothing(self, corpus: Corpus) -> None:
        """The bar a learned model must clear: it has to know more than who is ahead."""
        features, outcomes = corpus
        constant = calibration_report(ConstantModel(NUM_PLAYERS).predict(features), outcomes)
        vp_share = calibration_report(
            VictoryPointShareModel(public_vp_indices(4)).predict(features), outcomes
        )
        assert brier_skill_score(vp_share.brier_score, constant.brier_score) > 0.05

    def test_the_constant_model_has_no_discrimination(self, corpus: Corpus) -> None:
        """Every position lands in one band, so its error is just how far the
        base rate sits from 1/4 - it cannot tell any two positions apart."""
        features, outcomes = corpus
        report = calibration_report(ConstantModel(NUM_PLAYERS).predict(features), outcomes)
        assert len(report.populated_bins) == 1
        assert report.expected_calibration_error == pytest.approx(abs(outcomes.mean() - 0.25))

    def test_the_vp_baseline_discriminates_across_bands(self, corpus: Corpus) -> None:
        features, outcomes = corpus
        report = calibration_report(
            VictoryPointShareModel(public_vp_indices(4)).predict(features), outcomes
        )
        assert len(report.populated_bins) > 3
