from __future__ import annotations

from catan_coach.domain.corpus import VALIDATION, split_for_game


class TestSplitByGame:
    def test_the_same_game_and_seed_always_get_the_same_split(self) -> None:
        first = split_for_game(7, seed=13)
        second = split_for_game(7, seed=13)

        assert first == second

    def test_a_different_seed_can_move_the_same_game(self) -> None:
        splits = {split_for_game(0, seed=seed) for seed in range(50)}

        assert splits == {"train", VALIDATION}

    def test_both_splits_appear_across_games(self) -> None:
        splits = {split_for_game(game_id, seed=0) for game_id in range(40)}

        assert "train" in splits
        assert VALIDATION in splits
