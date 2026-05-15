# Citizen Sleeper Save Editor

[![CI](https://github.com/tgieruc/citizen-sleeper-save-editor/actions/workflows/ci.yml/badge.svg)](https://github.com/tgieruc/citizen-sleeper-save-editor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Edit your **Citizen Sleeper** save files: money (Bits), Energy, Condition,
the current Cycle, inventory items, skills, and 600+ other numeric
variables. Includes a Tkinter GUI with fuzzy search and a CLI for
scripting.

> **Citizen Sleeper** is a 2022 narrative RPG by Jump Over The Age,
> published by Fellow Traveller. This is an independent, unofficial tool;
> it isn't affiliated with or endorsed by the developer or publisher.

---

## Features

- 🖥️ **Tkinter GUI** with fuzzy search, friendly labels for items / quest
  flags / stats, inline edit, and quick-adjust buttons
  (`−100  −10  −1  +1  +10  +100  +1000`).
- ⌨️ **CLI** with `list`, `set`, and `add` subcommands.
- 🔍 **Inventory-aware**: the 15 `INV_*` variables and 90+ `*_COMPLETE`
  quest flags are auto-labelled and sortable.
- 💾 **Auto-backups** before every write — alongside the save as
  `save_N.dat.bak.<unix-timestamp>` (collision-safe within the same
  second).
- 🌐 **Cross-platform** save folder discovery (macOS, Windows, Linux).
- 🧪 **Well-tested**: 40+ tests covering the crypto round-trip, in-place
  patching, edge cases, file ops, the friendly-label patterns, and the
  fuzzy ranker.

---

## Install

The recommended setup uses [uv](https://docs.astral.sh/uv/) — it pins a
specific Python interpreter (including one with a working Tk for the GUI)
and resolves dependencies from `uv.lock`.

```bash
# 1. Install uv (if you don't have it)
brew install uv     # or:  curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the repo
git clone https://github.com/tgieruc/citizen-sleeper-save-editor
cd citizen-sleeper-save-editor

# 3. Install
uv sync

# 4. Run
uv run cs-save-editor              # GUI
uv run cs-save-editor list         # CLI: list every numeric variable
uv run cs-save-editor add Player_Bits 1000     # +1000 bits
uv run cs-save-editor set Cycle 1              # warp back to Day 1
```

Plain pip also works (`pip install .`), but you'll need to provide a
Python interpreter that has Tkinter available for the GUI.

---

## ⚠️ Steam Cloud — read this first

Citizen Sleeper uses Steam Cloud. Steam syncs:

- **On game launch**: cloud → local — wipes your edits if the cloud copy
  is newer.
- **On game exit**: local → cloud.

If you edit while the game is closed, the next launch can wipe your work.

### The safe procedure

1. Launch Citizen Sleeper through Steam.
2. Wait at the **main menu** — don't load a save yet. Steam has now
   finished syncing cloud → local.
3. *With the game still running on the main menu*, run the editor and
   save your changes to disk.
4. In-game, click **Continue** / load your slot. Your edits are live.
5. Quit normally. Steam syncs the modified save up to the cloud on exit.

### Alternative

Disable Steam Cloud for the game: right-click Citizen Sleeper in your
Steam library → Properties → General → uncheck *Keep game saves in the
Steam Cloud*. Then you can edit anytime, no menu dance.

---

## Save file locations

| OS      | Path                                                                                |
|---------|-------------------------------------------------------------------------------------|
| macOS   | `~/Library/Application Support/com.JumpOvertheAge.CitizenSleeper/save_N.dat`        |
| Windows | `%USERPROFILE%\AppData\LocalLow\Jump Over the Age\Citizen Sleeper\save_N.dat`       |
| Linux   | `~/.config/unity3d/Jump Over the Age/Citizen Sleeper/save_N.dat`                    |

The editor finds these automatically; the GUI also has an *Open save
folder* button.

---

## GUI tour

1. Launch with `uv run cs-save-editor` (or `python -m cs_save_editor`).
   Your slot 1 save loads automatically if found.
2. The table shows every editable numeric variable. "Show only labeled"
   limits it to inventory / stats / quest flags (~120 rows); uncheck to
   see all ~660.
3. Type into the **search box** — fuzzy ranking, so `bits` finds
   `Player_Bits`, `girolle` finds `INV_GirolleCaps`, even `shfrg` finds
   `INV_ShipmindFragment` (subsequence match).
4. Click a row, then either type a new value and **Apply**, or click one
   of the quick-adjust buttons to bump it by ±1, ±10, ±100, ±1000.
5. **💾 Save to disk** — a confirmation reminds you to be on the main menu.
6. Load the slot in-game.

---

## CLI reference

```text
$ uv run cs-save-editor --help
usage: cs-save-editor [-h] {list,set,add,gui} ...

Edit Citizen Sleeper save files (Bits, Energy, Cycle, items…).

positional arguments:
  {list,set,add,gui}
    list              list every editable numeric variable
    set               set a variable to an absolute value
    add               add a delta to a variable (use negative to subtract)
    gui               launch the graphical editor (default)
```

Examples:

```bash
uv run cs-save-editor list                              # all variables
uv run cs-save-editor list | grep -i inv                # just inventory
uv run cs-save-editor set Player_Bits 9999
uv run cs-save-editor add INV_ShipmindFragment 5        # +5 fragments
uv run cs-save-editor add Player_Energy -10             # −10 energy
```

You can pass an explicit save path as the last argument to override
auto-detection.

---

## Development

```bash
# Install dev tooling
uv sync --all-extras --dev

# Install the git hooks
uv run pre-commit install

# Run the tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .
```

The repository layout:

```
src/cs_save_editor/
  crypto.py         # DES-CBC + PBKDF2 (the encryption layer)
  format.py         # BinaryFormatter + PixelCrushers Lua tag-stream parsing
  labels.py         # KNOWN_STATS, friendly_label, fuzzy_score
  saves.py          # default_save_dir, load_save, write_save
  cli.py            # argparse subcommands
  gui.py            # Tkinter UI
  _tcltk.py         # Tcl/Tk path wiring for uv-managed Python
tests/
  test_crypto.py
  test_format.py
  test_labels.py
  test_saves.py
  conftest.py       # snapshot fixtures
```

---

## How it works

The Citizen Sleeper save format is a Russian doll:

| Layer | Format |
|---|---|
| Bytes on disk | base64 |
| First decode | `8-byte salt ‖ DES-CBC ciphertext` (PKCS7 padded) |
| Decrypt | `key = PBKDF2-HMAC-SHA1("WakeUpSleeper", salt, 1000 iter, 8 bytes)`, IV = salt |
| Inner result | base64 again |
| Second decode | .NET BinaryFormatter blob (`PixelCrushers.SavedGameData`) |
| Inside that | `m_dict["2 - CS - MAIN"]` → list of `SaveRecord`, one per saved component |
| `"CS Dialogue Manager"` SaveRecord's `value` | yet another base64 BF blob |
| Inside that | a PixelCrushers Lua tag stream: `S<len><utf8>`, `N<8-byte double>`, `B<bool>`, `T<header>…` |

The editor walks the inner tag stream looking for `S<key> N<value>` pairs
and patches doubles in place — same byte width every time, so the rest
of the file stays untouched.

The password `WakeUpSleeper` lives in the Unity-serialized
`CrossPlatformSavedGameDataStorer` MonoBehaviour (`sharedassets1.assets`,
path_id 1885). PixelCrushers SaveSystem ships with a default of
`"My Password"`; the game devs overrode it in the Unity Inspector and the
value gets baked into the build's asset bundle.

PixelCrushers (the Dialogue System / Save System asset that Citizen
Sleeper uses) is a commercial Unity asset by Pixel Crushers, LLC. The
encryption scheme described here is documented in their public API
([`EncryptionUtility`](https://www.pixelcrushers.com/dialogue_system/manual2x/html/class_pixel_crushers_1_1_encryption_utility.html));
this project re-implements only the decryption needed to read a user's
own save file.

---

## Troubleshooting

### `ModuleNotFoundError: No module named '_tkinter'`
Your Python build doesn't include Tkinter. Easiest fix is `uv sync` — it
installs python-build-standalone, which ships with a working Tk.

On Debian/Ubuntu: `sudo apt install python3-tk`.
On Fedora: `sudo dnf install python3-tkinter`.

### `_tkinter.TclError: Can't find a usable init.tcl`
The Python build has the Tkinter C module but not the Tcl/Tk library
files — a common quirk of
[python-build-standalone](https://github.com/astral-sh/python-build-standalone).
The package auto-wires the bundled libraries on import (see
`src/cs_save_editor/_tcltk.py`); if you still see the error, set them
yourself:

```bash
export TCL_LIBRARY="$(python3 -c 'import sys, pathlib; print(pathlib.Path(sys.base_prefix) / "lib" / "tcl8.6")')"
export TK_LIBRARY="$(python3 -c 'import sys, pathlib; print(pathlib.Path(sys.base_prefix) / "lib" / "tk8.6")')"
```

### "Key not found"
Some variables only exist after specific in-game events. Run
`cs-save-editor list` to see exactly what's in your save right now.

### Edits don't stick after relaunching the game
Steam Cloud is overwriting your changes — see [the Steam Cloud section](#%EF%B8%8F-steam-cloud--read-this-first)
above.

---

## Disclaimer

Use at your own risk. Editing save files can produce in-game states the
developers never intended. The editor always writes a backup before
overwriting, but Steam Cloud sync can still overwrite your local file if
you don't follow the procedure above. Don't use this for online
achievements or anything that interacts with leaderboards.

This project is not affiliated with Jump Over The Age, Fellow Traveller,
Pixel Crushers LLC, or Valve. Citizen Sleeper is a trademark of its
owners.

---

## License

MIT — see [LICENSE](LICENSE).
