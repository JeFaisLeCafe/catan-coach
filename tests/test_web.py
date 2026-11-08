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
            "players": [
                {"key": "HUMAN", "params": {}},
                {"key": "W", "params": {}},
                {"key": "R", "params": {}},
            ],
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
    opponent_index = next(index for index in range(len(state["colors"])) if index != human_index)
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
    assert set(saved_game["players"]) == {"HUMAN", "W", "R"}


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


@pytest.mark.engine
@pytest.mark.parametrize(
    "players",
    [
        ["HUMAN", "R"],
        ["HUMAN", "HUMAN", "R"],
        ["R", "R", "R"],
    ],
)
def test_local_game_rejects_nonstandard_seating(
    tmp_path: Path,
    players: list[str],
) -> None:
    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        testing=True,
    )

    response = app.test_client().post("/api/games", json={"players": players})

    assert response.status_code == 400


@pytest.mark.engine
def test_local_game_rejects_an_unsupported_mode(tmp_path: Path) -> None:
    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        testing=True,
    )

    response = app.test_client().post(
        "/api/games",
        json={"mode": "other", "players": ["HUMAN", "R", "R"]},
    )

    assert response.status_code == 400


@pytest.mark.engine
def test_reduced_target_human_vs_bots_game_completes_and_is_durable(
    tmp_path: Path,
) -> None:
    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        testing=True,
    )
    client = app.test_client()
    game_id = client.post(
        "/api/games",
        json={"players": ["HUMAN", "R", "R"], "vps_to_win": 3},
    ).get_json()["game_id"]

    for _ in range(1_000):
        state = client.get(f"/api/games/{game_id}/states/latest").get_json()
        if state["winning_color"] is not None:
            break
        action = None
        if state["current_color"] not in state["bot_colors"]:
            action = state["current_playable_actions"][0]
        advanced = client.post(
            f"/api/games/{game_id}/actions",
            json=action,
        ).get_json()
        persisted = client.get(f"/api/games/{game_id}/states/latest").get_json()
        assert persisted["state_index"] == advanced["state_index"]
    else:
        pytest.fail("Reduced-target game did not finish")

    assert state["winning_color"] in state["colors"]
    [saved_game] = client.get("/api/games").get_json()
    assert saved_game["status"] == "finished"
    assert saved_game["winning_color"] == state["winning_color"]


@pytest.mark.engine
def test_live_analysis_uses_a_labelled_fallback_without_changing_the_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from catan_coach.domain.analysis import Analysis
    from catan_coach.domain.prediction import WinProbabilityModel
    from catan_coach.engine.position import EnginePosition

    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        model_path=tmp_path / "missing-model.txt",
        testing=True,
    )
    client = app.test_client()
    game_id = client.post(
        "/api/games",
        json={"players": ["HUMAN", "R", "R"]},
    ).get_json()["game_id"]
    before = client.get(f"/api/games/{game_id}/states/latest").get_json()
    analyzed: list[bool] = []
    original = EnginePosition.analyze

    def analyze(position: EnginePosition, model: WinProbabilityModel) -> Analysis:
        analyzed.append(True)
        return original(position, model)

    monkeypatch.setattr(EnginePosition, "analyze", analyze)

    response = client.get(f"/api/games/{game_id}/analysis")

    assert response.status_code == 200
    assert analyzed == [True]
    payload = response.get_json()
    assert payload["seat"] == before["current_color"]
    assert payload["model"] == "vp-share(T=2.0)"
    assert payload["fallback"] is True
    assert "No trained model" in payload["notice"]
    assert payload["forced"] is (len(payload["actions"]) == 1)
    assert all(
        {"action", "win_probability", "loss", "reasons"} <= row.keys() for row in payload["actions"]
    )
    after = client.get(f"/api/games/{game_id}/states/latest").get_json()
    assert after["state_index"] == before["state_index"]
    assert after["action_records"] == before["action_records"]


@pytest.mark.engine
def test_live_analysis_rejects_a_finished_game(tmp_path: Path) -> None:
    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        model_path=tmp_path / "missing-model.txt",
        testing=True,
    )
    client = app.test_client()
    game_id = client.post(
        "/api/games",
        json={"players": ["HUMAN", "R", "R"], "vps_to_win": 3},
    ).get_json()["game_id"]

    for _ in range(1_000):
        state = client.get(f"/api/games/{game_id}/states/latest").get_json()
        if state["winning_color"] is not None:
            break
        action = None
        if state["current_color"] not in state["bot_colors"]:
            action = state["current_playable_actions"][0]
        client.post(f"/api/games/{game_id}/actions", json=action)
    else:
        pytest.fail("Reduced-target game did not finish")

    response = client.get(f"/api/games/{game_id}/analysis")

    assert response.status_code == 409


@pytest.mark.engine
def test_replay_position_lists_opening_lines_and_the_played_action(tmp_path: Path) -> None:
    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        model_path=tmp_path / "missing-model.txt",
        testing=True,
    )
    client = app.test_client()
    game_id = client.post(
        "/api/games",
        json={"players": ["HUMAN", "R", "R"]},
    ).get_json()["game_id"]
    opening = client.get(f"/api/games/{game_id}/states/0").get_json()
    played = opening["current_playable_actions"][-1]

    before = client.get(f"/api/games/{game_id}/states/0/analysis")
    assert before.status_code == 200
    payload = before.get_json()
    assert payload["ordering"] == "tiles"
    assert payload["played"] is None
    assert len(payload["lines"]) == 5
    assert all("then road toward" in line["summary"] for line in payload["lines"])
    assert "Listed by the hexes they touch." in payload["notice"]
    assert client.get(f"/api/games/{game_id}/states/99/analysis").status_code == 404

    advanced = client.post(f"/api/games/{game_id}/actions", json=played).get_json()
    record = advanced["action_records"][-1][0]
    after = client.get(f"/api/games/{game_id}/states/0/analysis").get_json()
    assert after["played"] == f"{record[1]} {record[2]}"
    assert any(line["action"] == after["played"] for line in after["lines"])
    latest = client.get(f"/api/games/{game_id}/states/latest").get_json()
    assert latest["state_index"] == 1


@pytest.mark.engine
def test_recorded_random_results_match_the_legal_choice() -> None:
    from catan_coach.engine.review import match_played_label

    assert (
        match_played_label(
            "BUY_DEVELOPMENT_CARD VICTORY_POINT",
            ["END_TURN", "BUY_DEVELOPMENT_CARD"],
        )
        == "BUY_DEVELOPMENT_CARD"
    )
    assert match_played_label("ROLL (4, 2)", ["ROLL"]) == "ROLL"
    assert (
        match_played_label(
            "BUILD_SETTLEMENT 3",
            ["BUILD_SETTLEMENT 3", "BUILD_SETTLEMENT 8"],
        )
        == "BUILD_SETTLEMENT 3"
    )


@pytest.mark.engine
def test_blunder_report_resumes_across_batches_without_changing_the_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from catan_coach.domain.analysis import Analysis
    from catan_coach.domain.prediction import WinProbabilityModel
    from catan_coach.engine.position import EnginePosition

    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        model_path=tmp_path / "missing-model.txt",
        testing=True,
    )
    client = app.test_client()
    game_id = client.post(
        "/api/games",
        json={"players": ["HUMAN", "R", "R"]},
    ).get_json()["game_id"]

    human_plies: list[int] = []
    for _ in range(40):
        if len(human_plies) == 2:
            break
        state = client.get(f"/api/games/{game_id}/states/latest").get_json()
        if state["current_color"] not in state["bot_colors"]:
            if len(state["current_playable_actions"]) > 1:
                human_plies.append(state["state_index"])
            client.post(
                f"/api/games/{game_id}/actions",
                json=state["current_playable_actions"][0],
            )
        else:
            client.post(f"/api/games/{game_id}/actions")
    else:
        pytest.fail("Game did not reach two human choices")

    before = client.get(f"/api/games/{game_id}/states/latest").get_json()
    analyzed: list[bool] = []
    original = EnginePosition.analyze

    def analyze(position: EnginePosition, model: WinProbabilityModel) -> Analysis:
        analyzed.append(True)
        return original(position, model)

    monkeypatch.setattr(EnginePosition, "analyze", analyze)
    first = client.get(f"/api/games/{game_id}/review?batch=1")
    assert first.status_code == 200
    assert analyzed == [True]
    first_payload = first.get_json()
    assert first_payload["complete"] is False
    assert first_payload["search_budget"] == "immediate"
    assert first_payload["model"] == "vp-share(T=2.0)"
    assert first_payload["fallback"] is True
    assert "No trained model" in first_payload["notice"]
    assert [row["ply"] for row in first_payload["decisions"]] == [human_plies[0]]
    assert first_payload["decisions"][0]["grade"] in {"best", "near-tie", "mistake", "blunder"}
    assert {"played", "best", "win_probability", "loss", "reasons", "seat"} <= first_payload[
        "decisions"
    ][0].keys()

    second = client.get(f"/api/games/{game_id}/review?batch=1").get_json()
    assert analyzed == [True, True]
    assert [row["ply"] for row in second["decisions"]] == human_plies
    assert second["complete"] is True
    assert second["decisions"][0] == first_payload["decisions"][0]

    after = client.get(f"/api/games/{game_id}/states/latest").get_json()
    assert after["state_index"] == before["state_index"]
    assert after["action_records"] == before["action_records"]


@pytest.mark.engine
def test_a_refused_trade_is_still_offered_to_every_other_bot(tmp_path: Path) -> None:
    from catanatron.models.enums import ActionPrompt
    from catanatron.state_functions import player_freqdeck_add, player_key
    from catanatron.web.models import get_game_state, upsert_game_state

    app = create_local_app(
        database_path=tmp_path / "games.sqlite",
        web_root=tmp_path,
        testing=True,
    )
    client = app.test_client()
    game_id = client.post(
        "/api/games",
        json={"players": ["HUMAN", "CATANATRON", "CATANATRON", "CATANATRON"]},
    ).get_json()["game_id"]

    with app.app_context():
        game = get_game_state(game_id)
        assert game is not None
        state = game.state
        human = next(player.color for player in state.players if not player.is_bot)
        others = [color for color in state.colors if color != human]
        state.is_initial_build_phase = False
        state.current_prompt = ActionPrompt.PLAY_TURN
        state.current_player_index = state.colors.index(human)
        state.current_turn_index = state.current_player_index
        for color in state.colors:
            key = player_key(state, color)
            state.player_state[f"{key}_HAS_ROLLED"] = color == human
            for resource in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"):
                state.player_state[f"{key}_{resource}_IN_HAND"] = 0
        player_freqdeck_add(state, human, [1, 0, 0, 0, 0])
        # The first seat can only refuse. The next one can accept, which is
        # the decision that used to crash the bot and stop the offer.
        player_freqdeck_add(state, others[1], [0, 0, 1, 0, 0])
        upsert_game_state(game)

    offered = client.post(
        f"/api/games/{game_id}/actions",
        json=[human.value, "OFFER_TRADE", [1, 0, 0, 0, 0, 0, 0, 1, 0, 0]],
    )
    assert offered.status_code == 200

    for _ in range(len(others)):
        state_view = client.get(f"/api/games/{game_id}/states/latest").get_json()
        assert state_view["current_color"] in {color.value for color in others}
        assert state_view["current_prompt"] == "DECIDE_TRADE"
        reply = client.post(f"/api/games/{game_id}/actions")
        assert reply.status_code == 200, reply.get_data(as_text=True)

    settled = client.get(f"/api/games/{game_id}/states/latest").get_json()
    replies = [
        record[0][0]
        for record in settled["action_records"]
        if record[0][1] in {"ACCEPT_TRADE", "REJECT_TRADE"}
    ]
    assert replies == [color.value for color in others]
    assert settled["current_color"] == human.value
    assert settled["current_prompt"] in {"PLAY_TURN", "DECIDE_ACCEPTEES"}
