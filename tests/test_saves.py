"""Tests for :mod:`cs_save_editor.saves` (discovery + file I/O)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import cs_save_editor as cs


@pytest.fixture
def tmp_save(snapshot_path: Path, tmp_path: Path) -> Path:
    """A throwaway copy of the snapshot under ``tmp_path``."""
    p = tmp_path / "save_1.dat"
    shutil.copy2(snapshot_path, p)
    return p


def test_default_save_dir_is_path() -> None:
    assert isinstance(cs.default_save_dir(), Path)


def test_list_save_files_returns_dats() -> None:
    sd = cs.default_save_dir()
    if not sd.exists():
        pytest.skip("save directory not present on this system")
    for s in cs.list_save_files(sd):
        assert s.name.startswith("save_") and s.name.endswith(".dat")


def test_write_save_creates_backup(tmp_save: Path) -> None:
    bf = cs.load_save(tmp_save)
    new_bf, _ = cs.set_value(bf, "Player_Bits", 1234)
    bak = cs.write_save(tmp_save, new_bf)
    assert bak.exists()
    # Backup is the OLD content; loading it gives the OLD value
    old_pairs = dict(cs.list_numeric_pairs(cs.load_save(bak)))
    assert old_pairs["Player_Bits"] != 1234
    # New file has the new value
    new_pairs = dict(cs.list_numeric_pairs(cs.load_save(tmp_save)))
    assert new_pairs["Player_Bits"] == 1234


def test_write_then_read_idempotent(tmp_save: Path) -> None:
    bf = cs.load_save(tmp_save)
    cs.write_save(tmp_save, bf)
    assert cs.load_save(tmp_save) == bf


def test_rapid_writes_keep_distinct_backups(tmp_save: Path) -> None:
    """Multiple writes within the same second must not lose the original."""
    original_bytes = tmp_save.read_bytes()
    bf = cs.load_save(tmp_save)
    baks: list[Path] = []
    for new_val in (1, 2, 3, 4):
        edited, _ = cs.set_value(bf, "Player_Bits", new_val)
        baks.append(cs.write_save(tmp_save, edited))
        bf = cs.load_save(tmp_save)
    assert len(set(baks)) == len(baks), f"backups collided: {baks}"
    for b in baks:
        assert b.exists(), f"missing backup: {b}"
    assert baks[0].read_bytes() == original_bytes
