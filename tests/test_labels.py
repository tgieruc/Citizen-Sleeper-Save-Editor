"""Tests for :mod:`cs_save_editor.labels`."""

from __future__ import annotations

import cs_save_editor as cs

# ---- friendly_label -------------------------------------------------------


def test_known_stat_returns_explicit_label() -> None:
    assert cs.friendly_label("Player_Bits") == "Bits (currency)"
    assert cs.friendly_label("Cycle") == "Cycle (current day)"


def test_inventory_items_labeled_as_items() -> None:
    assert cs.friendly_label("INV_GirolleCaps") == "Item: Girolle Caps"
    assert cs.friendly_label("INV_ShipmindFragment") == "Item: Shipmind Fragment"
    assert cs.friendly_label("INV_RipperWorm") == "Item: Ripper Worm"


def test_completion_flags_labeled_as_quests() -> None:
    assert cs.friendly_label("AMBERHULLREPAIRS_COMPLETE") == "Quest done: Amberhullrepairs"
    assert cs.friendly_label("C_BACKINBUSINESS_COMPLETE") == "Quest done: C Backinbusiness"


def test_unknown_key_returns_empty() -> None:
    assert cs.friendly_label("SomeRandomVar") == ""
    assert cs.friendly_label("DragosR") == ""


def test_inv_prefix_alone_not_labeled() -> None:
    """``INV_`` with nothing after should not produce ``"Item: "``."""
    assert cs.friendly_label("INV_") == ""


def test_inventory_items_get_labeled_in_real_save(snapshot_bf: bytes) -> None:
    inv_keys = [k for k, _ in cs.list_numeric_pairs(snapshot_bf) if k.startswith("INV_")]
    assert len(inv_keys) > 0, "save should have inventory items"
    for k in inv_keys:
        if k == "INV_New":
            continue
        assert cs.friendly_label(k).startswith("Item: "), f"INV_ key {k!r} not labeled as Item"


def test_some_quests_labeled_in_real_save(snapshot_bf: bytes) -> None:
    complete_keys = [k for k, _ in cs.list_numeric_pairs(snapshot_bf) if k.endswith("_COMPLETE")]
    assert len(complete_keys) > 5
    for k in complete_keys[:5]:
        assert cs.friendly_label(k).startswith("Quest done: ")


# ---- fuzzy_score ----------------------------------------------------------


def test_empty_query_keeps_everything() -> None:
    assert cs.fuzzy_score("", "AnyKey", "any label") > 0
    assert cs.fuzzy_score("   ", "AnyKey", "") > 0


def test_exact_key_beats_prefix_beats_substring() -> None:
    exact = cs.fuzzy_score("Player_Bits", "Player_Bits", "Bits")
    prefix = cs.fuzzy_score("Player", "Player_Bits", "Bits")
    substr = cs.fuzzy_score("Bits", "Player_Bits", "Bits")
    assert exact > prefix > substr > 0


def test_substring_in_key_beats_substring_in_label() -> None:
    key_hit = cs.fuzzy_score("girolle", "INV_GirolleCaps", "Item: Girolle Caps")
    label_hit = cs.fuzzy_score("currency", "Player_Bits", "Bits (currency)")
    assert key_hit > 0
    assert label_hit > 0
    assert key_hit > label_hit


def test_subsequence_match() -> None:
    s = cs.fuzzy_score("shfrg", "INV_ShipmindFragment", "Item: Shipmind Fragment")
    assert s > 0


def test_no_match_returns_zero() -> None:
    assert cs.fuzzy_score("xyz", "Player_Bits", "Bits") == 0
    assert cs.fuzzy_score("zzz", "Cycle", "Day") == 0


def test_case_insensitive() -> None:
    assert cs.fuzzy_score("PLAYER_BITS", "player_bits", "bits") > 0
    assert cs.fuzzy_score("PlayEr_BIts", "Player_Bits", "") > 0


def test_typical_searches_rank_expected_keys_first(snapshot_bf: bytes) -> None:
    keys = [k for k, _ in cs.list_numeric_pairs(snapshot_bf)]

    def top_k(query: str, n: int = 3) -> list[str]:
        scored = sorted(
            ((cs.fuzzy_score(query, k, cs.friendly_label(k)), k) for k in keys),
            key=lambda x: -x[0],
        )
        return [k for _, k in scored[:n]]

    assert top_k("girolle", 1) == ["INV_GirolleCaps"]
    assert top_k("bits", 1) == ["Player_Bits"]
    assert top_k("cycle", 1) == ["Cycle"]
    assert top_k("energy", 1) == ["Player_Energy"]

    # "condition" legitimately matches both Player_Condition and DieCondition.
    top = top_k("condition", 3)
    assert "Player_Condition" in top
    assert "DieCondition" in top
