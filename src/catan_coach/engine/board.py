"""Corpus boards: shuffled numbers, with a 6 never touching an 8."""

from __future__ import annotations

import random

from catanatron.models.map import BASE_MAP_TEMPLATE, CatanMap

_ATTEMPTS = 128


def corpus_map(seed: int) -> CatanMap:
    """The board a Corpus game with this seed always plays on.

    Terrain and ports follow Catanatron's shuffle. Numbers are shuffled too,
    and a layout where a 6 shares a side with an 8 is discarded.
    """
    rng = random.Random(seed)
    for _ in range(_ATTEMPTS):
        trial = random.Random(rng.randrange(1 << 30))
        board = CatanMap.from_template(BASE_MAP_TEMPLATE, "random", rng=trial)
        if not _six_touches_eight(board):
            return board
    raise RuntimeError(f"no separated-red board for seed {seed}")


def _six_touches_eight(board: CatanMap) -> bool:
    reds = [tile for tile in board.land_tiles.values() if tile.number in (6, 8)]
    for index, left in enumerate(reds):
        left_nodes = set(left.nodes.values())
        for right in reds[index + 1 :]:
            if {left.number, right.number} != {6, 8}:
                continue
            if len(left_nodes & set(right.nodes.values())) >= 2:
                return True
    return False
