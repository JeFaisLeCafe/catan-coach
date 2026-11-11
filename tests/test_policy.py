import pytest

from catan_coach.domain.policy import choose_opening_settlement


def test_opening_settlement_prefers_production_then_label() -> None:
    chosen = choose_opening_settlement(
        (
            ("BUILD_SETTLEMENT 16", 4),
            ("BUILD_SETTLEMENT 2", 9),
            ("BUILD_SETTLEMENT 10", 9),
        )
    )

    assert chosen == "BUILD_SETTLEMENT 10"


def test_opening_settlement_rejects_an_empty_list() -> None:
    with pytest.raises(ValueError, match="opening"):
        choose_opening_settlement(())
