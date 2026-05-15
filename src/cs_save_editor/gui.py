"""Tkinter GUI for editing save variables."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .format import add_value, list_numeric_pairs, set_value
from .labels import friendly_label, fuzzy_score
from .saves import default_save_dir, list_save_files, load_save, write_save

QUICK_ADJUST_DELTAS = (-100, -10, -1, +1, +10, +100, +1000)


def run_gui() -> None:
    state: dict[str, object] = {"path": None, "bf": None, "pairs": []}

    root = tk.Tk()
    root.title("Citizen Sleeper Save Editor")
    root.geometry("760x560")

    # --- top: file controls ------------------------------------------------
    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    path_var = tk.StringVar(value="(no save loaded)")
    ttk.Label(top, textvariable=path_var, foreground="#555").pack(
        side="left", fill="x", expand=True
    )

    def pick_file() -> None:
        sd = default_save_dir()
        path = filedialog.askopenfilename(
            initialdir=str(sd) if sd.exists() else None,
            title="Pick a save_N.dat file",
            filetypes=[("Citizen Sleeper save", "save_*.dat"), ("All files", "*")],
        )
        if path:
            load(Path(path))

    ttk.Button(top, text="Open save_N.dat…", command=pick_file).pack(side="right")

    def open_save_dir() -> None:
        sd = default_save_dir()
        if not sd.exists():
            messagebox.showerror("Not found", f"Save directory not found:\n{sd}")
            return
        if sys.platform == "darwin":
            os.system(f'open "{sd}"')
        elif sys.platform.startswith("linux"):
            os.system(f'xdg-open "{sd}"')
        else:
            os.system(f'explorer "{sd}"')

    ttk.Button(top, text="Open save folder", command=open_save_dir).pack(side="right", padx=4)

    # --- filter / search row -----------------------------------------------
    filt_frame = ttk.Frame(root, padding=(8, 0))
    filt_frame.pack(fill="x")
    ttk.Label(filt_frame, text="Search:").pack(side="left")
    filt_var = tk.StringVar()
    ttk.Entry(filt_frame, textvariable=filt_var).pack(side="left", fill="x", expand=True, padx=4)
    only_known = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        filt_frame,
        text="Show only labeled (stats, items, quests)",
        variable=only_known,
        command=lambda: refresh(),  # noqa: PLW0108 — forward reference to refresh() defined below
    ).pack(side="right")

    # --- table -------------------------------------------------------------
    cols = ("key", "value", "description")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    tree.heading("key", text="Variable")
    tree.column("key", width=300, anchor="w")
    tree.heading("value", text="Value")
    tree.column("value", width=120, anchor="e")
    tree.heading("description", text="Description")
    tree.column("description", width=300, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    # --- edit controls -----------------------------------------------------
    edit_frame = ttk.Frame(root, padding=8)
    edit_frame.pack(fill="x")
    ttk.Label(edit_frame, text="New value:").pack(side="left")
    new_var = tk.StringVar()
    ttk.Entry(edit_frame, textvariable=new_var, width=14).pack(side="left", padx=4)
    status_var = tk.StringVar(value="")
    ttk.Label(edit_frame, textvariable=status_var, foreground="#080").pack(side="left", padx=8)

    def refresh() -> None:
        for row in tree.get_children():
            tree.delete(row)
        if not state["pairs"]:
            return
        query = filt_var.get().strip()

        rows: list[tuple[int, str, float, str]] = []
        for k, v in state["pairs"]:  # type: ignore[union-attr]
            label = friendly_label(k)
            if only_known.get() and not label:
                continue
            score = fuzzy_score(query, k, label)
            if query and score == 0:
                continue
            rows.append((score, k, v, label))

        if query:
            rows.sort(key=lambda r: (-r[0], r[1]))
        else:
            rows.sort(key=lambda r: (0 if r[3] else 1, r[1]))

        for _, k, v, label in rows:
            val_s = str(int(v)) if v == int(v) else str(v)
            tree.insert("", "end", values=(k, val_s, label))

        if query:
            status_var.set(f"{len(rows)} match{'es' if len(rows) != 1 else ''}")
        else:
            status_var.set("")

    filt_var.trace_add("write", lambda *_: refresh())

    def on_select(_event: object) -> None:
        sel = tree.selection()
        if not sel:
            return
        item = tree.item(sel[0])
        new_var.set(item["values"][1])

    tree.bind("<<TreeviewSelect>>", on_select)

    def apply_value() -> None:
        sel = tree.selection()
        if not sel:
            status_var.set("Pick a row first")
            return
        key = tree.item(sel[0])["values"][0]
        try:
            nv = float(new_var.get())
        except ValueError:
            status_var.set("Bad number")
            return
        new_bf, old = set_value(state["bf"], key, nv)  # type: ignore[arg-type]
        if old is None:
            status_var.set("Key not found")
            return
        state["bf"] = new_bf
        state["pairs"] = list_numeric_pairs(new_bf)
        refresh()
        status_var.set(f"{key}: {old} → {nv} (not saved yet)")

    ttk.Button(edit_frame, text="Apply", command=apply_value).pack(side="left", padx=4)

    def apply_delta(delta: int) -> None:
        sel = tree.selection()
        if not sel:
            status_var.set("Pick a row first")
            return
        key = tree.item(sel[0])["values"][0]
        new_bf, old, new = add_value(state["bf"], key, delta)  # type: ignore[arg-type]
        if old is None:
            status_var.set("Key not found")
            return
        state["bf"] = new_bf
        state["pairs"] = list_numeric_pairs(new_bf)
        refresh()
        for row in tree.get_children():
            if tree.item(row)["values"][0] == key:
                tree.selection_set(row)
                new_var.set(tree.item(row)["values"][1])
                break
        sign = "+" if delta >= 0 else ""
        status_var.set(f"{key}: {old} {sign}{delta} = {new} (not saved yet)")

    quick_frame = ttk.Frame(root, padding=(8, 0))
    quick_frame.pack(fill="x")
    ttk.Label(quick_frame, text="Quick adjust selected:").pack(side="left")
    for d in QUICK_ADJUST_DELTAS:
        ttk.Button(
            quick_frame,
            text=f"{d:+d}",
            width=6,
            command=lambda x=d: apply_delta(x),
        ).pack(side="left", padx=2)

    def save_now() -> None:
        if state["bf"] is None or state["path"] is None:
            return
        ok = messagebox.askyesno(
            "Confirm save",
            "Have you started the game and reached the main menu?\n\n"
            "Steam Cloud will overwrite this file if you save while the game "
            "is closed. Proceed with writing the modified save?",
        )
        if not ok:
            return
        bak = write_save(state["path"], state["bf"])  # type: ignore[arg-type]
        status_var.set(f"Saved. Backup: {bak.name}")

    ttk.Button(edit_frame, text="💾 Save to disk", command=save_now).pack(side="right")

    def load(path: Path) -> None:
        try:
            state["bf"] = load_save(path)
            state["pairs"] = list_numeric_pairs(state["bf"])  # type: ignore[arg-type]
            state["path"] = path
            path_var.set(f"📂 {path}")
            status_var.set(f"Loaded {len(state['pairs'])} variables.")
            refresh()
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))

    # Auto-load slot 1 if available
    sd = default_save_dir()
    if sd.exists():
        saves = list_save_files(sd)
        if saves:
            load(saves[0])

    root.mainloop()
