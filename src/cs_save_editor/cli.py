"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .format import add_value, list_numeric_pairs, set_value
from .labels import friendly_label
from .saves import default_save_dir, list_save_files, load_save, write_save


def _resolve_save(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists():
            sys.exit(f"save not found: {p}")
        return p
    saves = list_save_files(default_save_dir())
    if not saves:
        sys.exit(f"no save files found in {default_save_dir()}")
    return saves[0]


def cmd_list(args: argparse.Namespace) -> int:
    save = _resolve_save(args.save)
    pairs = list_numeric_pairs(load_save(save))
    pairs.sort(key=lambda kv: (0 if friendly_label(kv[0]) else 1, kv[0]))
    print(f"# {len(pairs)} numeric variables in {save.name}")
    for k, v in pairs:
        desc = friendly_label(k)
        marker = "⭐" if desc else "  "
        val_s = str(int(v)) if v == int(v) else str(v)
        print(f"  {marker} {k:<40} = {val_s:<10}  {desc}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    save = _resolve_save(args.save)
    bf = load_save(save)
    new_bf, old = set_value(bf, args.key, args.value)
    if old is None:
        sys.exit(f"key not found: {args.key}")
    bak = write_save(save, new_bf)
    print(f"{args.key}: {old} → {args.value}   (backup: {bak.name})")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    save = _resolve_save(args.save)
    bf = load_save(save)
    new_bf, old, new = add_value(bf, args.key, args.delta)
    if old is None:
        sys.exit(f"key not found: {args.key}")
    bak = write_save(save, new_bf)
    sign = "+" if args.delta >= 0 else ""
    print(f"{args.key}: {old} {sign}{args.delta} = {new}   (backup: {bak.name})")
    return 0


def cmd_gui(_: argparse.Namespace) -> int:
    # Lazy import: avoid loading tkinter (and its Tcl init) for `list`/`set`/`add`.
    from .gui import run_gui  # noqa: PLC0415

    run_gui()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cs-save-editor",
        description="Edit Citizen Sleeper save files (Bits, Energy, Cycle, items…).",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="list every editable numeric variable")
    p_list.add_argument("save", nargs="?", help="path to save_N.dat (default: auto-detect)")
    p_list.set_defaults(func=cmd_list)

    p_set = sub.add_parser("set", help="set a variable to an absolute value")
    p_set.add_argument("key")
    p_set.add_argument("value", type=float)
    p_set.add_argument("save", nargs="?")
    p_set.set_defaults(func=cmd_set)

    p_add = sub.add_parser("add", help="add a delta to a variable (use negative to subtract)")
    p_add.add_argument("key")
    p_add.add_argument("delta", type=float)
    p_add.add_argument("save", nargs="?")
    p_add.set_defaults(func=cmd_add)

    p_gui = sub.add_parser("gui", help="launch the graphical editor (default)")
    p_gui.set_defaults(func=cmd_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        return cmd_gui(args)
    return args.func(args)
