from __future__ import annotations

import json
import math
from itertools import combinations

import pytest

from catan_coach.domain.experiment import FrozenPolicySpec, GameRules, PolicyPreference
from catan_coach.domain.league import LeagueGame, LeaguePlan, schedule

HASH = "a" * 64
SIDECAR = "b" * 64
BASE_SEED = 200_000


def value_entrants(names: tuple[str, ...]) -> tuple[FrozenPolicySpec, ...]:
    return tuple(FrozenPolicySpec(name=name, kind="value") for name in names)


def numbered(count: int) -> tuple[FrozenPolicySpec, ...]:
    return value_entrants(tuple(f"e{index}" for index in range(count)))


def make_plan(**updates: object) -> LeaguePlan:
    values: dict[str, object] = {
        "name": "opening",
        "entrants": numbered(4),
        "cycles": 1,
        "base_seed": BASE_SEED,
    }
    values.update(updates)
    return LeaguePlan(**values)  # type: ignore[arg-type]


def model(name: str, **updates: object) -> FrozenPolicySpec:
    values: dict[str, object] = {
        "name": name,
        "kind": "model",
        "model_path": "model.txt",
        "model_hash": HASH,
        "search_simulations": 0,
    }
    values.update(updates)
    return FrozenPolicySpec(**values)  # type: ignore[arg-type]


def blocks(games: tuple[LeagueGame, ...]) -> dict[tuple[int, int], tuple[LeagueGame, ...]]:
    grouped: dict[tuple[int, int], list[LeagueGame]] = {}
    for game in games:
        grouped.setdefault((game.cycle, game.block), []).append(game)
    return {key: tuple(grouped[key]) for key in sorted(grouped)}


def test_plan_json_round_trip() -> None:
    field = make_plan(
        name="field",
        cycles=2,
        rules=GameRules(vps_to_win=8, friendly_robber=True),
        entrants=(
            model(
                "candidate",
                search_simulations=4,
                explore=True,
                sidecar_path="map.json",
                sidecar_hash=SIDECAR,
            ),
            model(
                "biased",
                declared_preferences=(
                    PolicyPreference("port", -0.25),
                    PolicyPreference("settlement", 0.5),
                ),
            ),
            FrozenPolicySpec(name="value", kind="value"),
            FrozenPolicySpec(name="random", kind="random"),
        ),
    )

    restored = LeaguePlan.from_json(field.to_json())
    assert restored == field
    assert LeaguePlan.from_json(json.loads(json.dumps(field.to_json()))) == field
    assert [item.category for item in restored.entrants[1].declared_preferences] == [
        "settlement",
        "port",
    ]


def test_json_defaults_rules_and_map_and_rejects_unknown_fields() -> None:
    document = make_plan().to_json()
    del document["rules"]
    del document["map_policy"]
    restored = LeaguePlan.from_json(document)
    assert restored.rules == GameRules()
    assert restored.map_policy == "corpus"

    document["winner"] = "nobody"
    with pytest.raises(ValueError, match="unknown league plan field"):
        LeaguePlan.from_json(document)


def test_entrant_reuses_frozen_policy_rules() -> None:
    document = make_plan().to_json()
    entrants = document["entrants"]
    assert isinstance(entrants, list)
    first = entrants[0]
    assert isinstance(first, dict)
    first["model_path"] = "model.txt"
    first["model_hash"] = HASH
    with pytest.raises(ValueError, match="only a model"):
        LeaguePlan.from_json(document)


@pytest.mark.parametrize("count", [0, 1, 3, 13])
def test_entrant_count_is_rejected(count: int) -> None:
    with pytest.raises(ValueError, match="between 4 and 12"):
        make_plan(entrants=numbered(count))


def test_twelve_entrants_schedule_every_combination() -> None:
    field = make_plan(entrants=numbered(12))
    assert len(schedule(field)) == math.comb(12, 4) * 4


def test_duplicate_entrant_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate Entrant name a"):
        make_plan(entrants=value_entrants(("a", "b", "c", "a")))


@pytest.mark.parametrize("cycles", [0, -1, True])
def test_cycles_below_one_are_rejected(cycles: object) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        make_plan(cycles=cycles)


def test_schedule_is_deterministic_and_game_ids_are_not_seeds() -> None:
    field = make_plan(entrants=numbered(5), cycles=2)
    first = schedule(field)
    second = schedule(make_plan(entrants=numbered(5), cycles=2))

    assert first == second
    assert [game.pairing_key for game in first] == [game.pairing_key for game in second]
    assert len({game.game_id for game in first}) == len(first)
    assert len({game.pairing_key for game in first}) == len(first)
    assert len({game.seed for game in first}) == len(first) // 4
    assert all(game.game_id != str(game.seed) for game in first)
    assert all(game.pairing_key != game.game_id for game in first)


def test_pairing_key_tracks_who_sits_and_ignores_the_league_name() -> None:
    plain = schedule(make_plan(entrants=value_entrants(("a", "b", "c", "d"))))
    swapped = schedule(make_plan(entrants=value_entrants(("b", "a", "c", "d"))))
    renamed = schedule(make_plan(name="renamed", entrants=value_entrants(("a", "b", "c", "d"))))
    preferred = schedule(
        make_plan(
            entrants=(
                model(
                    "a",
                    declared_preferences=(PolicyPreference("city", 0.25),),
                ),
                *value_entrants(("b", "c", "d")),
            )
        )
    )
    unbiased = schedule(make_plan(entrants=(model("a"), *value_entrants(("b", "c", "d")))))

    assert plain[0].game_id == swapped[0].game_id == "c0-b0-r0"
    assert plain[0].pairing_key != swapped[0].pairing_key
    assert [game.pairing_key for game in renamed] == [game.pairing_key for game in plain]
    assert [game.game_id for game in renamed] == [game.game_id for game in plain]
    assert [game.seed for game in preferred] == [game.seed for game in unbiased]
    assert [game.pairing_key for game in preferred] != [game.pairing_key for game in unbiased]


def test_rotations_follow_plan_order_and_share_a_block_seed() -> None:
    names = ("delta", "charlie", "bravo", "alpha")
    games = schedule(make_plan(entrants=value_entrants(names), cycles=2))

    assert [game.game_id for game in games] == [
        "c0-b0-r0",
        "c0-b0-r1",
        "c0-b0-r2",
        "c0-b0-r3",
        "c1-b0-r0",
        "c1-b0-r1",
        "c1-b0-r2",
        "c1-b0-r3",
    ]
    assert [game.seed for game in games] == [BASE_SEED] * 4 + [BASE_SEED + 1] * 4
    for cycle in range(2):
        for rotation in range(4):
            game = games[cycle * 4 + rotation]
            assert (
                tuple(entrant.name for entrant in game.entrants)
                == names[rotation:] + names[:rotation]
            )


def test_every_combination_is_one_block_of_cyclic_rotations() -> None:
    count = 5
    cycles = 2
    field = make_plan(entrants=numbered(count), cycles=cycles)
    games = schedule(field)
    expected = {
        frozenset(table) for table in combinations(tuple(e.name for e in field.entrants), 4)
    }
    width = math.comb(count, 4)

    assert len(blocks(games)) == cycles * width
    for (cycle, block), table in blocks(games).items():
        assert len(table) == 4
        assert {game.seed for game in table} == {BASE_SEED + cycle * width + block}
        names = tuple(entrant.name for entrant in table[0].entrants)
        seated: dict[str, set[int]] = {name: set() for name in names}
        for rotation, game in enumerate(table):
            assert game.game_id == f"c{cycle}-b{block}-r{rotation}"
            assert (
                tuple(entrant.name for entrant in game.entrants)
                == names[rotation:] + names[:rotation]
            )
            for seat, entrant in enumerate(game.entrants):
                seated[entrant.name].add(seat)
        assert all(seats == {0, 1, 2, 3} for seats in seated.values())

    seen = {
        cycle: {
            frozenset(entrant.name for entrant in table[0].entrants)
            for (played_cycle, _), table in blocks(games).items()
            if played_cycle == cycle
        }
        for cycle in range(cycles)
    }
    assert seen[0] == seen[1] == expected
    assert tuple(entrant.name for entrant in blocks(games)[(0, 0)][0].entrants) == (
        "e0",
        "e1",
        "e2",
        "e3",
    )


@pytest.mark.parametrize("count", [4, 5, 7])
def test_each_entrant_plays_the_same_number_of_games_per_seat(count: int) -> None:
    cycles = 2
    field = make_plan(entrants=numbered(count), cycles=cycles)
    games = schedule(field)
    per_seat = math.comb(count - 1, 3)

    for cycle in range(cycles):
        played = [game for game in games if game.cycle == cycle]
        assert len(played) == math.comb(count, 4) * 4
        for entrant in field.entrants:
            for seat in range(4):
                sat = sum(game.entrants[seat].name == entrant.name for game in played)
                assert sat == per_seat


def test_alphabeta_entrant_keeps_its_depth() -> None:
    entrants = (*numbered(3), FrozenPolicySpec(name="ab", kind="alphabeta", depth=2))
    field = make_plan(entrants=entrants)
    document = field.to_json()
    assert LeaguePlan.from_json(json.loads(json.dumps(document))) == field

    deeper = make_plan(
        entrants=(*numbered(3), FrozenPolicySpec(name="ab", kind="alphabeta", depth=3))
    )
    assert schedule(field)[0].pairing_key != schedule(deeper)[0].pairing_key

    entrant = document["entrants"][3]  # type: ignore[index]
    del entrant["depth"]
    with pytest.raises(ValueError, match="depth"):
        LeaguePlan.from_json(document)
