# Citizen Sleeper Save Editor

[![CI](https://github.com/tgieruc/citizen-sleeper-save-editor/actions/workflows/ci.yml/badge.svg)](https://github.com/tgieruc/citizen-sleeper-save-editor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small desktop app to edit save files from **Citizen Sleeper** (2022)
and **Citizen Sleeper 2: Starward Vector** (2025): currency, energy /
condition / stress, fuel and supplies, the current Cycle, skills, dice,
crew state, inventory items, quest and contract flags — hundreds of
numeric variables, all in one tool.

When both games' saves are present the editor opens a chooser splash
showing each game's Steam library cover. Cover resolution tries three
sources in order: your local Steam library cache, the editor's own
download cache, then a one-time fetch from Steam's public CDN
(`cdn.cloudflare.steamstatic.com`). Everything is cached under
`~/.cache/cs-save-editor/covers/` so it stays offline-fast after the
first run. If all three sources fail (no network, CDN 404) the chooser
falls back to color-themed text tiles.

> **Citizen Sleeper** and **Citizen Sleeper 2: Starward Vector** are
> narrative RPGs by Jump Over The Age, published by Fellow Traveller.
> This is an independent, unofficial tool; it isn't affiliated with or
> endorsed by the developer or publisher.

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
3. *With the game still running on the main menu*, open the editor and
   save your changes to disk.
4. In-game, click **Continue** / load your slot. Your edits are live.
5. Quit normally. Steam syncs the modified save up to the cloud on exit.

### Alternative

Disable Steam Cloud for the game: right-click Citizen Sleeper in your
Steam library → Properties → General → uncheck *Keep game saves in the
Steam Cloud*. Then you can edit anytime, no menu dance.

---

## Install & run

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

# 4. Launch the editor
uv run cs-save-editor                # GUI (chooses CS1 vs CS2 if both installed)
uv run cs-save-editor list --game cs2
uv run cs-save-editor set Player_Bits 1000 --game cs1
uv run cs-save-editor add Cycle 1 --game cs2
```

Plain pip also works (`pip install .`), but you'll need a Python
interpreter that has Tkinter available.

---

## Save file locations

### Citizen Sleeper (CS1)

| OS      | Path                                                                                |
|---------|-------------------------------------------------------------------------------------|
| macOS   | `~/Library/Application Support/com.JumpOvertheAge.CitizenSleeper/save_N.dat`        |
| Windows | `%USERPROFILE%\AppData\LocalLow\Jump Over the Age\Citizen Sleeper\save_N.dat`       |
| Linux   | `~/.config/unity3d/Jump Over the Age/Citizen Sleeper/save_N.dat`                    |

### Citizen Sleeper 2: Starward Vector (CS2)

| OS      | Path                                                                                                       |
|---------|------------------------------------------------------------------------------------------------------------|
| macOS   | `~/Library/Application Support/com.Jump-Over-the-Age.Citizen-Sleeper-2/save_N.dat`                         |
| Windows | `%USERPROFILE%\AppData\LocalLow\Jump Over the Age\Citizen Sleeper 2 Starward Vector\save_N.dat`            |
| Linux   | `~/.config/unity3d/Jump Over the Age/Citizen Sleeper 2 Starward Vector/save_N.dat`                         |

CS2's directory also contains rolling auto-backups
(`save_N.backup.dat`, `.backup2.dat`, `.backup3.dat`) and a
`saveinfo.dat` menu-metadata file. The editor's slot picker ignores them
all — it only shows the active `save_N.dat` slots.

The editor finds these automatically; there's also an *Open save folder*
button in the app.

---

## How to use it

1. Launch the editor. Your slot 1 save loads automatically if found —
   use the dropdown to switch slots.
2. The table shows every editable numeric variable. "Show only labeled"
   limits it to inventory / stats / quest flags (~120 rows); uncheck to
   see all ~660.
3. Type into the **search box** — fuzzy ranking, so `bits` finds
   `Player_Bits`, `girolle` finds `INV_GirolleCaps`, even `shfrg` finds
   `INV_ShipmindFragment`.
4. Click a row, then either type a new value and **Apply**, or click one
   of the quick-adjust buttons to bump it by ±1, ±10, ±100, ±1000.
5. **💾 Save to disk** — a confirmation reminds you to be on the main menu.
6. Load the slot in-game.

Auto-backups are written before every save, alongside the original file
as `save_N.dat.bak.<unix-timestamp>`.

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
The package auto-wires the bundled libraries on import; if you still see
the error, set them yourself:

```bash
export TCL_LIBRARY="$(python3 -c 'import sys, pathlib; print(pathlib.Path(sys.base_prefix) / "lib" / "tcl8.6")')"
export TK_LIBRARY="$(python3 -c 'import sys, pathlib; print(pathlib.Path(sys.base_prefix) / "lib" / "tk8.6")')"
```

### Edits don't stick after relaunching the game
Steam Cloud is overwriting your changes — see [the Steam Cloud section](#%EF%B8%8F-steam-cloud--read-this-first)
above.

---

## Development

```bash
uv sync --all-extras --dev
uv run pre-commit install
uv run pytest
uv run ruff check .
uv run ruff format .
```

---

## How it works

Both games share the same save framework — the PixelCrushers Save
System Unity asset — with identical encryption, container, and inner
serialisation. Only the Unity ``persistentDataPath`` and the variable
vocabulary differ. The editor's `cs_save_editor.games` module captures
those two differences as a small `GameConfig` per game; everything else
(`crypto`, `format`, `cli`, `gui`) is game-agnostic.

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
and patches doubles in place.

The password `WakeUpSleeper` lives in the Unity-serialized
`CrossPlatformSavedGameDataStorer` MonoBehaviour. PixelCrushers
SaveSystem ships with a default of `"My Password"`; the game devs
overrode it in the Unity Inspector.

---

## Disclaimer

Use at your own risk. Editing save files can produce in-game states the
developers never intended. The editor always writes a backup before
overwriting, but Steam Cloud sync can still overwrite your local file if
you don't follow the procedure above. Don't use this for online
achievements or anything that interacts with leaderboards.

This project is not affiliated with Jump Over The Age, Fellow Traveller,
Pixel Crushers LLC, or Valve. *Citizen Sleeper* and *Citizen Sleeper 2:
Starward Vector* are trademarks of their owners. Steam library cover art
shown in the chooser is either read from your local Steam install or
fetched on demand from Steam's public CDN (the same URLs the Steam
client uses). No artwork is bundled in this repository.

---

## License

MIT — see [LICENSE](LICENSE).
