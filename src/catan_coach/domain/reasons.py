"""Group raw Observation contributions into player-recognisable reasons."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import numpy as np

from catan_coach.domain.analysis import Contribution

PLAYER_LABELS = frozenset({"production", "reachable expansion", "hand", "army", "road", "points"})
DEFAULT_LIMIT = 3


def group_feature(name: str) -> str | None:
    if "_IN_HAND" in name or "NUM_RESOURCES" in name or "NUM_DEVS" in name:
        return "hand"
    if "HAS_ARMY" in name or "KNIGHT" in name:
        return "army"
    if name.startswith("EDGE") or "ROAD" in name:
        return "road"
    if name.startswith("TILE") or name.startswith("BANK"):
        return "production"
    if name.startswith("PORT") or "SETTLEMENT" in name or "CITY" in name or "CITIES_LEFT" in name:
        return "reachable expansion"
    if "VPS" in name:
        return "points"
    return None


def top_contributions(
    values: np.ndarray,
    names: Sequence[str],
    *,
    limit: int = DEFAULT_LIMIT,
) -> tuple[Contribution, ...]:
    if values.shape != (len(names),):
        raise ValueError("values and names must have the same length")
    buckets: dict[str, float] = defaultdict(float)
    for value, name in zip(values, names, strict=True):
        label = group_feature(name)
        if label is None:
            continue
        buckets[label] += float(value)
    ranked = sorted(buckets.items(), key=lambda item: abs(item[1]), reverse=True)
    return tuple(Contribution(label, delta) for label, delta in ranked[:limit] if delta != 0.0)
