from __future__ import annotations

import json
import subprocess
import threading
import webbrowser
from pathlib import Path
from typing import cast

from catanatron.game import Game
from catanatron.web import api as catanatron_api
from catanatron.web import create_app as create_catanatron_app
from catanatron.web.models import StoredGame, db, get_game_state
from flask import Flask, abort, jsonify, request, send_from_directory
from flask.typing import ResponseReturnValue
from sqlalchemy import select

_PROJECT_ROOT = Path(__file__).parents[3]
_DEFAULT_WEB_ROOT = _PROJECT_ROOT / "web" / "dist"
_DEFAULT_DATABASE_PATH = Path.home() / ".catan-coach" / "games.sqlite"
_UPSTREAM_PERSPECTIVE = catanatron_api._perspective


def create_local_app(
    *,
    database_path: Path = _DEFAULT_DATABASE_PATH,
    web_root: Path = _DEFAULT_WEB_ROOT,
    testing: bool = False,
) -> Flask:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # Upstream routes call this module function directly and offer no app-level hook.
    catanatron_api._perspective = _local_perspective
    app = cast(
        Flask,
        create_catanatron_app(
            {
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
                "TESTING": testing,
            }
        ),
    )

    @app.get("/api/games")
    def list_games() -> ResponseReturnValue:
        summaries: list[dict[str, object]] = []
        stored_games = db.session.scalars(select(StoredGame).order_by(StoredGame.uuid)).all()
        for stored_game in stored_games:
            game = get_game_state(stored_game.uuid)
            if game is None:
                continue
            winner = game.winning_color()
            player_specs = json.loads(stored_game.player_specs)
            summaries.append(
                {
                    "game_id": stored_game.uuid,
                    "players": [spec["key"] for spec in player_specs],
                    "state_index": stored_game.head_index,
                    "status": "finished" if winner is not None else "in_progress",
                    "winning_color": winner.value if winner is not None else None,
                }
            )
        return jsonify(summaries)

    @app.get("/api/games/<string:game_id>/human-seat")
    def human_seat(game_id: str) -> ResponseReturnValue:
        game = get_game_state(game_id)
        if game is None:
            abort(404, description="Resource not found")
        colors = [player.color.value for player in game.state.players if not player.is_bot]
        return jsonify({"color": colors[0] if len(colors) == 1 else None})

    @app.get("/")
    @app.get("/<path:requested_path>")
    def serve_browser(requested_path: str = "") -> ResponseReturnValue:
        candidate = web_root / requested_path
        if requested_path and candidate.is_file():
            return send_from_directory(web_root, requested_path)
        index = web_root / "index.html"
        if index.is_file():
            return send_from_directory(web_root, "index.html")
        abort(503, description="Browser assets are not built")

    return app


def _local_perspective(game: Game) -> str | None:
    human_colors = [str(player.color.value) for player in game.state.players if not player.is_bot]
    if len(human_colors) == 1:
        return human_colors[0]
    if request.args.get("as") is not None:
        return cast(str | None, _UPSTREAM_PERSPECTIVE(game))
    return None


def run_local_server(
    *,
    host: str = "127.0.0.1",
    port: int = 5001,
    open_browser: bool = True,
) -> None:
    _build_browser_assets()
    app = create_local_app()
    url = f"http://{host}:{port}"
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    app.run(host=host, port=port, use_reloader=False)


def _build_browser_assets() -> None:
    web_root = _PROJECT_ROOT / "web"
    try:
        if not (web_root / "node_modules").is_dir():
            subprocess.run(["npm", "ci"], cwd=web_root, check=True)
        subprocess.run(["npm", "run", "build"], cwd=web_root, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise RuntimeError(
            "Could not build the browser app. Install Node.js 24 and npm 11, then retry."
        ) from error
