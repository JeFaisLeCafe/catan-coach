"""CLI orchestration for Strategy Lab runs, reports, and comparisons."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from pathlib import Path

from catan_coach.domain.experiment import (
    CompletedGame,
    DroppedGame,
    ExperimentConfig,
    GameRules,
    PolicyConfig,
    PolicyPreference,
    ScheduledGame,
    SourceProvenance,
    TechnicalFailure,
    schedule,
)
from catan_coach.domain.experiment_report import (
    compare,
    format_comparison,
    format_report,
    report_to_json,
    summarize,
)
from catan_coach.engine.experiment_store import (
    ExperimentStore,
    PlanMismatch,
    freeze_config,
    load_plan,
)

_CONFIG_FIELDS = {
    "name",
    "candidate",
    "opponent",
    "games_per_candidate_seat",
    "base_seed",
    "map_policy",
    "rules",
    "player_count",
}
_POLICY_FIELDS = {
    "name",
    "kind",
    "search_simulations",
    "explore",
    "model_path",
    "sidecar_path",
    "preferences",
}
_RULE_FIELDS = {"vps_to_win", "discard_limit", "friendly_robber", "turn_limit"}
_PREFERENCE_FIELDS = {"category", "delta"}
# Bugs in the harness must stay visible. Ordinary play failures are retried once.
_PROGRAMMER_ERRORS = (
    AssertionError,
    AttributeError,
    ImportError,
    NameError,
    NotImplementedError,
    RecursionError,
    SyntaxError,
    TypeError,
)


class DirtyWorktree(ValueError):
    """The source tree has changes and the run did not allow them."""


def load_config(path: Path) -> ExperimentConfig:
    document = json.loads(path.read_text(encoding="utf-8"))
    _unknown(document, _CONFIG_FIELDS, "plan")
    root = path.parent
    rules = document.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError("rules must be an object")
    _unknown(rules, _RULE_FIELDS, "rules")
    return ExperimentConfig(
        name=str(document["name"]),
        candidate=_policy(document["candidate"], root),
        opponent=_policy(document["opponent"], root),
        games_per_candidate_seat=int(document["games_per_candidate_seat"]),
        base_seed=int(document["base_seed"]),
        map_policy=document.get("map_policy", "corpus"),
        rules=GameRules(
            vps_to_win=int(rules.get("vps_to_win", 10)),
            discard_limit=int(rules.get("discard_limit", 7)),
            friendly_robber=bool(rules.get("friendly_robber", False)),
            turn_limit=int(rules.get("turn_limit", 1000)),
        ),
        player_count=int(document.get("player_count", 4)),
    )


def source_provenance(allow_dirty: bool) -> SourceProvenance:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    dirty = bool(status.strip())
    if dirty and not allow_dirty:
        raise DirtyWorktree("refusing a dirty source tree; pass --allow-dirty to record it")
    diff_hash = _dirty_hash(root) if dirty else None
    return SourceProvenance(commit, dirty, diff_hash)


def run_plan(plan_path: Path, out: Path, *, workers: int, allow_dirty: bool) -> int:
    if workers < 1:
        raise ValueError("workers must be at least 1")
    config = load_config(plan_path)
    frozen = freeze_config(config, source_provenance(allow_dirty))
    store = ExperimentStore.open(out, frozen)
    pending = list(store.pending())
    started = time.monotonic()
    _play_all(store, pending, workers, started, out)
    retry = [
        game
        for game in pending
        if _attempts(store, game.result_key) == 1 and not _has_result(store, game.result_key)
    ]
    _play_all(store, retry, workers, started, out)
    terminal = [failure for failure in store.read_failures() if failure.attempt == 2]
    scheduled = len(schedule(store.plan))
    print(
        f"{scheduled - len(store.pending())}/{scheduled} games, "
        f"{len(terminal)} terminal failures, {time.monotonic() - started:.0f}s, {out}",
        file=sys.stderr,
    )
    return 1 if terminal else 0


def report_dir(out: Path, *, json_path: Path | None, markdown_path: Path | None) -> int:
    plan = load_plan(out)
    store = ExperimentStore.open(out, plan)
    report = summarize(plan, schedule(plan), store.read_outcomes(), store.read_failures())
    text = format_report(report)
    payload = json.dumps(report_to_json(report), sort_keys=True, indent=2) + "\n"
    if json_path is not None:
        _atomic(json_path, payload)
    if markdown_path is not None:
        _atomic(markdown_path, text)
    print(text, end="")
    return 0


def compare_dirs(
    reference: Path,
    variants: Sequence[Path],
    *,
    seed: int,
    json_path: Path | None,
    markdown_path: Path | None,
) -> int:
    directories = (reference, *variants)
    plans = tuple(load_plan(path) for path in directories)
    stores = tuple(
        ExperimentStore.open(path, plan) for path, plan in zip(directories, plans, strict=True)
    )
    schedules = tuple(schedule(plan) for plan in plans)
    outcomes = tuple(store.read_outcomes() for store in stores)
    failures = tuple(store.read_failures() for store in stores)
    report = compare(
        plans[0],
        plans[1:],
        schedules,
        outcomes,
        failures,
        seed=seed,
    )
    text = format_comparison(report)
    if json_path is not None:
        _atomic(json_path, json.dumps(report_to_json(report), sort_keys=True, indent=2) + "\n")
    if markdown_path is not None:
        _atomic(markdown_path, text)
    print(text, end="")
    return 0


def _play_all(
    store: ExperimentStore,
    games: list[ScheduledGame],
    workers: int,
    started: float,
    out: Path,
) -> None:
    if not games:
        return
    from catan_coach.engine.experiment import play_scheduled_game

    pool = ProcessPoolExecutor(max_workers=workers)
    outstanding: dict[Future[CompletedGame | DroppedGame], ScheduledGame] = {}
    waiting = iter(games)
    interrupted = False

    def fill() -> None:
        while len(outstanding) < workers:
            try:
                game = next(waiting)
            except StopIteration:
                return
            outstanding[pool.submit(play_scheduled_game, game)] = game

    try:
        fill()
        while outstanding:
            done, _pending = wait(set(outstanding), return_when=FIRST_COMPLETED)
            for future in done:
                game = outstanding.pop(future)
                try:
                    result = future.result()
                except _PROGRAMMER_ERRORS:
                    raise
                except Exception as error:
                    attempt = _attempts(store, game.result_key) + 1
                    store.write_failure(
                        TechnicalFailure(
                            game.result_key,
                            game.pairing_key,
                            attempt,  # type: ignore[arg-type]
                            type(error).__name__,
                            str(error) or type(error).__name__,
                        )
                    )
                else:
                    store.write_result(result)
                done_count = len(schedule(store.plan)) - len(store.pending())
                print(
                    f"{done_count}/{len(schedule(store.plan))} games, "
                    f"{time.monotonic() - started:.0f}s, {out}",
                    file=sys.stderr,
                )
            fill()
    except KeyboardInterrupt:
        interrupted = True
        raise
    finally:
        pool.shutdown(wait=not interrupted, cancel_futures=interrupted)


def _attempts(store: ExperimentStore, result_key: str) -> int:
    return sum(failure.result_key == result_key for failure in store.read_failures())


def _has_result(store: ExperimentStore, result_key: str) -> bool:
    return any(result.result_key == result_key for result in store.read_outcomes())


def _policy(payload: object, root: Path) -> PolicyConfig:
    if not isinstance(payload, dict):
        raise ValueError("a Policy must be an object")
    _unknown(payload, _POLICY_FIELDS, "policy")
    raw_preferences = payload.get("preferences", [])
    if not isinstance(raw_preferences, list):
        raise ValueError("preferences must be a list")
    declared: list[PolicyPreference] = []
    for item in raw_preferences:
        if not isinstance(item, dict):
            raise ValueError("a preference must be an object")
        _unknown(item, _PREFERENCE_FIELDS, "preference")
        declared.append(PolicyPreference(item["category"], item["delta"]))
    return PolicyConfig(
        name=str(payload["name"]),
        kind=payload["kind"],
        search_simulations=int(payload.get("search_simulations", 0)),
        explore=bool(payload.get("explore", False)),
        model_path=_relative(root, payload.get("model_path")),
        sidecar_path=_relative(root, payload.get("sidecar_path")),
        declared_preferences=tuple(declared),
    )


def _relative(root: Path, value: object) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = root / path
    return str(path)


def _unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    extra = sorted(set(payload) - allowed)
    if extra:
        raise ValueError(f"unknown {label} field {extra[0]}")


def _dirty_hash(root: Path) -> str:
    diff = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=root)
    listed = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root,
    )
    pieces = [diff]
    for relative in sorted(path.decode() for path in listed.split(b"\0") if path):
        file = root / relative
        pieces.append(relative.encode())
        pieces.append(file.read_bytes() if file.is_file() else b"")
    return hashlib.sha256(b"\0".join(pieces)).hexdigest()


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


# Re-exported for callers that want the mismatch type without importing the store.
__all__ = ["DirtyWorktree", "PlanMismatch", "compare_dirs", "load_config", "report_dir", "run_plan"]
