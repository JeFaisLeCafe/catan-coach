from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from catan_coach.domain.corpus import TRAIN, VALIDATION, Corpus
from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel
from catan_coach.models.train import compare_to_baselines, format_comparison, train

VP_COLUMNS = (0, 1, 2, 3)
N_PLAYERS = 4


def _corpus(*, train_games: int = 40, val_games: int = 12, seed: int = 0) -> Corpus:
    """Labels follow a hidden column the VP baseline cannot see."""
    rng = np.random.default_rng(seed)
    games: list[int] = []
    splits: list[str] = []
    seats: list[str] = []
    won: list[float] = []
    rows: list[np.ndarray] = []
    names = ("RED", "BLUE", "WHITE", "ORANGE")

    def add_game(game_id: int, split: str) -> None:
        winner = int(rng.integers(0, N_PLAYERS))
        for _ply in range(3):
            for seat_index, seat in enumerate(names):
                vps = rng.integers(0, 6, size=N_PLAYERS).astype(np.float64)
                vps[winner] += 3
                hidden = rng.normal(0.0, 0.1, size=N_PLAYERS)
                hidden[winner] = 8.0
                # P0 is the perspective Seat, matching a real Observation.
                observation = np.concatenate(
                    [np.roll(vps, -seat_index), np.roll(hidden, -seat_index)]
                )
                games.append(game_id)
                splits.append(split)
                seats.append(seat)
                won.append(float(seat_index == winner))
                rows.append(observation)

    for game_id in range(train_games):
        add_game(game_id, TRAIN)
    for game_id in range(train_games, train_games + val_games):
        add_game(game_id, VALIDATION)

    return Corpus(
        game_ids=np.array(games, dtype=np.int64),
        plies=np.zeros(len(games), dtype=np.int32),
        seats=np.array(seats, dtype=np.str_),
        splits=np.array(splits, dtype=np.str_),
        won=np.array(won, dtype=np.float64),
        observations=np.vstack(rows),
    )


class TestTrain:
    def test_training_ignores_the_validation_split(self) -> None:
        corpus = _corpus()
        poisoned = Corpus(
            game_ids=corpus.game_ids,
            plies=corpus.plies,
            seats=corpus.seats,
            splits=corpus.splits,
            won=np.where(corpus.splits == VALIDATION, np.nan, corpus.won),
            observations=corpus.observations,
        )

        model = train(poisoned, seed=0)

        assert np.all(np.isfinite(model.predict(corpus.observations)))

    def test_the_saved_model_loads_through_the_port(self, tmp_path: Path) -> None:
        from catan_coach.domain.prediction import WinProbabilityModel
        from catan_coach.models.gbdt import GbdtModel

        corpus = _corpus()
        trained = train(corpus, seed=1)
        path = tmp_path / "model.txt"
        trained.save(path)
        loaded = GbdtModel.load(path)

        assert isinstance(loaded, WinProbabilityModel)
        assert loaded.predict(corpus.observations[:5]).shape == (5,)
        assert loaded.predict(corpus.observations[:5]) == pytest.approx(
            trained.predict(corpus.observations[:5]), abs=1e-9
        )

    def test_the_model_beats_both_baselines_on_held_out_games(self) -> None:
        corpus = _corpus(train_games=60, val_games=20, seed=2)
        model = train(corpus, seed=2)
        comparison = compare_to_baselines(
            model,
            corpus,
            constant=ConstantModel(N_PLAYERS),
            vp_share=VictoryPointShareModel(VP_COLUMNS),
        )

        assert comparison.beats_constant
        assert comparison.beats_vp_share
        assert comparison.ece_better_than_vp_share

    def test_a_failure_to_clear_a_baseline_is_stated_in_the_report(self) -> None:
        corpus = _corpus(train_games=8, val_games=8, seed=3)
        comparison = compare_to_baselines(
            ConstantModel(N_PLAYERS),
            corpus,
            constant=ConstantModel(N_PLAYERS),
            vp_share=VictoryPointShareModel(VP_COLUMNS),
        )
        text = format_comparison(comparison, corpus_path="toy", n_games=corpus.n_games)

        assert comparison.beats_constant is False
        assert "does not beat" in text.lower()
        assert "toy" in text
        assert str(corpus.n_games) in text
        assert "brier" in text.lower()
        assert "ece" in text.lower()
        assert "Discrimination" in text

    def test_training_is_reproducible_from_a_seed(self) -> None:
        corpus = _corpus(seed=4)
        first = train(corpus, seed=7).predict(corpus.observations[:12])
        second = train(corpus, seed=7).predict(corpus.observations[:12])
        assert first == pytest.approx(second)

    def test_explanations_use_player_recognisable_labels(self, tmp_path: Path) -> None:
        from catan_coach.domain.reasons import PLAYER_LABELS
        from catan_coach.models.gbdt import GbdtModel

        corpus = _corpus(seed=5)
        names = (
            "P0_PUBLIC_VPS",
            "P1_PUBLIC_VPS",
            "P2_PUBLIC_VPS",
            "P3_PUBLIC_VPS",
            "TILE0_PROBA",
            "TILE1_PROBA",
            "P0_WHEAT_IN_HAND",
            "P0_HAS_ARMY",
        )
        path = tmp_path / "model.txt"
        train(corpus, seed=5).save(path)
        reasons = GbdtModel.load(path, feature_names=names).explain(corpus.observations[:3])

        assert len(reasons) == 3
        for group in reasons:
            assert {item.label for item in group} <= set(PLAYER_LABELS)


def test_n_games_counts_games_not_rows() -> None:
    corpus = _corpus(train_games=3, val_games=2)
    assert corpus.n_games == 5
    assert len(corpus.won) > 5
