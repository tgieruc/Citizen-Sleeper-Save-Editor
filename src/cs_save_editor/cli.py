"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .format import add_value, list_numeric_pairs, set_value
from .games import GAMES, GameConfig, available_games, detect_game
from .labels import friendly_label, sort_rank
from .saves import default_save_dir, list_save_files, load_save, write_save


def _resolve_game(args: argparse.Namespace) -> GameConfig:
    preferred = getattr(args, "game", None)
    if preferred:
        if preferred not in GAMES:
            sys.exit(f"unknown game: {preferred!r}; choices: {', '.join(GAMES)}")
        return GAMES[preferred]
    have = available_games()
    if len(have) > 1:
        ids = ", ".join(g.id for g in have)
        sys.exit(f"saves found for multiple games ({ids}); pick one with --game {{{ids}}}")
    return detect_game()


def _resolve_save(arg: str | None, game: GameConfig) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists():
            sys.exit(f"save not found: {p}")
        return p
    sd = default_save_dir(game)
    saves = list_save_files(sd, game)
    if not saves:
        sys.exit(f"no {game.id} save files found in {sd}")
    return saves[0]


def cmd_list(args: argparse.Namespace) -> int:
    game = _resolve_game(args)
    save = _resolve_save(args.save, game)
    pairs = list_numeric_pairs(load_save(save))
    pairs.sort(key=lambda kv: sort_rank(kv[0], game))
    print(f"# {len(pairs)} numeric variables in {save.name} ({game.id})")
    for k, v in pairs:
        desc = friendly_label(k, game)
        marker = "*" if desc else " "
        val_s = str(int(v)) if v == int(v) else str(v)
        print(f"  {marker} {k:<40} = {val_s:<10}  {desc}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    game = _resolve_game(args)
    save = _resolve_save(args.save, game)
    bf = load_save(save)
    new_bf, old = set_value(bf, args.key, args.value)
    if old is None:
        sys.exit(f"key not found: {args.key}")
    bak = write_save(save, new_bf)
    print(f"{args.key}: {old} -> {args.value}   (backup: {bak.name})")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    game = _resolve_game(args)
    save = _resolve_save(args.save, game)
    bf = load_save(save)
    new_bf, old, new = add_value(bf, args.key, args.delta)
    if old is None:
        sys.exit(f"key not found: {args.key}")
    bak = write_save(save, new_bf)
    sign = "+" if args.delta >= 0 else ""
    print(f"{args.key}: {old} {sign}{args.delta} = {new}   (backup: {bak.name})")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    # Lazy import: avoid loading tkinter (and its Tcl init) for `list`/`set`/`add`.
    from .gui import run_gui  # noqa: PLC0415

    preferred = getattr(args, "game", None)
    run_gui(preferred_game=preferred)
    return 0


def _add_game_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--game",
        choices=sorted(GAMES),
        help="which game's save to operate on (default: auto-detect)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cs-save-editor",
        description="Edit Citizen Sleeper and Citizen Sleeper 2 save files.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="list every editable numeric variable")
    p_list.add_argument("save", nargs="?", help="path to save_N.dat (default: auto-detect)")
    _add_game_arg(p_list)
    p_list.set_defaults(func=cmd_list)

    p_set = sub.add_parser("set", help="set a variable to an absolute value")
    p_set.add_argument("key")
    p_set.add_argument("value", type=float)
    p_set.add_argument("save", nargs="?")
    _add_game_arg(p_set)
    p_set.set_defaults(func=cmd_set)

    p_add = sub.add_parser("add", help="add a delta to a variable (use negative to subtract)")
    p_add.add_argument("key")
    p_add.add_argument("delta", type=float)
    p_add.add_argument("save", nargs="?")
    _add_game_arg(p_add)
    p_add.set_defaults(func=cmd_add)

    p_gui = sub.add_parser("gui", help="launch the graphical editor (default)")
    _add_game_arg(p_gui)
    p_gui.set_defaults(func=cmd_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        return cmd_gui(args)
    return args.func(args)
