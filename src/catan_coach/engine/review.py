"""Walk a saved game and cache its Blunder Report in batches."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict, cast

from catanatron.serialization import action_record_from_json
from catanatron.web.models import StoredAction, StoredGame, db, get_game_state
from flask import abort
from sqlalchemy import select

from catan_coach.domain.position import Action
from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.domain.review import (
    IMMEDIATE_SEARCH_BUDGET,
    Decision,
    ReviewedDecision,
    review_decisions,
)
from catan_coach.engine.position import EnginePosition, action_label

_CACHE_VERSION = 1


def match_played_label(recorded: str, legal: Sequence[str]) -> str:
    """Map a logged Action back to the choice that was legal beforehand.

    Dice, drawn development cards, and stolen resources are part of the log,
    not of the Action the player selected.
    """
    if recorded in legal:
        return recorded
    action_type = recorded.split(" ", 1)[0]
    same_type = [
        label for label in legal if label == action_type or label.startswith(f"{action_type} ")
    ]
    if len(same_type) == 1:
        return same_type[0]
    raise ValueError(f"played Action {recorded} is not legal among {legal}")


class ReviewCache(TypedDict):
    version: int
    head_index: int
    model: str
    seat: str | None
    through_index: int
    complete: bool
    decisions: list[dict[str, object]]


def advance_blunder_report(
    game_id: str,
    *,
    model: WinProbabilityModel,
    fallback: bool,
    cache_dir: Path,
    batch_size: int = 25,
) -> dict[str, object]:
    """Review the next batch of human Actions and persist what is finished.

    Replaying up to the cached ply is cheap. Scoring is not, so a long game
    resumes from the last saved Action instead of starting over.
    """
    stored = db.session.get(StoredGame, game_id)
    if stored is None:
        abort(404, description="Resource not found")

    cache_path = cache_dir / f"{game_id}.json"
    cache = _load_cache(cache_path, head_index=int(stored.head_index), model_name=model.name)
    if cache["complete"]:
        return _payload(cache, model_name=model.name, fallback=fallback)

    game = get_game_state(game_id, cache["through_index"])
    if game is None:
        abort(404, description="Resource not found")
    human_colors = {player.color for player in game.state.players if not player.is_bot}
    log = db.session.scalars(
        select(StoredAction)
        .where(
            StoredAction.uuid == game_id,
            StoredAction.index >= cache["through_index"],
            StoredAction.index < stored.head_index,
        )
        .order_by(StoredAction.index)
    ).all()

    added = 0
    for entry in log:
        if added >= batch_size:
            break
        record = action_record_from_json(json.loads(entry.payload))
        if game.winning_color() is None and game.state.current_color() in human_colors:
            position = EnginePosition(game)
            reviewed = review_decisions(
                [
                    Decision(
                        ply=int(entry.index),
                        played=Action(
                            match_played_label(
                                action_label(record.action),
                                [action.label for action in position.legal_actions()],
                            )
                        ),
                        position=position,
                    )
                ],
                model,
            )
            cache["decisions"].extend(_decision_payload(row) for row in reviewed)
            if reviewed:
                added += 1
        game.execute(record.action, validate_action=False, action_record=record)
        cache["through_index"] = int(entry.index) + 1

    cache["complete"] = cache["through_index"] >= int(stored.head_index)
    cache["seat"] = next(
        (player.color.name for player in game.state.players if not player.is_bot),
        None,
    )
    _save_cache(cache_path, cache)
    return _payload(cache, model_name=model.name, fallback=fallback)


def _decision_payload(row: ReviewedDecision) -> dict[str, object]:
    return {
        "ply": row.ply,
        "seat": row.seat,
        "played": row.played,
        "best": row.best,
        "win_probability": row.win_probability,
        "loss": row.loss,
        "reasons": [{"label": reason.label, "delta": reason.delta} for reason in row.reasons],
        "grade": row.grade,
    }


def _payload(
    cache: ReviewCache,
    *,
    model_name: str,
    fallback: bool,
) -> dict[str, object]:
    return {
        "seat": cache["seat"],
        "model": model_name,
        "fallback": fallback,
        "notice": (
            "No trained model is available; using the vp-share Baseline." if fallback else None
        ),
        "search_budget": IMMEDIATE_SEARCH_BUDGET,
        "complete": cache["complete"],
        "through_index": cache["through_index"],
        "head_index": cache["head_index"],
        "decisions": cache["decisions"],
    }


def _load_cache(path: Path, *, head_index: int, model_name: str) -> ReviewCache:
    if path.is_file():
        cached = json.loads(path.read_text())
        if (
            isinstance(cached, dict)
            and cached.get("version") == _CACHE_VERSION
            and cached.get("head_index") == head_index
            and cached.get("model") == model_name
            and isinstance(cached.get("through_index"), int)
            and isinstance(cached.get("complete"), bool)
            and isinstance(cached.get("decisions"), list)
        ):
            seat = cached.get("seat")
            return {
                "version": _CACHE_VERSION,
                "head_index": head_index,
                "model": model_name,
                "seat": seat if isinstance(seat, str) else None,
                "through_index": cached["through_index"],
                "complete": cached["complete"],
                "decisions": cast(list[dict[str, object]], cached["decisions"]),
            }
    return {
        "version": _CACHE_VERSION,
        "head_index": head_index,
        "model": model_name,
        "seat": None,
        "through_index": 0,
        "complete": head_index == 0,
        "decisions": [],
    }


def _save_cache(path: Path, cache: ReviewCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(cache))
    temporary.replace(path)
