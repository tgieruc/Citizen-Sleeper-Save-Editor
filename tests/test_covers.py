"""Tests for :mod:`cs_save_editor.covers` (Steam CDN cover fetching + cache)."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from cs_save_editor import covers, games


@pytest.fixture
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the cover cache at a throwaway directory.

    The covers module honours ``XDG_CACHE_HOME``; setting it gives us a
    hermetic cache per-test without monkey-patching internals.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    return tmp_path / "cs-save-editor" / "covers"


def _stub_game(appid: int | None = 12345) -> games.GameConfig:
    """A minimal GameConfig with no local Steam cache (forces the fetch path)."""
    return games.GameConfig(
        id="stub",
        title="Stub",
        release_year=2025,
        save_dir_candidates=(Path("/nonexistent"),),
        slot_pattern=re.compile(r"^save_\d+\.dat$"),
        steam_appid=appid,
    )


def test_user_cache_dir_uses_xdg(isolated_cache: Path) -> None:
    d = covers._user_cache_dir()
    assert d == isolated_cache
    assert d.is_dir()


def test_resolve_uses_local_steam_cache_when_present(
    isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Local Steam cache wins — never touches the network."""
    fake_cover = isolated_cache.parent / "steam_pretend.jpg"
    fake_cover.parent.mkdir(parents=True, exist_ok=True)
    fake_cover.write_bytes(b"x" * 2048)
    game = _stub_game()
    monkeypatch.setattr(games.GameConfig, "cover_path", lambda self: fake_cover)
    with patch.object(covers, "_download_cover") as dl:
        result = covers.resolve_cover(game)
    assert result == fake_cover
    dl.assert_not_called()


def test_resolve_fetches_when_steam_cache_missing(
    isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _stub_game(appid=42)
    monkeypatch.setattr(games.GameConfig, "cover_path", lambda self: None)

    def fake_download(appid: int, dst: Path) -> bool:
        dst.write_bytes(b"y" * 2048)
        return True

    with patch.object(covers, "_download_cover", side_effect=fake_download) as dl:
        result = covers.resolve_cover(game)
    assert result == isolated_cache / "42_library_600x900.jpg"
    assert result.is_file()
    dl.assert_called_once_with(42, result)


def test_resolve_uses_editor_cache_on_second_call(
    isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once a cover is cached, subsequent calls don't re-download."""
    game = _stub_game(appid=99)
    monkeypatch.setattr(games.GameConfig, "cover_path", lambda self: None)
    isolated_cache.mkdir(parents=True, exist_ok=True)
    cached = isolated_cache / "99_library_600x900.jpg"
    cached.write_bytes(b"z" * 2048)
    with patch.object(covers, "_download_cover") as dl:
        result = covers.resolve_cover(game)
    assert result == cached
    dl.assert_not_called()


def test_resolve_returns_none_when_download_fails(
    isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _stub_game(appid=7)
    monkeypatch.setattr(games.GameConfig, "cover_path", lambda self: None)
    with patch.object(covers, "_download_cover", return_value=False):
        result = covers.resolve_cover(game)
    assert result is None


def test_resolve_returns_none_without_appid(
    isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _stub_game(appid=None)
    monkeypatch.setattr(games.GameConfig, "cover_path", lambda self: None)
    with patch.object(covers, "_download_cover") as dl:
        result = covers.resolve_cover(game)
    assert result is None
    dl.assert_not_called()


def test_resolve_does_not_fetch_when_fetch_false(
    isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _stub_game(appid=1)
    monkeypatch.setattr(games.GameConfig, "cover_path", lambda self: None)
    with patch.object(covers, "_download_cover") as dl:
        result = covers.resolve_cover(game, fetch=False)
    assert result is None
    dl.assert_not_called()
