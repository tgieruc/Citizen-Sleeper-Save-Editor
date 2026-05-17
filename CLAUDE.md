# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python desktop tool (CLI + Tk GUI) that decrypts, edits, and re-encrypts
**Citizen Sleeper** (2022) and **Citizen Sleeper 2: Starward Vector** (2025)
save files. Both games ship with the same PixelCrushers Save System asset,
so encryption and serialisation are shared — only the Unity
`persistentDataPath` and the variable vocabulary differ.

## Common commands

Dev setup uses `uv` (it pins a Python build with working Tkinter):

```bash
uv sync --all-extras --dev          # install
uv run pre-commit install            # one-time hook install
uv run pytest                        # full test suite
uv run pytest tests/test_labels.py   # one file
uv run pytest -k fuzzy               # one test by name
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run ruff format --check .         # CI's check-only mode
```

Run the editor:

```bash
uv run cs-save-editor                       # GUI (splash if both games installed)
uv run cs-save-editor list --game cs2
uv run cs-save-editor set Player_Bits 1000 --game cs1
```

## Architecture

The save format is a Russian-doll stack of well-known building blocks
(base64 → DES-CBC → BinaryFormatter → base64 → BinaryFormatter → Lua tag
stream). The codebase is split so each layer has its own module and only
the bottom two (`games`, `labels`) hold game-specific knowledge:

```
saves.py           default_save_dir, list_save_files, load_save, write_save
   │               (atomic write with timestamped .bak backup)
   ▼
crypto.py          decrypt_save / encrypt_save
   │               PBKDF2-SHA1(WakeUpSleeper, salt, 1000) → DES-CBC key, IV=salt
   ▼
format.py          find_inner_base64 → find_lua_tag_stream → parse_pairs
   │               In-place patching of 8-byte LE doubles preserves all
   │               surrounding byte offsets, so we never have to re-serialise
   │               the .NET BinaryFormatter or rebuild the table headers.
   ▼
games.py           GameConfig (per-game vocabulary + save dir + slot regex)
labels.py          friendly_label, fuzzy_score, sort_rank (search + display)
cli.py / gui.py    Argparse CLI and Tk GUI on top of the library
chooser.py         Game-picker splash with Steam library cover art
_tcltk.py          Wires TCL_LIBRARY/TK_LIBRARY for uv's bundled Tk
                   (imported from __init__.py BEFORE anything touches tkinter)
```

### Things that look weird but are load-bearing

- **`_tcltk` import in `__init__.py` must stay before any module that
  imports `tkinter`.** python-build-standalone ships the Tk C module but
  not Tcl's auto-discovery roots; we set `TCL_LIBRARY`/`TK_LIBRARY`
  explicitly before Tk init.
- **CLI lazily imports the GUI** (`cmd_gui` does `from .gui import run_gui`
  inside the function) so `list`/`set`/`add` don't pay Tcl init costs.
- **`_VALID_KEY_RE` filter in `format.py`** drops keys with punctuation.
  Ink scripting state embeds inline JSON inside string tags, and a naive
  walker treats those bytes as fresh `S<key>` tags. Don't remove the
  filter without thinking through the false positives.
- **`set_value` enforces a size invariant** (`len(new_b64) != inner_len`
  raises). Doubles are fixed-width, so any size drift means we patched
  something that wasn't actually the value we thought it was — refuse to
  write rather than corrupt the save.
- **Add a variable to a game's vocabulary in `games.py`, not `labels.py`.**
  `labels.py` only re-exports `KNOWN_STATS`/`FEATURED_KEYS` from CS1 for
  backwards compat; the real source of truth is `_CS1_KNOWN_STATS` /
  `_CS2_KNOWN_STATS` etc. in `games.py`.

## Testing notes

- Tests that touch real encrypted bytes (`test_crypto.py`, `test_format.py`,
  `test_saves.py`) require a save snapshot at `/tmp/save_snapshot.dat`.
  `conftest.py::ensure_snapshot` auto-copies it from the user's live
  `save_1.dat` on first run; in CI those files are deselected and only
  `test_labels.py` / `test_games.py` run.
- The snapshot is never committed (binary, user-specific). Don't add a
  fixture file to the repo — the `pytest.skip` path handles the no-save
  case.

## Backups

`write_save` always copies the current file to `<path>.bak.<unix-ts>`
before overwriting (collision suffix appended if two writes land in the
same second). When users report "edit reverted itself" the culprit is
almost always Steam Cloud sync, not a missing backup — see the Steam
Cloud section of `README.md` for the safe edit procedure.
