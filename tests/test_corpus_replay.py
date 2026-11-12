"""A Corpus replayed from a stored candidate-versus-opponent experiment."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.engine

pytest.importorskip("catanatron")

from catan_coach.domain.experiment import (  # noqa: E402
    CompletedGame,
    ExperimentPlan,
    FrozenPolicySpec,
    SourceProvenance,
    schedule,
)
from catan_coach.domain.manifest import MANIFEST_NAME, CorpusManifest  # noqa: E402
from catan_coach.engine.corpus import (  # noqa: E402
    ReplayMismatch,
    read_corpus,
    replay_experiment_corpus,
)
from catan_coach.engine.experiment import play_scheduled_game  # noqa: E402
from catan_coach.engine.experiment_store import ExperimentStore  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEATS = frozenset({"RED", "BLUE", "WHITE", "ORANGE"})


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _installed(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    model = directory / "model.txt"
    shutil.copyfile(ROOT / "model.txt", model)
    shutil.copyfile(ROOT / "model.calibration.json", directory / "model.calibration.json")
    return model


def _stored_experiment(tmp_path: Path) -> tuple[Path, ExperimentPlan, Path]:
    """Play one block of the installed model against three value Seats."""
    elsewhere = _installed(tmp_path / "elsewhere")
    sidecar = elsewhere.with_name("model.calibration.json")
    plan = ExperimentPlan(
        name="replay-fixture",
        candidate=FrozenPolicySpec(
            "generation-7",
            "model",
            search_simulations=0,
            explore=False,
            model_path=str(elsewhere),
            model_hash=_sha(elsewhere),
            sidecar_path=str(sidecar),
            sidecar_hash=_sha(sidecar),
        ),
        opponent=FrozenPolicySpec("ValueFunctionPlayer", "value"),
        games_per_candidate_seat=1,
        base_seed=60000,
        source=SourceProvenance("e" * 40, False),
    )
    stored = tmp_path / "stored"
    store = ExperimentStore.open(stored, plan)
    for game in schedule(plan):
        store.write_result(play_scheduled_game(game))
    # The candidate is replayed from this checkout's copy, not the frozen path.
    shutil.rmtree(tmp_path / "elsewhere")
    return stored, plan, _installed(tmp_path / "here")


def test_an_observer_sees_every_ply_and_changes_nothing() -> None:
    plan = ExperimentPlan(
        name="observer",
        candidate=FrozenPolicySpec("value-candidate", "value"),
        opponent=FrozenPolicySpec("value", "value"),
        games_per_candidate_seat=1,
        base_seed=60010,
        source=SourceProvenance("e" * 40, False),
    )
    game = schedule(plan)[0]
    seen: list[int] = []

    observed = play_scheduled_game(game, lambda ply, _game: seen.append(ply))

    assert observed == play_scheduled_game(game)
    assert seen == list(range(observed.plies))


def test_a_replay_samples_every_seat_and_labels_the_stored_winner(tmp_path: Path) -> None:
    stored, plan, model = _stored_experiment(tmp_path)
    out = tmp_path / "corpus"

    summary = replay_experiment_corpus(stored, out, model_path=model, ply_stride=12)
    corpus = read_corpus(out)

    assert summary.games_played == 4
    assert summary.games_dropped == 0
    manifest = CorpusManifest.from_json((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest.player_kind == "mixed"
    assert manifest.opponent == "value"
    assert manifest.model_sha256 == _sha(model)
    assert manifest.search_simulations == 0
    assert manifest.exploration is False
    assert manifest.base_seed == 60000
    assert manifest.requested_games == 4
    assert manifest.max_turns == plan.rules.turn_limit
    assert (manifest.games_finished, manifest.games_dropped) == (4, 0)

    outcomes = {result.seed: result for result in ExperimentStore(stored, plan).read_outcomes()}
    assert set(corpus.game_ids.tolist()) == set(outcomes)
    candidate_losses = 0
    for seed, result in outcomes.items():
        assert isinstance(result, CompletedGame)
        rows = corpus.game_ids == seed
        assert set(corpus.seats[rows]) == SEATS
        assert len(set(corpus.splits[rows])) == 1
        plies = sorted(set(corpus.plies[rows].tolist()))
        assert plies == list(range(0, result.plies, 12))
        assert int(rows.sum()) == 4 * len(plies)
        winner = result.seats[result.winner].seat_name
        np.testing.assert_array_equal(
            corpus.won[rows], (corpus.seats[rows] == winner).astype(np.float64)
        )
        candidate = result.seats[result.candidate_seat].seat_name
        candidate_rows = rows & (corpus.seats == candidate)
        assert int(candidate_rows.sum()) == len(plies)
        if result.winner != result.candidate_seat:
            candidate_losses += 1
            assert not corpus.won[candidate_rows].any()
    assert candidate_losses > 0

    again = replay_experiment_corpus(stored, out, model_path=model, ply_stride=12)
    assert again == summary


def test_a_stored_winner_that_does_not_replay_stops_the_work(tmp_path: Path) -> None:
    stored, plan, model = _stored_experiment(tmp_path)
    first = schedule(plan)[0]
    path = stored / "games" / f"{first.result_key}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    loser = next(seat["seat_index"] for seat in document["seats"] if not seat["profile"]["won"])
    for seat in document["seats"]:
        seat["profile"]["won"] = seat["seat_index"] == loser
    document["winner"] = loser
    path.write_text(json.dumps(document), encoding="utf-8")
    out = tmp_path / "corpus"

    with pytest.raises(ReplayMismatch, match=f"seed {first.seed}"):
        replay_experiment_corpus(stored, out, model_path=model)

    assert not (out / "games" / f"{first.seed:05d}.parquet").exists()


def test_a_replay_refuses_a_different_model_or_a_self_play_directory(tmp_path: Path) -> None:
    stored, _plan, model = _stored_experiment(tmp_path)
    other = tmp_path / "other" / "model.txt"
    other.parent.mkdir()
    other.write_text(model.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    shutil.copyfile(
        model.with_name("model.calibration.json"), other.with_name("model.calibration.json")
    )

    with pytest.raises(ValueError, match="not the stored candidate model"):
        replay_experiment_corpus(stored, tmp_path / "corpus", model_path=other)

    self_play = tmp_path / "self-play"
    self_play.mkdir()
    claim = CorpusManifest(
        player_kind="model",
        model_sha256=_sha(model),
        search_simulations=4,
        exploration=True,
        ply_stride=12,
        base_seed=60000,
        requested_games=4,
        validation_fraction=0.2,
        max_turns=1000,
        git_revision="unknown",
        dirty_tree=False,
        games_finished=0,
        games_dropped=0,
        drop_rate=0.0,
    )
    (self_play / MANIFEST_NAME).write_text(claim.to_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="player_kind"):
        replay_experiment_corpus(stored, self_play, model_path=model)
    assert not any((self_play / "games").glob("*.parquet"))


def test_a_replay_refuses_a_self_play_experiment(tmp_path: Path) -> None:
    stored, _plan, model = _stored_experiment(tmp_path)
    document = json.loads((stored / "plan.json").read_text(encoding="utf-8"))
    document["opponent"] = document["candidate"]
    (stored / "plan.json").write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="mixed table only"):
        replay_experiment_corpus(stored, tmp_path / "corpus", model_path=model)
