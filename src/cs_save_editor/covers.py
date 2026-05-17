"""On-demand Steam cover-art fetching for the game chooser splash.

The chooser tries three sources, in order, for each game's library
portrait (the 600x900 JPEG Steam uses on its library page):

1. **The user's local Steam library cache** — instant, zero network.
   Populated automatically by Steam whenever you open the game in your
   library. See :meth:`.games.GameConfig.cover_path`.
2. **An editor-managed download cache** at ``~/.cache/cs-save-editor/covers/``
   (XDG / ``LOCALAPPDATA`` aware). Populated by step 3.
3. **Steam's public CDN** (``cdn.cloudflare.steamstatic.com``) — the same
   URL Steam itself uses. Fetched on first run for users who don't have
   Steam installed, or who've never opened the game in their Steam library.
   The downloaded JPEG is saved into the cache so subsequent runs stay
   offline-fast.

If all three fail (no Steam, no network, CDN 404) the chooser draws the
text-only fallback tile instead — nothing is bundled in the repo.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

from .games import GameConfig

_USER_AGENT = "cs-save-editor/0.2 (+https://github.com/tgieruc/citizen-sleeper-save-editor)"
_FETCH_TIMEOUT_SECONDS = 5.0
# Steam covers are >10kB even for tiny indies; anything below is almost
# certainly a Cloudflare error page served with a 200, so reject it.
_MIN_BYTES = 1024


def _user_cache_dir() -> Path:
    """Return the per-user cover-cache directory, creating it on demand.

    Honours ``XDG_CACHE_HOME`` on Linux, ``LOCALAPPDATA`` on Windows, and
    falls back to ``~/.cache`` everywhere else (the de-facto convention on
    macOS for CLI tools).
    """
    env_xdg = os.environ.get("XDG_CACHE_HOME")
    env_local = os.environ.get("LOCALAPPDATA")
    if env_xdg:
        base = Path(env_xdg)
    elif env_local:
        base = Path(env_local)
    else:
        base = Path.home() / ".cache"
    p = base / "cs-save-editor" / "covers"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cached_cover_path(appid: int) -> Path:
    return _user_cache_dir() / f"{appid}_library_600x900.jpg"


def _download_cover(appid: int, dst: Path) -> bool:
    """Fetch the 600x900 portrait from Steam's CDN into ``dst``.

    Returns ``True`` on success. Writes via a ``.part`` sidecar so an
    interrupted download never leaves a half-written file in the cache.
    """
    url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    if len(data) < _MIN_BYTES:
        return False
    tmp = dst.with_suffix(dst.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dst)
    return True


def resolve_cover(game: GameConfig, *, fetch: bool = True) -> Path | None:
    """Return a usable cover image path for ``game``, or ``None``.

    Resolution order: local Steam cache → editor cache → CDN fetch (if
    ``fetch=True``). Returning ``None`` tells the chooser to draw a
    text-only fallback tile instead.
    """
    steam = game.cover_path()
    if steam is not None:
        return steam
    if game.steam_appid is None:
        return None
    cached = _cached_cover_path(game.steam_appid)
    if cached.is_file():
        return cached
    if fetch and _download_cover(game.steam_appid, cached):
        return cached
    return None
