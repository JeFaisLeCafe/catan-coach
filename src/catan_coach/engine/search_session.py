"""One Progressive Analysis at a time, cancelled when its Position changes."""

from __future__ import annotations

import random
import threading
import time
import uuid
from dataclasses import dataclass

from catanatron.game import Game

from catan_coach.domain.prediction import WinProbabilityModel
from catan_coach.domain.search import Budget, SearchCache, Snapshot
from catan_coach.engine.lines import action_summaries
from catan_coach.engine.search import refine_position

_BATCH_SIZE = 4
_POLICY_WIDTH = 3
# Ten minutes is the cutoff while a position stays on screen. The other two
# limits only keep a full tree from being replayed, and one line from recursing
# without bound. A ten-minute search should still be storing new positions.
_SEARCH_SECONDS = 10 * 60
_MAX_DEPTH = 200
_MAX_NODES = 800_000


class _SearchClock:
    """Wall time with pauses removed, so a stopped search can be resumed."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._skipped = 0.0
        self._paused_at: float | None = None

    def __call__(self) -> float:
        with self._lock:
            now = time.perf_counter()
            if self._paused_at is not None:
                return self._paused_at - self._skipped
            return now - self._skipped

    def pause(self) -> None:
        with self._lock:
            if self._paused_at is None:
                self._paused_at = time.perf_counter()

    def resume(self) -> None:
        with self._lock:
            if self._paused_at is not None:
                self._skipped += time.perf_counter() - self._paused_at
                self._paused_at = None


@dataclass
class _Job:
    job_id: str
    game_id: str
    state_index: int
    budget: Budget
    stop: threading.Event
    proceed: threading.Event
    clock: _SearchClock
    model_name: str
    fallback: bool
    notice: str | None
    summaries: dict[str, str]
    snapshot: Snapshot | None = None
    running: bool = True
    thread: threading.Thread | None = None


class SearchHub:
    def __init__(self) -> None:
        self._jobs: dict[str, _Job] = {}
        self._cache = SearchCache()
        self._lock = threading.Lock()

    def start(
        self,
        game: Game,
        model: WinProbabilityModel,
        *,
        game_id: str,
        state_index: int,
        budget: Budget,
        fallback: bool,
    ) -> dict[str, object]:
        proceed = threading.Event()
        proceed.set()
        job = _Job(
            job_id=uuid.uuid4().hex,
            game_id=game_id,
            state_index=state_index,
            budget=budget,
            stop=threading.Event(),
            proceed=proceed,
            clock=_SearchClock(),
            model_name=model.name,
            fallback=fallback,
            notice=(
                "No trained model is available; using the vp-share Baseline." if fallback else None
            ),
            summaries=action_summaries(game),
        )
        with self._lock:
            previous = self._jobs.get(game_id)
            if previous is not None:
                previous.stop.set()
                previous.proceed.set()
                previous.running = False
            self._jobs[game_id] = job

        if budget.mode == "immediate":
            self._publish_all(job, game, model)
            return _payload(job)

        worker = threading.Thread(
            target=self._publish_all,
            args=(job, game, model),
            name=f"search-{job.job_id[:8]}",
            daemon=True,
        )
        job.thread = worker
        worker.start()
        deadline = time.perf_counter() + 30
        while time.perf_counter() < deadline:
            with self._lock:
                if job.snapshot is not None or not job.running:
                    break
            time.sleep(0.01)
        return _payload(job)

    def read(self, game_id: str) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(game_id)
            if job is None:
                return None
            return _payload(job)

    def stop(
        self, game_id: str, job_id: str | None, *, cancel: bool = False
    ) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(game_id)
            if job is None:
                return None
            if job_id is not None and job.job_id != job_id:
                return _payload(job)
            job.running = False
            job.clock.pause()
            if cancel:
                job.stop.set()
                job.proceed.set()
            else:
                job.proceed.clear()
            return _payload(job)

    def resume(self, game_id: str, job_id: str | None) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(game_id)
            if job is None:
                return None
            if job_id is not None and job.job_id != job_id:
                return None
            if job.stop.is_set() or job.thread is None or not job.thread.is_alive():
                return None
            job.clock.resume()
            job.running = True
            job.proceed.set()
            return _payload(job)

    def _publish_all(self, job: _Job, game: Game, model: WinProbabilityModel) -> None:
        try:
            for snapshot in refine_position(
                game,
                model,
                budget=_running_budget(job.budget),
                clock=job.clock,
                rng=random.Random(),
                stop=job.stop.is_set,
                cache=self._cache,
                position_id=f"{job.game_id}:{job.state_index}",
                batch_size=_BATCH_SIZE,
                max_depth=_MAX_DEPTH,
                max_nodes=_MAX_NODES,
                policy_width=_POLICY_WIDTH,
            ):
                with self._lock:
                    if job.stop.is_set() or self._jobs.get(job.game_id) is not job:
                        return
                    if job.proceed.is_set() or job.snapshot is None:
                        job.snapshot = snapshot
                job.proceed.wait()
        finally:
            with self._lock:
                if self._jobs.get(job.game_id) is job:
                    job.running = False


def _running_budget(budget: Budget) -> Budget:
    if budget.mode == "continuous":
        return Budget("timed", float(_SEARCH_SECONDS))
    return budget


def _payload(job: _Job) -> dict[str, object]:
    snapshot = job.snapshot
    lines: list[dict[str, object]] = []
    if snapshot is not None:
        lines = [
            {
                "action": line.action,
                "win_probability": line.win_probability,
                "loss": line.loss,
                "visits": line.visits,
                "summary": job.summaries.get(line.action, ""),
                "reasons": [],
            }
            for line in snapshot.lines
        ]
    return {
        "job_id": job.job_id,
        "running": job.running,
        "state_index": job.state_index,
        "source": snapshot.source if snapshot is not None else "immediate",
        "seat": snapshot.seat if snapshot is not None else "",
        "model": job.model_name,
        "fallback": job.fallback,
        "notice": job.notice,
        "forced": len(lines) == 1,
        "simulations": snapshot.simulations if snapshot is not None else 0,
        "nodes": snapshot.nodes if snapshot is not None else 0,
        "elapsed": snapshot.elapsed if snapshot is not None else 0.0,
        "horizon": snapshot.horizon if snapshot is not None else 0.0,
        "uncertainty": snapshot.uncertainty if snapshot is not None else 0.0,
        "lines": lines,
    }
