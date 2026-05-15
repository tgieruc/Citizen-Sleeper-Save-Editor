# Changelog

All notable changes to this project will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Restructure as a proper `src/` layout Python package
  (`cs_save_editor`) with one module per responsibility:
  `crypto`, `format`, `labels`, `saves`, `cli`, `gui`.
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
