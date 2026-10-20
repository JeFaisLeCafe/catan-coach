"""Progressive Analysis over HTTP: start, stop, and replace."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from catan_coach.engine.web import create_local_app

pytestmark = pytest.mark.engine


def _client(tmp_path: Path) -> tuple[FlaskClient, str]:
    web_root = tmp_path / "dist"
    web_root.mkdir()
    (web_root / "index.html").write_text("<main>Catan Coach</main>")
    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=web_root,
        model_path=tmp_path / "missing-model.txt",
        testing=True,
    )
    client = app.test_client()
    created = client.post(
        "/api/games",
        json={
            "players": [
                {"key": "HUMAN", "params": {}},
                {"key": "W", "params": {}},
                {"key": "R", "params": {}},
            ],
            "map_template": "BASE",
        },
    )
    assert created.status_code == 200
    return client, created.get_json()["game_id"]


def test_the_first_snapshot_is_the_model_and_a_repeat_is_cached(tmp_path: Path) -> None:
    client, game_id = _client(tmp_path)

    first = client.post(f"/api/games/{game_id}/search", json={"mode": "immediate"})
    second = client.post(f"/api/games/{game_id}/search", json={"mode": "immediate"})

    assert first.status_code == 200
    body = first.get_json()
    assert body["source"] == "immediate"
    assert body["running"] is False
    assert body["simulations"] == 0
    assert body["uncertainty"] == 0
    assert body["lines"]
    assert body["lines"][0]["summary"]
    assert body["fallback"] is True
    assert second.get_json()["lines"] == body["lines"]
    assert second.get_json()["simulations"] == 0


def test_stopping_keeps_the_latest_snapshot(tmp_path: Path) -> None:
    client, game_id = _client(tmp_path)
    started = client.post(f"/api/games/{game_id}/search", json={"mode": "continuous"})
    assert started.status_code == 200
    assert started.get_json()["running"] is True

    stopped = client.delete(
        f"/api/games/{game_id}/search",
        query_string={"job": started.get_json()["job_id"]},
    )
    assert stopped.status_code == 200
    frozen = stopped.get_json()
    assert frozen["running"] is False
    assert frozen["lines"]

    time.sleep(0.4)
    later = client.get(f"/api/games/{game_id}/search").get_json()
    assert later["running"] is False
    assert later["simulations"] == frozen["simulations"]
    assert later["job_id"] == frozen["job_id"]


def test_replacing_a_search_drops_the_old_result(tmp_path: Path) -> None:
    client, game_id = _client(tmp_path)
    first = client.post(f"/api/games/{game_id}/search", json={"mode": "continuous"}).get_json()
    second = client.post(f"/api/games/{game_id}/search", json={"mode": "continuous"}).get_json()

    ignored = client.delete(
        f"/api/games/{game_id}/search",
        query_string={"job": first["job_id"]},
    )
    assert ignored.get_json()["job_id"] == second["job_id"]
    assert ignored.get_json()["running"] is True

    stopped = client.delete(
        f"/api/games/{game_id}/search",
        query_string={"job": second["job_id"]},
    )
    assert stopped.get_json()["running"] is False


def test_a_timed_budget_finishes(tmp_path: Path) -> None:
    client, game_id = _client(tmp_path)
    body = client.post(
        f"/api/games/{game_id}/search",
        json={"mode": "timed", "seconds": 0.25, "state_index": 0},
    ).get_json()
    deadline = time.time() + 8
    while body["running"] and time.time() < deadline:
        time.sleep(0.05)
        body = client.get(f"/api/games/{game_id}/search").get_json()

    assert body["running"] is False
    assert body["state_index"] == 0
    assert body["elapsed"] >= 0
    assert "depth" not in body


def test_search_rejects_a_bad_budget_and_a_missing_game(tmp_path: Path) -> None:
    client, game_id = _client(tmp_path)
    assert client.post(f"/api/games/{game_id}/search", json={"mode": "forever"}).status_code == 400
    assert client.get("/api/games/missing/search").status_code == 404
