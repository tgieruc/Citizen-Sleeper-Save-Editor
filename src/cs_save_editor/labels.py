"""Friendly names + fuzzy ranking for save variables.

The save contains hundreds of numeric variables. Most have machine-style
names (``Player_Bits``, ``INV_GirolleCaps``, ``AMBERHULLREPAIRS_COMPLETE``).
We attach human-readable labels so the GUI can show a "what does this do"
column, and we provide a fuzzy ranker so the search box can put the most
relevant match first.
"""

from __future__ import annotations

import re

KNOWN_STATS: dict[str, str] = {
    "Player_Bits": "Bits (currency)",
    "Player_Energy": "Energy (max)",
    "Player_Condition": "Condition (HP)",
    "Player_UpgradePoints": "Unspent improvement points",
    "Cycle": "Cycle (current day)",
    "INTUIT": "Intuit skill",
    "INTERFACE": "Interface skill",
    "ENGINEER": "Engineer skill",
    "ENDURE": "Endure skill",
    "INTUIT_PERKS": "Intuit perks",
    "INTERFACE_PERKS": "Interface perks",
    "ENGINEER_PERKS": "Engineer perks",
    "ENDURE_PERKS": "Endure perks",
    "UpgradeAvailable": "Improvement-available HUD flag",
    "ContinueAvailable": "Continue-available HUD flag",
    "MOOD": "Mood",
    "DieCondition": "Dice condition (good dice count)",
    "Die1": "Die 1 value",
    "Die2": "Die 2 value",
    "Die3": "Die 3 value",
    "Die4": "Die 4 value",
    "Die5": "Die 5 value",
    "LightCycle": "Light cycle",
    "SaveSlot": "Save slot index",
    "INV_New": "Has new item (HUD flag)",
}
"""Explicit labels for variables that don't fit one of the patterns below."""


def _split_camel(s: str) -> str:
    """``'GirolleCaps' -> 'Girolle Caps'`` (also handles ``'TLAcronym'``)."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s)


def friendly_label(key: str) -> str:
    """Return a human-readable label for a save variable, or ``""`` if unknown."""
    if key in KNOWN_STATS:
        return KNOWN_STATS[key]
    if key.startswith("INV_") and len(key) > 4:
        return f"Item: {_split_camel(key[4:])}"
    if key.endswith("_COMPLETE"):
        stem = key[:-9].replace("_", " ").title()
        return f"Quest done: {stem}"
    return ""


def fuzzy_score(query: str, key: str, label: str = "") -> int:  # noqa: PLR0911 — one return per tier
    """Rank a ``(key, label)`` row against ``query``.

    Returns 0 for no match, higher = better. Designed to feel like an IDE
    quick-open: literal substring matches beat subsequence matches, and key
    matches outrank label matches.

    Tiers (rough):

    ===== =====  =================================================
    Score Tier   Example
    ===== =====  =================================================
    1000  Exact  ``query == key``  (case-insensitive)
     900  Prefix ``key.startswith(query)``
    700+  Sub    substring inside key (earlier offset = higher)
    500+  Sub    substring inside label
    100+  Seq    subsequence inside key (tight grouping = higher)
     50+  Seq    subsequence inside label
       0  None   no match
    ===== =====  =================================================
    """
    q = query.strip().lower()
    if not q:
        return 1  # empty query: keep everything visible, no preferred order
    k = key.lower()
    label_lc = label.lower()

    if k == q:
        return 1000
    if k.startswith(q):
        return 900
    if q in k:
        return max(700, 800 - k.find(q) - len(k) // 20)
    if label_lc and q in label_lc:
        return max(500, 600 - label_lc.find(q) - len(label_lc) // 20)

    def subseq(haystack: str) -> int:
        i = 0
        positions: list[int] = []
        for qc in q:
            while i < len(haystack):
                if haystack[i] == qc:
                    positions.append(i)
                    i += 1
                    break
                i += 1
            else:
                return 0
        span = positions[-1] - positions[0] + 1
        return max(100, 400 - span)

    if s := subseq(k):
        return s
    if s := subseq(label_lc):
        return max(50, s - 100)
    return 0
