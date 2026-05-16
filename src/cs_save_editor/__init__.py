"""Citizen Sleeper save file editor.

A small library + CLI + Tk GUI for decrypting, inspecting, and editing
Citizen Sleeper save files. See the top-level README for usage.

Public API:

    from cs_save_editor import (
        decrypt_save, encrypt_save,
        list_numeric_pairs, set_value, add_value,
        friendly_label, fuzzy_score,
        default_save_dir, list_save_files, load_save, write_save,
    )
"""

from __future__ import annotations

# Wires Tcl/Tk library paths for uv-managed Python builds. Has no effect
# elsewhere. Must be imported before anything that imports tkinter, which is
# why we do it at package init rather than inside .gui.
from . import _tcltk  # noqa: F401
from .crypto import PASSWORD, decrypt_save, encrypt_save
from .format import (
    add_value,
    find_inner_base64,
    find_lua_tag_stream,
    list_numeric_pairs,
    parse_pairs,
    set_value,
)
from .labels import FEATURED_KEYS, KNOWN_STATS, friendly_label, fuzzy_score, sort_rank
from .saves import default_save_dir, list_save_files, load_save, write_save

__version__ = "0.1.0"

__all__ = [
    "FEATURED_KEYS",
    "KNOWN_STATS",
    "PASSWORD",
    "__version__",
    "add_value",
    "decrypt_save",
    "default_save_dir",
    "encrypt_save",
    "find_inner_base64",
    "find_lua_tag_stream",
    "friendly_label",
    "fuzzy_score",
    "list_numeric_pairs",
    "list_save_files",
    "load_save",
    "parse_pairs",
    "set_value",
    "sort_rank",
    "write_save",
]
