"""How a Policy turns scored Actions into one choice.

Win Probability stays what the model reported. These functions only choose.
"""

from __future__ import annotations

from collections.abc import Iterable


def choose_opening_settlement(options: Iterable[tuple[str, int]]) -> str:
    """The opening settlement with the most production pips.

    The installed model ranks opening nodes in an order that does not change
    with the board, so this choice does not consult Win Probability. An exact
    pip tie breaks on Action label, ascending, matching Analysis.
    """
    scored = tuple(options)
    if not scored:
        raise ValueError("no opening settlements")
    best = max(pips for _, pips in scored)
    return min(label for label, pips in scored if pips == best)
