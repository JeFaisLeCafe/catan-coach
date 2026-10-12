from pathlib import Path

import pytest

from catan_coach.engine.web import create_local_app


@pytest.mark.engine
def test_local_app_persists_and_lists_games(tmp_path: Path) -> None:
    database_path = tmp_path / "games.sqlite"
    web_root = tmp_path / "dist"
    web_root.mkdir()
    (web_root / "index.html").write_text("<main>Catan Coach</main>")

    app = create_local_app(database_path=database_path, web_root=web_root, testing=True)
    response = app.test_client().post(
        "/api/games",
        json={
            "players": ["HUMAN", "W"],
            "map_template": "BASE",
        },
    )
    assert response.status_code == 200
    game_id = response.get_json()["game_id"]
    seat_response = app.test_client().get(f"/api/games/{game_id}/human-seat")
    assert seat_response.status_code == 200
    human_color = seat_response.get_json()["color"]
    assert human_color in {"RED", "BLUE"}

    state = app.test_client().get(f"/api/games/{game_id}/states/latest").get_json()
    human_index = state["colors"].index(human_color)
    opponent_index = 1 - human_index
    assert f"P{human_index}_WOOD_IN_HAND" in state["player_state"]
    assert f"P{opponent_index}_WOOD_IN_HAND" not in state["player_state"]
    assert f"P{opponent_index}_NUM_RESOURCES_IN_HAND" in state["player_state"]
    opponent_color = state["colors"][opponent_index]
    requested_opponent = app.test_client().get(
        f"/api/games/{game_id}/states/latest?as={opponent_color}"
    )
    assert f"P{opponent_index}_WOOD_IN_HAND" not in requested_opponent.get_json()["player_state"]

    restarted_app = create_local_app(
        database_path=database_path,
        web_root=web_root,
        testing=True,
    )
    games_response = restarted_app.test_client().get("/api/games")

    assert games_response.status_code == 200
    [saved_game] = games_response.get_json()
    assert saved_game == {
        "game_id": game_id,
        "players": saved_game["players"],
        "state_index": 0,
        "status": "in_progress",
        "winning_color": None,
    }
    assert set(saved_game["players"]) == {"HUMAN", "W"}


@pytest.mark.engine
def test_local_app_serves_browser_routes(tmp_path: Path) -> None:
    web_root = tmp_path / "dist"
    web_root.mkdir()
    (web_root / "index.html").write_text("<main>Catan Coach</main>")
    (web_root / "asset.txt").write_text("asset")
    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=web_root,
        testing=True,
    )

    client = app.test_client()
    assert client.get("/").text == "<main>Catan Coach</main>"
    assert client.get("/games/saved-game").text == "<main>Catan Coach</main>"
    assert client.get("/asset.txt").text == "asset"
