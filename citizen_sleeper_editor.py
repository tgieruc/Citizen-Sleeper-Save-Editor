#!/usr/bin/env python3
"""
Citizen Sleeper Save Editor

A single-file editor for Citizen Sleeper (Jump Over The Age, 2022) save files.

What it edits: Player_Bits (money), Player_Energy, Player_Condition,
Cycle (day number), and any other numeric Lua variable stored in the save.

How to use:
  Double-click to launch GUI, or:
    python3 citizen_sleeper_editor.py            # GUI
    python3 citizen_sleeper_editor.py list       # CLI: list editable stats
    python3 citizen_sleeper_editor.py set Player_Bits 9999
    python3 citizen_sleeper_editor.py add Player_Bits 100   # add 100 bits
    python3 citizen_sleeper_editor.py add Player_Bits -50   # remove 50 bits

Save file locations:
  macOS:   ~/Library/Application Support/com.JumpOvertheAge.CitizenSleeper/save_*.dat
  Windows: %USERPROFILE%\\AppData\\LocalLow\\Jump Over the Age\\Citizen Sleeper\\save_*.dat
  Linux:   ~/.config/unity3d/Jump Over the Age/Citizen Sleeper/save_*.dat

⚠️ STEAM CLOUD SYNC ⚠️
Steam syncs cloud → local on game start and local → cloud on game exit.
For edits to actually stick:
  1. Start Citizen Sleeper, get to main menu
  2. While at main menu (game running), run this editor and save your changes
  3. Load the slot in-game
  4. The game saves your modified state back, and Steam syncs it up
Alternative: disable Steam Cloud for Citizen Sleeper in Steam properties.

Original save is always backed up to save_N.dat.bak.<timestamp> before overwriting.

Encryption credits: reversed from Assembly-CSharp-firstpass.dll (PixelCrushers
SaveSystem with DES-CBC, key = PBKDF2-HMAC-SHA1(password, salt[8 from blob],
1000 iter, 8 bytes), IV = same salt). Password 'WakeUpSleeper' lives in the
Unity Inspector value on the CrossPlatformSavedGameDataStorer MonoBehaviour.
"""
import base64, json, os, re, struct, sys, shutil, time
from pathlib import Path

# ---- Locate Tcl/Tk for uv-managed Python ----------------------------------
# uv (and python-build-standalone) bundle tcl/tk under <base_prefix>/lib but
# Tcl's auto-discovery doesn't find them when launched from a venv. We point
# it at the bundled libraries explicitly before tkinter is ever imported.
def _wire_tcl_tk():
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return
    for prefix in (sys.base_prefix, sys.prefix):
        lib = Path(prefix) / "lib"
        if not lib.is_dir(): continue
        tcl_dirs = sorted(lib.glob("tcl8.*"))
        tk_dirs  = sorted(lib.glob("tk8.*"))
        if tcl_dirs and tk_dirs:
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dirs[-1]))
            os.environ.setdefault("TK_LIBRARY",  str(tk_dirs[-1]))
            return
_wire_tcl_tk()

# ---- Auto-install pycryptodome on first run -------------------------------
try:
    from Crypto.Cipher import DES
except ImportError:
    import subprocess
    print("Installing pycryptodome (one-time)...", file=sys.stderr)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--user", "pycryptodome"])
    from Crypto.Cipher import DES

# PBKDF2 is in stdlib (hashlib.pbkdf2_hmac) — no extra dep needed for that.
import hashlib

# ---- Constants ------------------------------------------------------------
PASSWORD = b"WakeUpSleeper"
PBKDF2_ITERATIONS = 1000

# Explicit labels for variables that don't fit an auto-detected pattern.
# Anything matching INV_* or *_COMPLETE gets labeled by friendly_label() below
# without needing an entry here.
KNOWN_STATS = {
    "Player_Bits":      "Bits (currency)",
    "Player_Energy":    "Energy (max)",
    "Player_Condition": "Condition (HP)",
    "Cycle":            "Cycle (current day)",
    "INTUIT":           "Intuit skill",
    "INTERFACE":        "Interface skill",
    "ENGINEER":         "Engineer skill",
    "INTUIT_PERKS":     "Intuit perks",
    "INTERFACE_PERKS":  "Interface perks",
    "ENGINEER_PERKS":   "Engineer perks",
    "MOOD":             "Mood",
    "DieCondition":     "Dice condition (good dice count)",
    "Die1":             "Die 1 value",
    "Die2":             "Die 2 value",
    "Die3":             "Die 3 value",
    "Die4":             "Die 4 value",
    "Die5":             "Die 5 value",
    "LightCycle":       "Light cycle",
    "INV_New":          "Has new item (HUD flag)",
}


def _split_camel(s: str) -> str:
    """ 'GirolleCaps' -> 'Girolle Caps'  (also handles 'TLAcronym' -> 'TL Acronym'). """
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s)


def friendly_label(key: str) -> str:
    """Return a human-readable label for a save variable, or '' if unknown."""
    if key in KNOWN_STATS:
        return KNOWN_STATS[key]
    if key.startswith("INV_") and len(key) > 4:
        return f"Item: {_split_camel(key[4:])}"
    if key.endswith("_COMPLETE"):
        stem = key[:-9].replace("_", " ").title()
        return f"Quest done: {stem}"
    return ""

# ---- Save file discovery --------------------------------------------------

def default_save_dir() -> Path:
    home = Path.home()
    candidates = [
        home / "Library/Application Support/com.JumpOvertheAge.CitizenSleeper",
        home / "AppData/LocalLow/Jump Over the Age/Citizen Sleeper",
        home / ".config/unity3d/Jump Over the Age/Citizen Sleeper",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def list_save_files(save_dir: Path):
    return sorted(p for p in save_dir.glob("save_*.dat") if p.is_file())


# ---- Encryption layer -----------------------------------------------------

def _derive_key(password: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, salt, PBKDF2_ITERATIONS, dklen=8)


def decrypt_save(file_bytes: bytes) -> bytes:
    """File bytes → decoded BinaryFormatter blob."""
    blob = base64.b64decode(file_bytes.strip())
    salt, ct = blob[:8], blob[8:]
    key = _derive_key(PASSWORD, salt)
    pt = DES.new(key, DES.MODE_CBC, salt).decrypt(ct)
    pad = pt[-1]
    if 1 <= pad <= 8 and pt[-pad:] == bytes([pad]) * pad:
        pt = pt[:-pad]
    return base64.b64decode(pt)


def encrypt_save(bf_blob: bytes) -> bytes:
    """BinaryFormatter blob → file bytes (random fresh salt)."""
    inner_b64 = base64.b64encode(bf_blob)
    pad = 8 - (len(inner_b64) % 8)
    padded = inner_b64 + bytes([pad]) * pad
    salt = os.urandom(8)
    key = _derive_key(PASSWORD, salt)
    ct = DES.new(key, DES.MODE_CBC, salt).encrypt(padded)
    return base64.b64encode(salt + ct)


# ---- Inner BinaryFormatter walking ----------------------------------------
# The outer BF wraps a `CS Dialogue Manager` SaveRecord. Its `value` field
# is a base64 string holding ANOTHER BF blob, which itself wraps a
# `DialogueSystemSaver+RawData.bytes` array containing PixelCrushers Lua state
# serialized as a tag stream: S<1B-len><utf8>, N<8B-double>, B<1B-bool>,
# T<8 bytes header><entries>, etc.

def find_inner_base64(bf_blob: bytes) -> tuple[int, int, bytes]:
    """Locate the `CS Dialogue Manager` SaveRecord's base64 value within the
    outer BinaryFormatter blob. Returns (start_offset, length, decoded_bytes)."""
    # The value always starts with this BF blob magic, base64-encoded:
    marker = b"AAEAAAD/////AQAAAAAAAAAMAg"
    start = bf_blob.find(marker)
    if start < 0:
        raise RuntimeError("Could not locate inner CS Dialogue Manager blob")
    end = start
    b64_alphabet = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    while end < len(bf_blob) and bf_blob[end] in b64_alphabet:
        end += 1
    return start, end - start, base64.b64decode(bf_blob[start:end])


def find_lua_tag_stream(inner_bf: bytes) -> tuple[int, int]:
    """Locate the embedded Lua tag stream inside the inner BF blob.
    Returns (offset, length) of the tag stream within inner_bf."""
    # The tag stream is the value of the `bytes` byte[] field on
    # DialogueSystemSaver+RawData. BF encodes byte[]s as
    # 0x09 (ArraySinglePrimitive) ... 0x02 (PrimitiveType=Byte) length(4 bytes LE).
    # An easier heuristic: scan for the first S<len><printable> tag run.
    for i in range(len(inner_bf) - 4):
        if inner_bf[i] == 0x53:
            ln = inner_bf[i+1]
            if 1 <= ln <= 100 and i+2+ln <= len(inner_bf):
                txt = inner_bf[i+2:i+2+ln]
                if all(0x20 <= b < 0x7f for b in txt):
                    # found likely start of tag stream; extend until end of blob
                    return i, len(inner_bf) - i
    raise RuntimeError("Could not locate Lua tag stream")


def parse_pairs(tag_stream: bytes) -> list[tuple[int, str, float]]:
    """Walk the tag stream, returning a list of (number_offset, last_key, value).
    The offset is where the 8-byte double sits, so callers can patch it in place."""
    pairs = []
    last_str = None
    i = 0
    n = len(tag_stream)
    while i < n:
        b = tag_stream[i]
        if b == 0x53:  # S string
            if i + 1 >= n: break
            ln = tag_stream[i+1]
            if i + 2 + ln > n: break
            try:
                last_str = tag_stream[i+2:i+2+ln].decode("utf-8")
            except UnicodeDecodeError:
                last_str = None
            i += 2 + ln
        elif b == 0x4E:  # N number
            if i + 9 > n: break
            val = struct.unpack("<d", tag_stream[i+1:i+9])[0]
            if last_str is not None:
                pairs.append((i + 1, last_str, val))
            i += 9
        elif b == 0x42:  # B bool
            i += 2
        else:
            i += 1
    return pairs


def set_value(bf_blob: bytes, key: str, new_value: float) -> tuple[bytes, float | None]:
    """Return (new_bf_blob, old_value). Modifies the FIRST occurrence of key.
    old_value is None if key not found."""
    inner_start, inner_len, inner_bf = find_inner_base64(bf_blob)
    tag_off, tag_len = find_lua_tag_stream(inner_bf)
    tag_stream = inner_bf[tag_off:tag_off + tag_len]

    pairs = parse_pairs(tag_stream)
    for num_off, k, val in pairs:
        if k == key:
            new_bytes = struct.pack("<d", float(new_value))
            new_tag_stream = tag_stream[:num_off] + new_bytes + tag_stream[num_off+8:]
            new_inner_bf = inner_bf[:tag_off] + new_tag_stream + inner_bf[tag_off+tag_len:]
            new_b64 = base64.b64encode(new_inner_bf)
            # The new base64 string must be the same length as the old one,
            # otherwise the outer BF varint length prefix would need updating.
            if len(new_b64) != inner_len:
                raise RuntimeError(
                    f"Internal size mismatch ({len(new_b64)} vs {inner_len}); refusing to save."
                )
            new_blob = bf_blob[:inner_start] + new_b64 + bf_blob[inner_start+inner_len:]
            return new_blob, val
    return bf_blob, None


def add_value(bf_blob: bytes, key: str, delta: float) -> tuple[bytes, float | None, float | None]:
    """Add `delta` to the current value of `key`. Returns (new_bf, old, new)."""
    # Iterate the FULL pair list (including spurious-named keys) so callers
    # can still operate on any reachable variable even if list_all_pairs
    # filters it out of the display.
    _, _, inner_bf = find_inner_base64(bf_blob)
    off, ln = find_lua_tag_stream(inner_bf)
    for _, k, v in parse_pairs(inner_bf[off:off+ln]):
        if k == key:
            new_bf, old = set_value(bf_blob, key, v + float(delta))
            return new_bf, old, v + float(delta)
    return bf_blob, None, None


_VALID_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")


def list_all_pairs(bf_blob: bytes) -> list[tuple[str, float]]:
    """Return [(key, value)] for all numeric pairs whose key looks like a
    real Lua identifier. The save's Ink script state stores inline JSON that
    can fool a tag-stream walker, so we filter to identifier-shaped names."""
    _, _, inner_bf = find_inner_base64(bf_blob)
    off, ln = find_lua_tag_stream(inner_bf)
    pairs = parse_pairs(inner_bf[off:off+ln])
    return [(k, v) for _, k, v in pairs if _VALID_KEY_RE.match(k)]


# ---- File ops -------------------------------------------------------------

def load_save(path: Path) -> bytes:
    return decrypt_save(path.read_bytes())


def write_save(path: Path, bf_blob: bytes):
    bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    suffix = 0
    while bak.exists():
        suffix += 1
        bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}.{suffix}")
    shutil.copy2(path, bak)
    path.write_bytes(encrypt_save(bf_blob))
    return bak


# ---- CLI ------------------------------------------------------------------

def cli_list(save_path: Path):
    bf = load_save(save_path)
    pairs = list_all_pairs(bf)
    # Sort: known stats first, then alphabetical
    pairs.sort(key=lambda kv: (0 if friendly_label(kv[0]) else 1, kv[0]))
    print(f"# {len(pairs)} numeric variables in {save_path.name}")
    for k, v in pairs:
        desc = friendly_label(k)
        marker = "⭐" if desc else "  "
        val_s = str(int(v)) if v == int(v) else str(v)
        print(f"  {marker} {k:<40} = {val_s:<10}  {desc}")


def cli_set(save_path: Path, key: str, value: str):
    bf = load_save(save_path)
    try:
        new_val = float(value)
    except ValueError:
        sys.exit(f"value must be a number, got {value!r}")
    new_bf, old = set_value(bf, key, new_val)
    if old is None:
        sys.exit(f"key not found: {key}")
    bak = write_save(save_path, new_bf)
    print(f"{key}: {old} → {new_val}   (backup: {bak.name})")


def cli_add(save_path: Path, key: str, delta: str):
    bf = load_save(save_path)
    try:
        d = float(delta)
    except ValueError:
        sys.exit(f"delta must be a number, got {delta!r}")
    new_bf, old, new = add_value(bf, key, d)
    if old is None:
        sys.exit(f"key not found: {key}")
    bak = write_save(save_path, new_bf)
    sign = "+" if d >= 0 else ""
    print(f"{key}: {old} {sign}{d} = {new}   (backup: {bak.name})")


# ---- GUI ------------------------------------------------------------------

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    state = {"path": None, "bf": None, "pairs": []}

    root = tk.Tk()
    root.title("Citizen Sleeper Save Editor")
    root.geometry("760x560")

    # Top: file picker
    top = ttk.Frame(root, padding=8); top.pack(fill="x")
    path_var = tk.StringVar(value="(no save loaded)")
    ttk.Label(top, textvariable=path_var, foreground="#555").pack(side="left", fill="x", expand=True)
    def pick():
        save_dir = default_save_dir()
        f = filedialog.askopenfilename(
            initialdir=str(save_dir) if save_dir.exists() else None,
            title="Pick a save_N.dat file",
            filetypes=[("Citizen Sleeper save", "save_*.dat"), ("All files", "*")],
        )
        if f: load(Path(f))
    ttk.Button(top, text="Open save_N.dat...", command=pick).pack(side="right")
    def open_save_dir():
        d = default_save_dir()
        if not d.exists():
            messagebox.showerror("Not found", f"Save directory not found:\n{d}")
            return
        os.system(f'open "{d}"' if sys.platform == 'darwin' else f'xdg-open "{d}"' if sys.platform.startswith('linux') else f'explorer "{d}"')
    ttk.Button(top, text="Open save folder", command=open_save_dir).pack(side="right", padx=4)

    # Filter
    filt_frame = ttk.Frame(root, padding=(8, 0)); filt_frame.pack(fill="x")
    ttk.Label(filt_frame, text="Filter:").pack(side="left")
    filt_var = tk.StringVar()
    ttk.Entry(filt_frame, textvariable=filt_var).pack(side="left", fill="x", expand=True, padx=4)
    only_known = tk.BooleanVar(value=True)
    ttk.Checkbutton(filt_frame, text="Show only labeled (stats, items, quests)", variable=only_known, command=lambda: refresh()).pack(side="right")

    # Table
    cols = ("key", "value", "description")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    tree.heading("key", text="Variable"); tree.column("key", width=300, anchor="w")
    tree.heading("value", text="Value");  tree.column("value", width=120, anchor="e")
    tree.heading("description", text="Description"); tree.column("description", width=300, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    # Edit area
    edit_frame = ttk.Frame(root, padding=8); edit_frame.pack(fill="x")
    ttk.Label(edit_frame, text="New value:").pack(side="left")
    new_var = tk.StringVar()
    ttk.Entry(edit_frame, textvariable=new_var, width=14).pack(side="left", padx=4)
    status_var = tk.StringVar(value="")
    ttk.Label(edit_frame, textvariable=status_var, foreground="#080").pack(side="left", padx=8)

    def refresh():
        for row in tree.get_children():
            tree.delete(row)
        if not state["pairs"]:
            return
        q = filt_var.get().strip().lower()
        for k, v in sorted(state["pairs"], key=lambda kv: (0 if friendly_label(kv[0]) else 1, kv[0])):
            label = friendly_label(k)
            if only_known.get() and not label:
                continue
            if q and q not in k.lower() and q not in label.lower():
                continue
            val_s = str(int(v)) if v == int(v) else str(v)
            tree.insert("", "end", values=(k, val_s, label))
    filt_var.trace_add("write", lambda *_: refresh())

    def on_select(_):
        sel = tree.selection()
        if not sel: return
        item = tree.item(sel[0])
        new_var.set(item["values"][1])
    tree.bind("<<TreeviewSelect>>", on_select)

    def apply_value():
        sel = tree.selection()
        if not sel:
            status_var.set("Pick a row first"); return
        item = tree.item(sel[0])
        key = item["values"][0]
        try: nv = float(new_var.get())
        except ValueError:
            status_var.set("Bad number"); return
        new_bf, old = set_value(state["bf"], key, nv)
        if old is None:
            status_var.set("Key not found"); return
        state["bf"] = new_bf
        # refresh pairs list
        state["pairs"] = list_all_pairs(new_bf)
        refresh()
        status_var.set(f"{key}: {old} → {nv} (not saved yet)")
    ttk.Button(edit_frame, text="Apply", command=apply_value).pack(side="left", padx=4)

    def apply_delta(delta):
        sel = tree.selection()
        if not sel:
            status_var.set("Pick a row first"); return
        key = tree.item(sel[0])["values"][0]
        new_bf, old, new = add_value(state["bf"], key, delta)
        if old is None:
            status_var.set("Key not found"); return
        state["bf"] = new_bf
        state["pairs"] = list_all_pairs(new_bf)
        refresh()
        # try to keep the same row selected
        for row in tree.get_children():
            if tree.item(row)["values"][0] == key:
                tree.selection_set(row); new_var.set(tree.item(row)["values"][1]); break
        sign = "+" if delta >= 0 else ""
        status_var.set(f"{key}: {old} {sign}{delta} = {new} (not saved yet)")

    quick_frame = ttk.Frame(root, padding=(8, 0)); quick_frame.pack(fill="x")
    ttk.Label(quick_frame, text="Quick adjust selected:").pack(side="left")
    for d in (-100, -10, -1, +1, +10, +100, +1000):
        ttk.Button(quick_frame, text=f"{d:+d}", width=6, command=lambda x=d: apply_delta(x)).pack(side="left", padx=2)

    def save_now():
        if state["bf"] is None or state["path"] is None:
            return
        if not messagebox.askyesno(
            "Confirm",
            "Have you started the game and reached the main menu? "
            "Steam Cloud will overwrite this file if you save while the game is closed.\n\n"
            "Proceed with writing the modified save?",
        ):
            return
        bak = write_save(state["path"], state["bf"])
        status_var.set(f"Saved. Backup: {bak.name}")
    ttk.Button(edit_frame, text="💾 Save to disk", command=save_now).pack(side="right")

    def load(path: Path):
        try:
            state["bf"] = load_save(path)
            state["pairs"] = list_all_pairs(state["bf"])
            state["path"] = path
            path_var.set(f"📂 {path}")
            status_var.set(f"Loaded {len(state['pairs'])} variables.")
            refresh()
        except Exception as e:
            messagebox.showerror("Load failed", str(e))

    # Try auto-loading slot 1 if available
    sd = default_save_dir()
    if sd.exists():
        saves = list_save_files(sd)
        if saves:
            load(saves[0])

    root.mainloop()


# ---- Main -----------------------------------------------------------------

def main():
    if len(sys.argv) == 1:
        run_gui(); return

    cmd = sys.argv[1]
    save_dir = default_save_dir()
    saves = list_save_files(save_dir) if save_dir.exists() else []

    def pick_save():
        if not saves:
            sys.exit(f"No save files found in {save_dir}")
        return saves[0]

    if cmd == "list":
        sp = Path(sys.argv[2]) if len(sys.argv) > 2 else pick_save()
        cli_list(sp)
    elif cmd == "set":
        if len(sys.argv) < 4:
            sys.exit("usage: set KEY VALUE [save_path]")
        key, value = sys.argv[2], sys.argv[3]
        sp = Path(sys.argv[4]) if len(sys.argv) > 4 else pick_save()
        cli_set(sp, key, value)
    elif cmd == "add":
        if len(sys.argv) < 4:
            sys.exit("usage: add KEY DELTA [save_path]")
        key, delta = sys.argv[2], sys.argv[3]
        sp = Path(sys.argv[4]) if len(sys.argv) > 4 else pick_save()
        cli_add(sp, key, delta)
    elif cmd in ("-h", "--help", "help"):
        print(__doc__)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
