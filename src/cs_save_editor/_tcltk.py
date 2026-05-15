"""Tcl/Tk library path wiring for uv-managed Python.

uv (and python-build-standalone) bundle the Tcl/Tk libraries under
``<base_prefix>/lib`` but Tcl's auto-discovery can't find them when launched
from a venv. We point Tcl at the bundled directories explicitly *before*
``tkinter`` is ever imported.

Importing this module is enough — it runs once on import.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _wire_tcl_tk() -> None:
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return
    for prefix in (sys.base_prefix, sys.prefix):
        lib = Path(prefix) / "lib"
        if not lib.is_dir():
            continue
        tcl_dirs = sorted(lib.glob("tcl8.*"))
        tk_dirs = sorted(lib.glob("tk8.*"))
        if tcl_dirs and tk_dirs:
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dirs[-1]))
            os.environ.setdefault("TK_LIBRARY", str(tk_dirs[-1]))
            return


_wire_tcl_tk()
