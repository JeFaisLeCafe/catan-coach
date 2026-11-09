"""Corpus manifest round-trip, resume identity, and the training drop-rate rule."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from catan_coach.domain.manifest import (
    MANIFEST_NAME,
    CorpusManifest,
    accepts_training,
    training_refusal,
)

_MODEL_SHA = "ab" * 32


def _value_manifest() -> CorpusManifest:
    return CorpusManifest(
        player_kind="value",
        model_sha256="",
        search_simulations=0,
        exploration=False,
        ply_stride=12,
        base_seed=0,
        requested_games=1000,
        validation_fraction=0.2,
        max_turns=1000,
        git_revision="abc123",
        dirty_tree=False,
        games_finished=0,
        games_dropped=0,
        drop_rate=0.0,
    )


def _model_manifest() -> CorpusManifest:
    return CorpusManifest(
        player_kind="model",
        model_sha256=_MODEL_SHA,
        search_simulations=4,
        exploration=True,
        ply_stride=12,
        base_seed=7000,
        requested_games=1000,
        validation_fraction=0.2,
        max_turns=1000,
        git_revision="abc123",
        dirty_tree=False,
        games_finished=0,
        games_dropped=0,
        drop_rate=0.0,
    )


def test_a_manifest_round_trips_through_json() -> None:
    manifest = _model_manifest().with_outcomes(1000, 0)

    restored = CorpusManifest.from_json(manifest.to_json())

    assert restored == manifest
    assert set(json.loads(manifest.to_json())) == {
        "player_kind",
        "model_sha256",
        "search_simulations",
        "exploration",
        "ply_stride",
        "base_seed",
        "requested_games",
        "validation_fraction",
        "max_turns",
        "git_revision",
        "dirty_tree",
        "games_finished",
        "games_dropped",
        "drop_rate",
    }


def test_a_drop_rate_that_does_not_match_the_counts_is_rejected() -> None:
    payload = json.loads(_value_manifest().with_outcomes(2792, 208).to_json())
    payload["drop_rate"] = 0

    with pytest.raises(ValueError, match="drop rate"):
        CorpusManifest.from_json(json.dumps(payload))


def test_resume_refuses_a_manifest_that_disagrees() -> None:
    stored = _value_manifest()

    assert stored.resume_conflicts(stored) == ()
    assert stored.resume_conflicts(stored.with_outcomes(10, 0)) == ()
    assert stored.resume_conflicts(replace(stored, requested_games=1001)) == ()
    assert stored.resume_conflicts(replace(stored, ply_stride=6)) == ("ply_stride",)
    assert stored.resume_conflicts(replace(stored, requested_games=999)) == ("requested_games",)
    assert stored.resume_conflicts(replace(stored, git_revision="other", dirty_tree=True)) == ()
    assert stored.resume_conflicts(replace(stored, base_seed=1)) == ("base_seed",)
    assert stored.resume_conflicts(replace(stored, max_turns=100)) == ("max_turns",)
    assert _model_manifest().resume_conflicts(replace(_model_manifest(), exploration=False)) == (
        "exploration",
    )
    assert _model_manifest().resume_conflicts(replace(_model_manifest(), search_simulations=0)) == (
        "search_simulations",
    )
    assert stored.resume_conflicts(
        replace(
            stored,
            player_kind="model",
            model_sha256=_MODEL_SHA,
            search_simulations=4,
            exploration=True,
        )
    ) == ("player_kind", "model_sha256", "search_simulations", "exploration")


def test_a_drop_rate_of_208_in_3000_is_refused() -> None:
    manifest = _value_manifest().with_outcomes(2792, 208)

    assert manifest.games_dropped / (manifest.games_finished + manifest.games_dropped) == (
        pytest.approx(208 / 3000)
    )
    assert manifest.drop_rate == pytest.approx(208 / 3000)
    assert accepts_training(manifest) is False
    refusal = training_refusal(manifest)
    assert refusal is not None
    assert "6.9%" in refusal
    assert "above 1%" in refusal


def test_a_drop_rate_of_0_in_1000_is_allowed() -> None:
    manifest = _value_manifest().with_outcomes(1000, 0)

    assert manifest.drop_rate == 0.0
    assert accepts_training(manifest) is True
    assert training_refusal(manifest) is None


def test_a_drop_rate_of_exactly_one_percent_is_allowed() -> None:
    manifest = _value_manifest().with_outcomes(990, 10)

    assert manifest.drop_rate == pytest.approx(0.01)
    assert accepts_training(manifest) is True


def test_a_missing_manifest_is_refused() -> None:
    assert training_refusal(None) == "Corpus manifest is missing"


def test_binding_writes_the_manifest_before_games_and_refuses_disagreement(tmp_path: Path) -> None:
    from catan_coach.engine.corpus import _bind_manifest

    invocation = _value_manifest()
    _bind_manifest(tmp_path, invocation)
    assert CorpusManifest.from_json((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8")) == (
        invocation
    )

    stored = invocation.with_outcomes(1, 0)
    (tmp_path / MANIFEST_NAME).write_text(stored.to_json(), encoding="utf-8")
    _bind_manifest(tmp_path, replace(invocation, requested_games=1001))
    assert CorpusManifest.from_json((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8")) == (
        stored
    )

    with pytest.raises(ValueError, match="disagrees") as error:
        _bind_manifest(tmp_path, replace(invocation, ply_stride=1))
    assert "ply_stride" in str(error.value)
    assert CorpusManifest.from_json((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8")) == (
        stored
    )


def test_binding_refuses_games_that_have_no_manifest(tmp_path: Path) -> None:
    from catan_coach.engine.corpus import _bind_manifest

    games = tmp_path / "games"
    games.mkdir()
    (games / "00000.parquet").write_bytes(b"")

    with pytest.raises(ValueError, match="no manifest"):
        _bind_manifest(tmp_path, _value_manifest())


def test_a_loader_refuses_a_missing_manifest_and_a_high_drop_rate(tmp_path: Path) -> None:
    from catan_coach.engine.corpus import require_trainable_corpus

    with pytest.raises(ValueError, match="manifest is missing"):
        require_trainable_corpus(tmp_path)

    high = tmp_path / "high"
    high.mkdir()
    (high / MANIFEST_NAME).write_text(
        _value_manifest().with_outcomes(2792, 208).to_json(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="above 1%"):
        require_trainable_corpus(high)

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / MANIFEST_NAME).write_text(
        _value_manifest().with_outcomes(1000, 0).to_json(),
        encoding="utf-8",
    )
    require_trainable_corpus(clean)
