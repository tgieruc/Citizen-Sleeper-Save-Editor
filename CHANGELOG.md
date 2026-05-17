# Changelog

All notable changes to this project will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Citizen Sleeper 2: Starward Vector support.** Same save framework
  (PixelCrushers + DES-CBC + `"WakeUpSleeper"` password), different save
  directory (`com.Jump-Over-the-Age.Citizen-Sleeper-2`), different
  variable vocabulary (ship Fuel / Supplies, Stress, Push tokens, crew,
  Engage skill, per-die health, contracts).
- `cs_save_editor.games` registry with `CS1` and `CS2` `GameConfig`
  entries; auto-detection picks the right one based on which save dir
  exists on disk. CLI accepts `--game cs1|cs2`; GUI has a game dropdown.
- Game-chooser splash window shown on startup when both games' saves
  exist. Tiles use each game's 600x900 Steam library cover (resolved
  from local Steam cache → editor cache → CDN fetch; cached under
  `~/.cache/cs-save-editor/covers/`). Falls back to color-themed text
  tiles if no cover is available.
- CS2 slot listing filters out the game's rolling auto-backups
  (`save_1.backup{,2,3}.dat`) and `saveinfo.dat` metadata file.
- `Player_UpgradePoints` and `UpgradeAvailable` labels for CS2 (was an
  unlabeled value despite being a featured stat).

### Changed
- Restructure as a proper `src/` layout Python package
  (`cs_save_editor`) with one module per responsibility:
  `crypto`, `format`, `labels`, `saves`, `cli`, `gui`, plus the new
  `games` module.
- Add `pyproject.toml` (PEP 621), `uv` lockfile, and a `cs-save-editor` console
  script entry point.
- Configure Ruff for lint + format and pre-commit hooks.
- Add GitHub Actions CI matrix (Linux/macOS/Windows × Python 3.10–3.13).
- Move tests to a `tests/` directory, switch from `unittest` to pytest style,
  introduce shared `conftest.py` fixtures.

## [0.1.0] — 2026-05-15

Initial release. Decrypt, edit, and re-encrypt Citizen Sleeper save files via
either a Tkinter GUI or a `list` / `set` / `add` CLI. Auto-detects save
location on macOS / Windows / Linux, auto-backs up before every write, and
ships with a labelled view of inventory items, quest completion flags, and
the main player stats.
