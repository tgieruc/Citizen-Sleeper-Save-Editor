"""Tests for :mod:`cs_save_editor.games` (per-game config + detection)."""

from __future__ import annotations

import cs_save_editor as cs


def test_games_registry_has_cs1_and_cs2() -> None:
    assert "cs1" in cs.GAMES
    assert "cs2" in cs.GAMES
    assert cs.GAMES["cs1"] is cs.CS1
    assert cs.GAMES["cs2"] is cs.CS2


def test_games_have_distinct_save_dirs() -> None:
    cs1_paths = {p.expanduser() for p in cs.CS1.save_dir_candidates}
    cs2_paths = {p.expanduser() for p in cs.CS2.save_dir_candidates}
    assert cs1_paths.isdisjoint(cs2_paths), "CS1 and CS2 must point at different save dirs"


def test_slot_pattern_matches_active_slots_only() -> None:
    # Both games use save_<digits>.dat; reject CS2 auto-backup / metadata names.
    for game in (cs.CS1, cs.CS2):
        assert game.slot_pattern.match("save_1.dat")
        assert game.slot_pattern.match("save_99.dat")
        assert not game.slot_pattern.match("save_1.backup.dat")
        assert not game.slot_pattern.match("save_1.backup2.dat")
        assert not game.slot_pattern.match("saveinfo.dat")
        assert not game.slot_pattern.match("save_1.dat.bak.1234")


def test_detect_game_with_explicit_id() -> None:
    assert cs.detect_game("cs1") is cs.CS1
    assert cs.detect_game("cs2") is cs.CS2


def test_cs1_known_stats_keep_cs1_specific_entries() -> None:
    assert "Player_Condition" in cs.CS1.known_stats
    assert "DieCondition" in cs.CS1.known_stats
    # CS1 doesn't have CS2's ship resources
    assert "Player_Fuel" not in cs.CS1.known_stats
    assert "ENGAGE" not in cs.CS1.known_stats


def test_cs2_known_stats_have_cs2_specific_entries() -> None:
    for k in ("Player_Fuel", "Player_Supplies", "Player_Stress", "ENGAGE", "CrewNumber"):
        assert k in cs.CS2.known_stats, f"{k!r} missing from CS2 known_stats"
    # CS2 keeps the carryover names from CS1 too
    assert "Player_Bits" in cs.CS2.known_stats
    assert "Player_UpgradePoints" in cs.CS2.known_stats


def test_cs2_contract_prefix_labels_contract_keys() -> None:
    label = cs.friendly_label("C_RULESOFTHEEXCHANGE_COMPLETE", cs.CS2)
    # _COMPLETE pattern wins over contract prefix — that's the right call;
    # it tells you the contract is *done*, not just that it exists.
    assert "Quest done" in label or "Contract" in label
    # A bare C_<NAME> with no _COMPLETE should land in the contract bucket.
    assert cs.friendly_label("C_FUELLIMIT", cs.CS2).startswith("Contract:")
    # CS1 has no contract prefix, so the same key is unlabeled.
    assert cs.friendly_label("C_FUELLIMIT", cs.CS1) == ""


def test_friendly_label_defaults_to_cs1() -> None:
    """Back-compat: bare ``friendly_label(key)`` (no game arg) keeps the
    pre-refactor behaviour of using the CS1 vocabulary."""
    assert cs.friendly_label("Player_Condition") == "Condition (HP)"


def test_sort_rank_respects_game_specific_featured() -> None:
    """``Player_Fuel`` is featured for CS2 but unknown to CS1."""
    cs2_rank = cs.sort_rank("Player_Fuel", cs.CS2)
    cs1_rank = cs.sort_rank("Player_Fuel", cs.CS1)
    assert cs2_rank[0] == 0, "Player_Fuel should be featured in CS2"
    assert cs1_rank[0] == 2, "Player_Fuel should be unlabeled in CS1"
