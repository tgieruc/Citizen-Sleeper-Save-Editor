"""Save file discovery and on-disk I/O.

Each :class:`.games.GameConfig` knows where its target game's saves live
and which filenames are real slots. This module provides game-aware
helpers built on top of that, plus safe read / write that always makes a
timestamped backup before overwriting.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .crypto import decrypt_save, encrypt_save
from .games import CS1, GameConfig

# Default game used by the bare ``default_save_dir()`` / ``list_save_files()``
# entry points. CS1 stays the default so the existing CLI / GUI / tests
# behave the same as before this refactor.
_DEFAULT_GAME: GameConfig = CS1


def default_save_dir(game: GameConfig = _DEFAULT_GAME) -> Path:
    """Return the platform-specific save directory for ``game``.

    Falls back to the first candidate if no existing directory is found, so
    the return value is always usable as a file-picker starting point.
    """
    return game.save_dir()


def list_save_files(save_dir: Path, game: GameConfig = _DEFAULT_GAME) -> list[Path]:
    """Return active slot files in ``save_dir`` sorted by name.

    CS2's directory contains rolling auto-backups (``save_1.backup.dat``,
    ``.backup2.dat``, ``.backup3.dat``) and a ``saveinfo.dat`` menu-metadata
    file alongside real slots. ``game.slot_pattern`` is what filters those
    out — ``save_<digits>.dat`` for both currently supported games.
    """
    if not save_dir.is_dir():
        return []
    return sorted(p for p in save_dir.iterdir() if p.is_file() and game.slot_pattern.match(p.name))


def load_save(path: Path) -> bytes:
    """Read and decrypt a save file. Game-agnostic — both CS1 and CS2 use
    the same crypto."""
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
