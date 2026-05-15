"""Tests for :mod:`cs_save_editor.format` (BinaryFormatter + Lua tag stream)."""

from __future__ import annotations

import re

import pytest

import cs_save_editor as cs


def test_finds_many_pairs(snapshot_bf: bytes) -> None:
    pairs = cs.list_numeric_pairs(snapshot_bf)
    assert len(pairs) > 100


def test_known_stats_present(snapshot_bf: bytes) -> None:
    keys = {k for k, _ in cs.list_numeric_pairs(snapshot_bf)}
    for required in ("Player_Bits", "Player_Energy", "Player_Condition", "Cycle"):
        assert required in keys, f"{required!r} missing from save"


def test_known_stats_have_sensible_values(snapshot_bf: bytes) -> None:
    pairs = dict(cs.list_numeric_pairs(snapshot_bf))
    assert 0 <= pairs["Player_Bits"] < 100_000
    assert 0 <= pairs["Player_Condition"] <= 100
    assert pairs["Cycle"] >= 1


def test_set_updates_only_targeted_key(snapshot_bf: bytes) -> None:
    before = dict(cs.list_numeric_pairs(snapshot_bf))
    new_bf, old = cs.set_value(snapshot_bf, "Player_Bits", 9999.0)
    assert old == before["Player_Bits"]
    after = dict(cs.list_numeric_pairs(new_bf))
    assert after["Player_Bits"] == 9999.0
    for k, before_val in before.items():
        if k == "Player_Bits":
            continue
        assert before_val == after[k], f"unrelated key {k!r} changed"


def test_set_missing_key_is_a_noop(snapshot_bf: bytes) -> None:
    new_bf, old = cs.set_value(snapshot_bf, "ThisKeyDoesNotExist_XYZ", 42)
    assert old is None
    assert new_bf == snapshot_bf


def test_set_preserves_blob_size(snapshot_bf: bytes) -> None:
    new_bf, _ = cs.set_value(snapshot_bf, "Player_Bits", 1)
    assert len(new_bf) == len(snapshot_bf)


@pytest.mark.parametrize("value", [-5, 0, 2_147_483_647, 3.14159])
def test_set_edge_values(snapshot_bf: bytes, value: float) -> None:
    new_bf, _ = cs.set_value(snapshot_bf, "Player_Bits", value)
    after = dict(cs.list_numeric_pairs(new_bf))
    assert after["Player_Bits"] == pytest.approx(float(value))


def test_set_then_encrypt_then_decrypt_preserves_change(snapshot_bf: bytes) -> None:
    new_bf, _ = cs.set_value(snapshot_bf, "Player_Bits", 12345)
    round_tripped = cs.decrypt_save(cs.encrypt_save(new_bf))
    assert dict(cs.list_numeric_pairs(round_tripped))["Player_Bits"] == 12345.0


def test_multiple_sequential_edits(snapshot_bf: bytes) -> None:
    bf = snapshot_bf
    bf, _ = cs.set_value(bf, "Player_Bits", 100)
    bf, _ = cs.set_value(bf, "Player_Energy", 99)
    bf, _ = cs.set_value(bf, "Player_Condition", 50)
    bf = cs.decrypt_save(cs.encrypt_save(bf))
    d = dict(cs.list_numeric_pairs(bf))
    assert d["Player_Bits"] == 100.0
    assert d["Player_Energy"] == 99.0
    assert d["Player_Condition"] == 50.0


def test_add_positive(snapshot_bf: bytes) -> None:
    before = dict(cs.list_numeric_pairs(snapshot_bf))["Player_Bits"]
    new_bf, old, new = cs.add_value(snapshot_bf, "Player_Bits", 100)
    assert old == before
    assert new == before + 100
    assert dict(cs.list_numeric_pairs(new_bf))["Player_Bits"] == before + 100


def test_add_negative(snapshot_bf: bytes) -> None:
    before = dict(cs.list_numeric_pairs(snapshot_bf))["Player_Bits"]
    _, _, new = cs.add_value(snapshot_bf, "Player_Bits", -10)
    assert new == before - 10


def test_add_missing_key(snapshot_bf: bytes) -> None:
    new_bf, old, new = cs.add_value(snapshot_bf, "NoSuchKey_QQQ", 5)
    assert old is None
    assert new is None
    assert new_bf == snapshot_bf


def test_add_zero_is_noop(snapshot_bf: bytes) -> None:
    new_bf, old, new = cs.add_value(snapshot_bf, "Player_Bits", 0)
    assert old == new
    assert new_bf == snapshot_bf


def test_chained_adds(snapshot_bf: bytes) -> None:
    bf = snapshot_bf
    before = dict(cs.list_numeric_pairs(bf))["Player_Bits"]
    for delta in (10, 20, 30, -5):
        bf, _, _ = cs.add_value(bf, "Player_Bits", delta)
    assert dict(cs.list_numeric_pairs(bf))["Player_Bits"] == before + 55


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")


def test_no_spurious_keys_with_punctuation(snapshot_bf: bytes) -> None:
    """Inner Ink-state JSON used to leak into the variable list as fake keys
    containing ``"``, ``:``, etc. The identifier-shape filter prevents that."""
    for k, _ in cs.list_numeric_pairs(snapshot_bf):
        for ch in ('"', ":", ",", "[", "]", "{", "}", " "):
            assert ch not in k, f"spurious key leaked through filter: {k!r}"


def test_all_displayed_keys_are_identifier_shaped(snapshot_bf: bytes) -> None:
    for k, _ in cs.list_numeric_pairs(snapshot_bf):
        assert _IDENT.match(k), f"key not identifier-shaped: {k!r}"
