from __future__ import annotations

import numpy as np

from catan_coach.domain.reasons import PLAYER_LABELS, group_feature, top_contributions


class TestGroupFeature:
    def test_hand_cards_are_hand(self) -> None:
        assert group_feature("P0_WHEAT_IN_HAND") == "hand"
        assert group_feature("P1_NUM_RESOURCES_IN_HAND") == "hand"

    def test_knights_are_army(self) -> None:
        assert group_feature("P0_HAS_ARMY") == "army"
        assert group_feature("P0_KNIGHT_PLAYED") == "army"

    def test_edges_and_longest_road_are_road(self) -> None:
        assert group_feature("EDGE(0, 1)_P0_ROAD") == "road"
        assert group_feature("P0_HAS_ROAD") == "road"
        assert group_feature("P0_LONGEST_ROAD_LENGTH") == "road"

    def test_tile_odds_are_production(self) -> None:
        assert group_feature("TILE0_PROBA") == "production"
        assert group_feature("TILE3_IS_WHEAT") == "production"

    def test_settlements_and_cities_are_reachable_expansion(self) -> None:
        assert group_feature("NODE0_P0_SETTLEMENT") == "reachable expansion"
        assert group_feature("P0_CITIES_LEFT") == "reachable expansion"

    def test_public_points_and_ports_are_grouped(self) -> None:
        assert group_feature("P0_PUBLIC_VPS") == "points"
        assert group_feature("PORT0_IS_WHEAT") == "reachable expansion"
        assert group_feature("BANK_WOOD") == "production"


class TestTopContributions:
    def test_returns_the_handful_of_largest_groups_with_player_labels(self) -> None:
        names = (
            "P0_WHEAT_IN_HAND",
            "P0_ORE_IN_HAND",
            "P0_HAS_ARMY",
            "TILE0_PROBA",
            "EDGE(0, 1)_P0_ROAD",
        )
        values = np.array([0.04, 0.03, -0.20, 0.01, 0.02])

        reasons = top_contributions(values, names, limit=3)

        assert [reason.label for reason in reasons] == ["army", "hand", "road"]
        assert {reason.label for reason in reasons} <= set(PLAYER_LABELS)
