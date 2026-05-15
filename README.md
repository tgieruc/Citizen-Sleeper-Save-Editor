# Citizen Sleeper Save Editor

Edit your Citizen Sleeper save files. Money, energy, condition, current cycle,
perks, quest flags — anything stored as a numeric variable.

Works on macOS, Windows, and Linux. Single-file Python tool with both a GUI
and a CLI. Auto-backs up your save before every write.

> **Citizen Sleeper** is a 2022 narrative RPG by Jump Over The Age, published
> by Fellow Traveller. This tool is an independent, unofficial project; it
> isn't affiliated with or endorsed by the developer or publisher.

---

## Features

- **GUI** (tkinter, no extra deps): table of all editable variables, filter,
  inline edit, quick adjust buttons (−100, −10, −1, +1, +10, +100, +1000).
- **CLI**: `list`, `set KEY VALUE`, `add KEY DELTA`.
- **Known stats** are surfaced with friendly descriptions:
  `Player_Bits` (money), `Player_Energy`, `Player_Condition`, `Cycle`,
  `INTUIT`, `INTERFACE`, `ENGINEER_PERKS`, `INTERFACE_PERKS`, `MOOD`,
  `DieCondition`.
- **Auto-backup** before every write — files land alongside the save as
  `save_N.dat.bak.<timestamp>`. Same-second writes get suffixed `.1`, `.2`, …
  so you can't lose your original by editing in rapid succession.
- **Cross-platform save discovery** — finds your save folder automatically on
  macOS, Windows, and Linux.

---

## Requirements

- Python 3.10+ (3.13 recommended)
- One pip package: `pycryptodome` (the script auto-installs it on first run
  if missing)
- Tkinter for the GUI. Stock Python on most systems already has it; if not,
  see [Troubleshooting](#troubleshooting) below.

---

## Quick start

```bash
# 1. Get Python with a working tkinter (uv is the easy way on macOS)
brew install uv
uv venv --python 3.13 ~/cs_editor_env
uv pip install --python ~/cs_editor_env/bin/python pycryptodome

# 2. Launch the GUI
~/cs_editor_env/bin/python citizen_sleeper_editor.py
```

…or if you already have a working `python3` with tkinter:

```bash
python3 citizen_sleeper_editor.py           # GUI
python3 citizen_sleeper_editor.py list      # show all numeric variables
python3 citizen_sleeper_editor.py set Player_Bits 9999
python3 citizen_sleeper_editor.py add Player_Bits 1000     # +1000 bits
python3 citizen_sleeper_editor.py add Player_Bits -50      # −50 bits
```

---

## ⚠️ Steam Cloud — read this first

Citizen Sleeper uses Steam Cloud. Steam syncs:

- **On game launch**: cloud → local (overwrites your edits if the cloud copy
  is newer)
- **On game exit**: local → cloud

So if you edit while the game is closed, the next launch can wipe your work.

### The safe procedure

1. Launch Citizen Sleeper through Steam.
2. Wait at the **main menu** — don't load a save yet. Steam has now finished
   syncing cloud → local.
3. *With the game still running on the main menu*, run the editor and save
   your changes to disk.
4. In-game, click **Continue** / load your slot. Your edits are live.
5. Quit normally. Steam syncs your edited save up to the cloud on exit.

### Alternative

Disable Steam Cloud for the game: right-click Citizen Sleeper in your Steam
library → Properties → General → uncheck *Keep game saves in the Steam Cloud*.
Then you can edit anytime, no menu dance.

---

## GUI walkthrough

1. Launch the GUI (see Quick start). Your slot 1 save loads automatically if
   it exists.
2. The table shows all editable numeric variables. The "Show only known
   stats" checkbox limits it to the ⭐ ones with friendly names; uncheck to
   see everything (≈450 variables).
3. Click a row, then either:
   - type a new value and click **Apply**, or
   - click one of the quick adjust buttons to bump it by ±1, ±10, ±100, ±1000.
4. Click **💾 Save to disk**. You'll get a confirmation prompt reminding you
   to be on the main menu.
5. Load the slot in-game.

---

## Save file locations

- **macOS**: `~/Library/Application Support/com.JumpOvertheAge.CitizenSleeper/save_N.dat`
- **Windows**: `%USERPROFILE%\AppData\LocalLow\Jump Over the Age\Citizen Sleeper\save_N.dat`
- **Linux**: `~/.config/unity3d/Jump Over the Age/Citizen Sleeper/save_N.dat`

The editor finds these automatically; the GUI also has an "Open save folder"
button.

---

## Tests

```bash
python3 test_citizen_sleeper_editor.py
```

29 tests covering the crypto layer (round-trip, salt randomness, blob size
invariants), pair extraction, `set_value` / `add_value` semantics, file ops
(backup correctness, rapid-write deduplication), and the key-shape filter.

The tests use a snapshot of a real save at `/tmp/save_snapshot.dat`. If it's
missing they'll copy from your live save dir.

---

## How it works

The Citizen Sleeper save format is a Russian doll:

| Layer | Format |
|---|---|
| Bytes on disk | base64 |
| First decode | 8-byte salt ‖ DES-CBC ciphertext (PKCS7 padded) |
| Decrypt | key = PBKDF2-HMAC-SHA1(`"WakeUpSleeper"`, salt, 1000 iter, 8 bytes); IV = salt |
| Inner result | base64 again |
| Second decode | .NET BinaryFormatter blob (`PixelCrushers.SavedGameData`) |
| Inside that | `m_dict["2 - CS - MAIN"]` → list of `SaveRecord`, one per saved component |
| `SaveRecord.value` (one of them is `"CS Dialogue Manager"`) | yet another base64 BF blob |
| Inside that | a PixelCrushers Lua tag stream: `S<len><utf8>`, `N<8-byte double>`, `B<bool>`, `T<header>…` |

The editor walks the inner tag stream looking for `S<key> N<value>` pairs
and patches doubles in place — same byte width every time, so the rest of
the file stays untouched.

The password `WakeUpSleeper` lives in the Unity-serialized
`CrossPlatformSavedGameDataStorer` MonoBehaviour
(`sharedassets1.assets`, path_id 1885). PixelCrushers SaveSystem ships with a
default of `"My Password"`; the game devs overrode it in the Unity Inspector
and the value gets baked into the build's asset bundle.

PixelCrushers (the Dialogue System / Save System asset that Citizen Sleeper
uses) is a commercial Unity asset by Pixel Crushers, LLC. The encryption
scheme described here is from their public API surface
([EncryptionUtility](https://www.pixelcrushers.com/dialogue_system/manual2x/html/class_pixel_crushers_1_1_encryption_utility.html));
this project re-implements only the decryption needed to read a user's own
save file.

---

## Troubleshooting

### `ModuleNotFoundError: No module named '_tkinter'`
Your Python build doesn't include tkinter. Easiest fix on macOS:

```bash
brew install uv
uv venv --python 3.13 ~/cs_editor_env
uv pip install --python ~/cs_editor_env/bin/python pycryptodome
~/cs_editor_env/bin/python citizen_sleeper_editor.py
```

On Debian/Ubuntu: `sudo apt install python3-tk`. On Fedora:
`sudo dnf install python3-tkinter`.

### `_tkinter.TclError: Can't find a usable init.tcl`
The Python build has the tkinter C module but not the Tcl/Tk library files,
which is a common quirk of [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
(used by uv and Rye). The editor already handles this — it looks for the
bundled libraries under `<base_prefix>/lib` and sets `TCL_LIBRARY` /
`TK_LIBRARY` automatically. If you still see the error, set them yourself:

```bash
export TCL_LIBRARY="$(dirname "$(python3 -c 'import sys; print(sys.executable)')")"/../lib/tcl8.6
export TK_LIBRARY=$(dirname "$TCL_LIBRARY")/tk8.6
```

### "Key not found"
Some variables only exist after specific in-game events. Run `list` to see
exactly what's in your save right now.

### Edits don't stick after relaunching the game
Steam Cloud is overwriting your changes — see [the Steam Cloud
section](#%EF%B8%8F-steam-cloud--read-this-first) above.

---

## Disclaimer

Use at your own risk. Editing save files can produce in-game states the
developers never intended. The editor always writes a backup before
overwriting, but Steam Cloud sync can still overwrite your local file if you
don't follow the procedure above. Don't use this for online achievements or
anything that interacts with leaderboards.

This project is not affiliated with Jump Over The Age, Fellow Traveller,
Pixel Crushers LLC, or Valve. Citizen Sleeper is a trademark of its owners.

---

## License

MIT — see [LICENSE](LICENSE).
