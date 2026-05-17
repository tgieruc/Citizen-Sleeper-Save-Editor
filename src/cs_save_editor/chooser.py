"""Startup game-chooser splash.

When both Citizen Sleeper games have saves on the same machine — or when
the user runs the GUI without ``--game`` — the editor shows a small splash
with one tile per game before opening the main window.

Each tile shows the game's Steam library cover (the 600x900 portrait
Steam caches locally for the library view) where available, or a
text-only fallback with the title + release year.

The chooser is **skipped** when only one game's save directory exists on
disk: there's nothing to pick, so it would just be a wasted click. Pass
``force=True`` to show it anyway (used by an explicit menu entry).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .covers import resolve_cover
from .games import GAMES, GameConfig, available_games

_TILE_W = 240
_TILE_H = 360
_COVER_W = 220
_COVER_H = 330  # 600x900 source -> downscaled with the same aspect

# CS-themed accent colours used by the text-only fallback tiles.
_ACCENTS: dict[str, str] = {
    "cs1": "#e8a73c",  # CS1 amber
    "cs2": "#2cb1c4",  # CS2 cyan
}


def _load_cover(game: GameConfig) -> object | None:
    """Return a Tk-compatible image (``PIL.ImageTk.PhotoImage``) for the
    game's Steam cover, or ``None`` if the cover or Pillow isn't available.

    Cover resolution (local Steam cache → editor cache → CDN fetch) lives
    in :func:`.covers.resolve_cover`. The download only happens once per
    machine; subsequent chooser opens are instant.
    """
    cover = resolve_cover(game)
    if cover is None:
        return None
    try:
        from PIL import Image, ImageTk  # noqa: PLC0415
    except ImportError:
        return None
    with Image.open(cover) as raw:
        img = raw.convert("RGB")
        img.thumbnail((_COVER_W, _COVER_H))
    return ImageTk.PhotoImage(img)


def choose_game(preferred: str | None = None, *, force: bool = False) -> GameConfig | None:
    """Show the chooser splash and return the picked game.

    - If ``preferred`` is given and known, return that game immediately.
    - If only one game is installed and ``force`` is false, return it.
    - Otherwise open a modal Tk window with one tile per registered game.
      Returns ``None`` if the user closes the window without picking.
    """
    if preferred is not None and preferred in GAMES:
        return GAMES[preferred]

    have = available_games()
    if not force and len(have) <= 1:
        return have[0] if have else None

    choice: dict[str, GameConfig | None] = {"game": None}

    root = tk.Tk()
    root.title("Citizen Sleeper Save Editor")
    root.resizable(False, False)

    header = ttk.Label(
        root,
        text="Which game's save do you want to edit?",
        font=("TkDefaultFont", 14, "bold"),
        padding=(20, 16, 20, 8),
    )
    header.pack()

    tiles = ttk.Frame(root, padding=(20, 8, 20, 20))
    tiles.pack()

    # Keep image refs alive: Tk discards them when the local goes out of scope.
    image_refs: list[object] = []

    def pick(game: GameConfig) -> None:
        choice["game"] = game
        root.destroy()

    for game in GAMES.values():
        tile = tk.Frame(
            tiles,
            width=_TILE_W,
            height=_TILE_H,
            relief="ridge",
            borderwidth=2,
            cursor="hand2",
        )
        tile.pack_propagate(False)
        tile.pack(side="left", padx=8)

        cover = _load_cover(game)
        if cover is not None:
            image_refs.append(cover)
            label = tk.Label(tile, image=cover)  # type: ignore[arg-type]
            label.pack(pady=(8, 4))
        else:
            accent = _ACCENTS.get(game.id, "#888888")
            placeholder = tk.Frame(tile, width=_COVER_W, height=_COVER_H, bg=accent)
            placeholder.pack_propagate(False)
            placeholder.pack(pady=(8, 4))
            tk.Label(
                placeholder,
                text=game.title.replace(": ", "\n"),
                font=("TkDefaultFont", 16, "bold"),
                bg=accent,
                fg="white",
                wraplength=_COVER_W - 24,
                justify="center",
            ).pack(expand=True, fill="both")

        title = ttk.Label(
            tile,
            text=game.title,
            font=("TkDefaultFont", 12, "bold"),
            wraplength=_TILE_W - 24,
            justify="center",
        )
        title.pack()
        ttk.Label(tile, text=f"({game.release_year})", foreground="#777").pack()

        # Click anywhere on the tile, the cover label, or the placeholder
        # to pick. (Children of the tile inherit the cursor but not the
        # bindings, so wire each.)
        for w in (tile, *tile.winfo_children()):
            w.bind("<Button-1>", lambda _e, g=game: pick(g))
            for c in w.winfo_children() if hasattr(w, "winfo_children") else ():
                c.bind("<Button-1>", lambda _e, g=game: pick(g))

    # Centre on screen — small splash, looks weird in the top-left corner.
    root.update_idletasks()
    w = root.winfo_reqwidth()
    h = root.winfo_reqheight()
    sx = (root.winfo_screenwidth() - w) // 2
    sy = (root.winfo_screenheight() - h) // 3
    root.geometry(f"+{sx}+{sy}")

    root.mainloop()
    return choice["game"]
