"""Friendly names + fuzzy ranking for save variables.

The save contains hundreds of numeric variables. Most have machine-style
names (``Player_Bits``, ``INV_GirolleCaps``, ``AMBERHULLREPAIRS_COMPLETE``).
We attach human-readable labels so the GUI can show a "what does this do"
column, and we provide a fuzzy ranker so the search box can put the most
relevant match first.

The per-game variable vocabulary lives in :mod:`.games`. This module
holds the generic pattern matchers (``INV_*`` items, ``*_COMPLETE``
quests, optional ``<prefix>_*`` contracts) and the ranker.
"""

from __future__ import annotations

import re

from .games import CS1, GameConfig

# Default game used by the bare ``friendly_label("X")`` / ``sort_rank("X")``
# entry points. Tests and back-compat callers rely on this defaulting to CS1.
_DEFAULT_GAME: GameConfig = CS1

# Re-exports kept for backwards compatibility with the CS1-only API:
KNOWN_STATS: dict[str, str] = _DEFAULT_GAME.known_stats
FEATURED_KEYS: tuple[str, ...] = _DEFAULT_GAME.featured_keys


def _split_camel(s: str) -> str:
    """``'GirolleCaps' -> 'Girolle Caps'`` (also handles ``'TLAcronym'``)."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s)


def friendly_label(key: str, game: GameConfig = _DEFAULT_GAME) -> str:
    """Return a human-readable label for a save variable, or ``""`` if unknown."""
    if key in game.known_stats:
        return game.known_stats[key]
    if key.startswith("INV_") and len(key) > 4:
        return f"Item: {_split_camel(key[4:])}"
    if key.endswith("_COMPLETE"):
        stem = key[:-9].replace("_", " ").title()
        return f"Quest done: {stem}"
    if (
        game.contract_prefix
        and key.startswith(game.contract_prefix)
        and len(key) > len(game.contract_prefix)
    ):
        return f"Contract: {key[len(game.contract_prefix) :].replace('_', ' ').title()}"
    return ""


def sort_rank(key: str, game: GameConfig = _DEFAULT_GAME) -> tuple[int, int, str]:
    """Sort key for the variable list.

    Returns a tuple suitable for :func:`sorted` that orders:

    1. Featured keys first, in the explicit order of ``game.featured_keys``.
    2. Other labeled keys, alphabetical.
    3. Unlabeled keys, alphabetical (hidden by default in the GUI).
    """
    try:
        idx = game.featured_keys.index(key)
        return (0, idx, key)
    except ValueError:
        pass
    if friendly_label(key, game):
        return (1, 0, key)
    return (2, 0, key)


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
        return 1
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
