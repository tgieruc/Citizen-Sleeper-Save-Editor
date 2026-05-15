"""Save file discovery and on-disk I/O.

Citizen Sleeper stores its save files under a platform-specific Unity
``Application.persistentDataPath`` directory. This module finds it and
provides safe read / write helpers that always make a timestamped backup
before overwriting.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .crypto import decrypt_save, encrypt_save


def default_save_dir() -> Path:
    """Return the platform-specific Citizen Sleeper save directory.

    Falls back to the macOS path if no existing directory is found, so the
    return value is always usable as the starting point for a file picker.
    """
    home = Path.home()
    candidates = (
        home / "Library/Application Support/com.JumpOvertheAge.CitizenSleeper",
        home / "AppData/LocalLow/Jump Over the Age/Citizen Sleeper",
        home / ".config/unity3d/Jump Over the Age/Citizen Sleeper",
    )
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def list_save_files(save_dir: Path) -> list[Path]:
    """Return ``save_*.dat`` files sorted by name."""
    return sorted(p for p in save_dir.glob("save_*.dat") if p.is_file())


def load_save(path: Path) -> bytes:
    """Read and decrypt a save file."""
    return decrypt_save(path.read_bytes())


def write_save(path: Path, bf_blob: bytes) -> Path:
    """Encrypt and write ``bf_blob`` to ``path``, returning the backup path.

    A backup of the pre-write contents lands alongside the save as
    ``<name>.bak.<unix-timestamp>``. If multiple writes happen within the
    same second, a counter suffix is appended so backups never collide.
    """
    bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    suffix = 0
    while bak.exists():
        suffix += 1
        bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}.{suffix}")
    shutil.copy2(path, bak)
    path.write_bytes(encrypt_save(bf_blob))
    return bak
