from __future__ import annotations

import numpy as np

from catan_coach.domain.corpus import TRAIN, VALIDATION, Corpus, combine_corpora, split_for_game


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


def test_a_mixture_keeps_each_split_and_separates_game_ids() -> None:
    def part(ids: list[int], splits: list[str]) -> Corpus:
        count = len(ids)
        return Corpus(
            game_ids=np.array(ids, dtype=np.int64),
            plies=np.zeros(count, dtype=np.int32),
            seats=np.array(["RED"] * count),
            splits=np.array(splits),
            won=np.zeros(count),
            observations=np.zeros((count, 3)),
        )

    mixed = combine_corpora(
        [
            part([0, 1], [TRAIN, VALIDATION]),
            part([0, 1], [VALIDATION, TRAIN]),
        ]
    )

    assert mixed.n_games == 4
    assert len(set(mixed.game_ids.tolist())) == 4
    first_validation = int(mixed.game_ids[1])
    assert mixed.splits[mixed.game_ids == first_validation].tolist() == [VALIDATION]
    assert set(mixed.splits.tolist()) == {TRAIN, VALIDATION}
