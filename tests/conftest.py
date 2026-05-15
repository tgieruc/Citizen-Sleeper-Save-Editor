"""Shared test fixtures.

A real save snapshot is kept at ``/tmp/save_snapshot.dat`` so we don't have
to ship binary fixtures in the repo. If it isn't there we copy the user's
live save_1.dat in. Tests that need it call :func:`ensure_snapshot` (the
``snapshot_path`` fixture handles that automatically).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import cs_save_editor

SNAPSHOT = Path("/tmp/save_snapshot.dat")


def ensure_snapshot() -> Path:
    if SNAPSHOT.exists() and SNAPSHOT.stat().st_size > 1000:
        return SNAPSHOT
    save_dir = cs_save_editor.default_save_dir()
    saves = cs_save_editor.list_save_files(save_dir)
    if not saves:
        pytest.skip(f"no save files found in {save_dir}; cannot create snapshot")
    shutil.copy2(saves[0], SNAPSHOT)
    return SNAPSHOT


@pytest.fixture(scope="session")
def snapshot_path() -> Path:
    return ensure_snapshot()


@pytest.fixture(scope="session")
def snapshot_bf(snapshot_path: Path) -> bytes:
    """The decrypted BinaryFormatter blob from the snapshot save."""
    return cs_save_editor.decrypt_save(snapshot_path.read_bytes())
