from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from catan_coach.domain.experiment import SourceProvenance
from catan_coach.domain.league import schedule
from catan_coach.engine.arena import LeagueStore, load_league
from catan_coach.engine.experiment_store import PlanMismatch

SOURCE = SourceProvenance("e" * 40, False)


def _write_plan(path: Path, **updates: object) -> Path:
    document: dict[str, object] = {
        "name": "tiny",
        "entrants": [{"name": f"value-{index}", "kind": "value"} for index in range(4)],
        "cycles": 1,
        "base_seed": 200_000,
    }
    document.update(updates)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _model_entrant(**updates: object) -> dict[str, object]:
    entrant: dict[str, object] = {"name": "model", "kind": "model", "model_path": "model.txt"}
    entrant.update(updates)
    return entrant


def _field_with(entrant: dict[str, object]) -> list[dict[str, object]]:
    others: list[dict[str, object]] = [
        {"name": f"value-{index}", "kind": "value"} for index in range(3)
    ]
    return [entrant, *others]


def test_a_model_entrant_is_resolved_and_pinned(tmp_path: Path) -> None:
    (tmp_path / "model.txt").write_text("booster", encoding="utf-8")
    plan = load_league(_write_plan(tmp_path / "plan.json", entrants=_field_with(_model_entrant())))
    model = plan.entrants[0]
    assert model.model_path == str((tmp_path / "model.txt").resolve())
    assert model.model_hash == hashlib.sha256(b"booster").hexdigest()


def test_a_declared_hash_must_match_the_model_file(tmp_path: Path) -> None:
    (tmp_path / "model.txt").write_text("booster", encoding="utf-8")
    entrant = _model_entrant(model_hash="a" * 64)
    with pytest.raises(ValueError, match="model hash for model does not match"):
        load_league(_write_plan(tmp_path / "plan.json", entrants=_field_with(entrant)))


def test_a_changed_plan_refuses_to_resume(tmp_path: Path) -> None:
    plan = load_league(_write_plan(tmp_path / "plan.json"))
    LeagueStore.open(tmp_path / "out", plan, SOURCE)
    changed = load_league(_write_plan(tmp_path / "plan.json", cycles=2))
    with pytest.raises(PlanMismatch, match="cycles"):
        LeagueStore.open(tmp_path / "out", changed, SOURCE)


def test_the_frozen_league_loads_back(tmp_path: Path) -> None:
    plan = load_league(_write_plan(tmp_path / "plan.json"))
    LeagueStore.open(tmp_path / "out", plan, SOURCE)
    loaded = LeagueStore.load(tmp_path / "out")
    assert loaded.plan == plan
    assert loaded.source == SOURCE
    assert [game.result_key for game in loaded.scheduled] == [
        game.game_id for game in schedule(plan)
    ]


def test_a_dirty_tree_is_refused_without_allow_dirty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import subprocess

    from catan_coach.cli import main

    def git(command: list[str], **_kwargs: object) -> str:
        if command[1:] == ["rev-parse", "--show-toplevel"]:
            return str(tmp_path)
        if command[1:] == ["rev-parse", "HEAD"]:
            return "e" * 40
        return " M src/catan_coach/cli.py\n"

    monkeypatch.setattr(subprocess, "check_output", git)
    plan = _write_plan(tmp_path / "plan.json")
    out = tmp_path / "out"
    assert main(["arena", "run", str(plan), "--out", str(out)]) == 1
    assert "--allow-dirty" in capsys.readouterr().err
    assert not out.exists()


def _run(plan: Path, out: Path, workers: int = 1) -> int:
    from catan_coach.cli import main

    return main(
        ["arena", "run", str(plan), "--out", str(out), "--workers", str(workers), "--allow-dirty"]
    )


@pytest.mark.engine
def test_each_game_stores_its_entrants_by_seat_and_a_winner(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path / "plan.json")
    out = tmp_path / "out"
    assert _run(plan_path, out) == 0
    league = schedule(load_league(plan_path))
    stored = {path.stem: json.loads(path.read_text()) for path in (out / "games").glob("*.json")}
    assert sorted(stored) == sorted(game.game_id for game in league)
    for game in league:
        document = stored[game.game_id]
        assert document["kind"] == "completed"
        assert document["seed"] == game.seed
        assert [policy["name"] for policy in document["policies"]] == [
            entrant.name for entrant in game.entrants
        ]
        assert [seat["policy_name"] for seat in document["seats"]] == [
            entrant.name for entrant in game.entrants
        ]
        assert [seat["profile"]["won"] for seat in document["seats"]].count(True) == 1
        assert document["seats"][document["winner"]]["profile"]["won"] is True


@pytest.mark.engine
def test_an_interrupted_league_resumes_to_an_identical_store(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path / "plan.json", rules={"turn_limit": 30})
    whole = tmp_path / "whole"
    resumed = tmp_path / "resumed"
    assert _run(plan_path, whole) == 0
    shutil.copytree(whole, resumed)
    games = sorted((resumed / "games").glob("*.json"))
    for path in games[:2]:
        path.unlink()
    kept = {path.name: os.stat(path).st_mtime_ns for path in games[2:]}

    assert _run(plan_path, resumed, workers=2) == 0

    for name, modified in kept.items():
        assert os.stat(resumed / "games" / name).st_mtime_ns == modified
    for path in sorted(whole.rglob("*")):
        twin = resumed / path.relative_to(whole)
        assert twin.exists(), twin
        if path.is_file():
            assert twin.read_bytes() == path.read_bytes(), path.name
    assert sorted(p.relative_to(resumed) for p in resumed.rglob("*")) == sorted(
        p.relative_to(whole) for p in whole.rglob("*")
    )


def test_a_model_override_must_match_the_frozen_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from catan_coach.cli import main
    from catan_coach.engine.corpus import replay_league_corpus

    model = tmp_path / "model.txt"
    model.write_text("booster", encoding="utf-8")
    plan = load_league(_write_plan(tmp_path / "plan.json", entrants=_field_with(_model_entrant())))
    league = tmp_path / "league"
    LeagueStore.open(league, plan, SOURCE)
    wrong = tmp_path / "other.txt"
    wrong.write_text("different", encoding="utf-8")
    out = tmp_path / "corpus"

    with pytest.raises(ValueError, match="not the frozen model"):
        replay_league_corpus(league, out, model_paths={"model": wrong})
    assert (
        main(["arena", "corpus", str(league), "--out", str(out), "--model", f"model={wrong}"]) == 1
    )
    assert "not the frozen model" in capsys.readouterr().err
    assert not out.exists()

    copy = tmp_path / "copy.txt"
    copy.write_bytes(model.read_bytes())
    with pytest.raises(ValueError, match="no result"):
        replay_league_corpus(league, out, model_paths={"model": copy})

    model.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="not the frozen model"):
        replay_league_corpus(league, out, model_paths=None)


@pytest.mark.engine
def test_four_rotations_of_one_block_all_become_corpus_games(tmp_path: Path) -> None:
    import pandas as pd

    from catan_coach.domain.experiment import CompletedGame
    from catan_coach.domain.league import league_plan_sha256
    from catan_coach.domain.manifest import MANIFEST_NAME, CorpusManifest
    from catan_coach.engine.corpus import read_corpus, replay_league_corpus

    plan_path = _write_plan(tmp_path / "plan.json")
    league_dir = tmp_path / "league"
    assert _run(plan_path, league_dir) == 0
    corpus_dir = tmp_path / "corpus"

    summary = replay_league_corpus(league_dir, corpus_dir, model_paths=None)

    store = LeagueStore.load(league_dir)
    outcomes = {result.result_key: result for result in store.read_outcomes()}
    files = sorted((corpus_dir / "games").glob("*.parquet"))
    assert [path.stem for path in files] == [f"c0-b0-r{rotation}" for rotation in range(4)]
    assert summary.games_played == 4
    assert summary.games_dropped == 0
    assert len({result.seed for result in outcomes.values()}) == 1
    splits: set[str] = set()
    for path in files:
        result = outcomes[path.stem]
        assert isinstance(result, CompletedGame)
        document = json.loads((league_dir / "games" / f"{path.stem}.json").read_text())
        assert result.plies == document["plies"]
        assert result.turns == document["turns"]
        frame = pd.read_parquet(path)
        assert set(frame["game_id"].astype(str)) == {path.stem}
        assert set(int(seed) for seed in frame["seed"]) == {result.seed}
        assert sorted(set(frame["ply"].tolist())) == list(range(0, result.plies, 12))
        winner = result.seats[result.winner].seat_name
        assert set(frame.loc[frame["won"] == 1, "seat"]) == {winner}
        splits.update(str(split) for split in frame["split"].unique())
    assert len(splits) == 1
    manifest = CorpusManifest.from_json((corpus_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest.player_kind == "mixed"
    assert manifest.league_name == store.plan.name
    assert manifest.league_plan_sha256 == league_plan_sha256(store.plan)
    assert [(item.name, item.kind, item.model_hash) for item in manifest.entrants] == [
        (entrant.name, entrant.kind, entrant.model_hash or "") for entrant in store.plan.entrants
    ]
    assert read_corpus(corpus_dir).n_games == 4

    again = replay_league_corpus(league_dir, corpus_dir, model_paths=None)
    assert again == summary
