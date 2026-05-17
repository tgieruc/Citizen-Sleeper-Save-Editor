"""Per-game configuration registry.

Citizen Sleeper 1 (``Citizen Sleeper``, 2022) and Citizen Sleeper 2
(``Starward Vector``, 2025) share the same save framework — PixelCrushers
Save System with DES-CBC encryption (password ``"WakeUpSleeper"``), .NET
BinaryFormatter outer container, PixelCrushers Lua tag stream inside.
:mod:`.crypto` and :mod:`.format` are therefore game-agnostic.

What differs per game:

* Unity company/product directory (``Application.persistentDataPath``).
* Slot filename pattern. CS2 keeps rolling auto-backups
  (``save_1.backup.dat``, ``.backup2.dat``, ``.backup3.dat``) and a
  ``saveinfo.dat`` menu-metadata file alongside the actual slots; CS1 has
  neither.
* The variable vocabulary the game writes into the save: CS2 adds ship
  resources (Fuel, Supplies), crew state, per-die health, contracts, and
  the Engage skill that CS1 didn't have.

A :class:`GameConfig` bundles those differences. :data:`GAMES` is the
public registry; :func:`detect_game` picks the right one based on which
save directories actually exist on disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GameConfig:
    """Per-game settings used by the editor.

    Attributes:
        id: Short stable identifier (``"cs1"``, ``"cs2"``) used by the
            ``--game`` CLI flag and the GUI dropdown.
        title: Human-readable title shown in the GUI window title.
        release_year: Release year (used in chooser tile subtitles).
        save_dir_candidates: Possible save directories in OS preference
            order — the first existing one wins. Use ``~`` for home; this
            is expanded at lookup time so each user's home is respected.
        slot_pattern: Regex that matches an active save slot's filename.
            Must reject auto-backups and metadata files.
        known_stats: Explicit ``{variable_name: "Human label"}`` entries
            for variables that don't fit the generic patterns
            (``INV_*``, ``*_COMPLETE``).
        featured_keys: Variables pinned to the top of the GUI list, in
            this exact order.
        contract_prefix: If non-empty, variables starting with this
            prefix get labelled as ``"Contract: <name>"``. CS2 uses
            ``"C_"`` for its contract system; CS1 doesn't have contracts.
        steam_appid: Steam application ID, used to locate cover artwork in
            the local Steam library cache. ``None`` if the game isn't on
            Steam (or we just don't have cover support for it).
    """

    id: str
    title: str
    release_year: int
    save_dir_candidates: tuple[Path, ...]
    slot_pattern: re.Pattern[str]
    known_stats: dict[str, str] = field(default_factory=dict)
    featured_keys: tuple[str, ...] = ()
    contract_prefix: str = ""
    steam_appid: int | None = None

    def save_dir(self) -> Path:
        """Return the first existing candidate, or the first candidate as a
        fallback so it's always usable as a file-picker starting point."""
        for c in self.save_dir_candidates:
            expanded = c.expanduser()
            if expanded.is_dir():
                return expanded
        return self.save_dir_candidates[0].expanduser()

    def cover_path(self) -> Path | None:
        """Locate the game's 600x900 portrait cover in the local Steam cache.

        Returns ``None`` if Steam isn't installed, the appid is unknown,
        or the cover hasn't been cached yet (Steam downloads them lazily,
        usually on first library view).

        Handles both Steam library cache layouts:

        * **Flat** (older clients): ``<cache>/<appid>/library_600x900.jpg``.
        * **Hashed** (newer clients): ``<cache>/<appid>/<sha>/library_600x900.jpg``,
          where each artwork variant lives in its own content-addressed
          subdir.
        """
        if self.steam_appid is None:
            return None
        for root in _STEAM_LIBRARY_CACHES:
            base = root.expanduser() / str(self.steam_appid)
            if not base.is_dir():
                continue
            flat = base / "library_600x900.jpg"
            if flat.is_file():
                return flat
            # New hashed layout: glob any direct subdir for the same filename.
            for sub in base.iterdir():
                if sub.is_dir():
                    nested = sub / "library_600x900.jpg"
                    if nested.is_file():
                        return nested
        return None


_STEAM_LIBRARY_CACHES: tuple[Path, ...] = (
    Path("~/Library/Application Support/Steam/appcache/librarycache"),  # macOS
    Path("~/.local/share/Steam/appcache/librarycache"),  # Linux
    Path("~/.steam/steam/appcache/librarycache"),  # Linux (alt)
    Path("C:/Program Files (x86)/Steam/appcache/librarycache"),  # Windows
)


_CS1_KNOWN_STATS: dict[str, str] = {
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

_CS1_FEATURED: tuple[str, ...] = (
    "Player_Bits",
    "Player_Energy",
    "Player_Condition",
    "Player_UpgradePoints",
    "Cycle",
    "DieCondition",
    "Die1",
    "Die2",
    "Die3",
    "Die4",
    "Die5",
    "INTUIT",
    "INTERFACE",
    "ENGINEER",
    "ENDURE",
    "INTUIT_PERKS",
    "INTERFACE_PERKS",
    "ENGINEER_PERKS",
    "ENDURE_PERKS",
    "MOOD",
)

_CS2_KNOWN_STATS: dict[str, str] = {
    # Resources / ship state
    "Player_Bits": "Bits (currency)",
    "Player_Energy": "Energy",
    "Player_Fuel": "Fuel (ship)",
    "Player_Supplies": "Supplies (ship)",
    "Player_Stress": "Stress",
    "Player_Push": "Push tokens",
    "Player_Glitch": "Glitch dice",
    "Player_UpgradePoints": "Unspent skill points",
    "UpgradeAvailable": "Skill-point-available HUD flag",
    # Day / clock
    "Cycle": "Cycle (current day)",
    "END_CYCLE": "End-of-cycle flag",
    "LIFTOFF": "Liftoff event flag",
    "LightCycle": "Light cycle",
    # Skills
    "INTUIT": "Intuit skill",
    "INTERFACE": "Interface skill",
    "ENGINEER": "Engineer skill",
    "ENDURE": "Endure skill",
    "ENGAGE": "Engage skill",
    "INTUIT_BLOCKED": "Intuit blocked flag",
    "ENDURE_BLOCKED": "Endure blocked flag",
    "ENGAGE_BLOCKED": "Engage blocked flag",
    # Player dice
    "Die1": "Die 1 value",
    "Die2": "Die 2 value",
    "Die3": "Die 3 value",
    "Die4": "Die 4 value",
    "Die5": "Die 5 value",
    "Die1_Health": "Die 1 health",
    "Die2_Health": "Die 2 health",
    "Die3_Health": "Die 3 health",
    "Die4_Health": "Die 4 health",
    "Die5_Health": "Die 5 health",
    "DICEBREAK": "Dice-break flag",
    # Crew
    "CrewNumber": "Crew member count",
    "CrewActions": "Crew actions remaining",
    "Crew1Die1": "Crew 1 die 1",
    "Crew1Die2": "Crew 1 die 2",
    "Crew1_Stress": "Crew 1 stress",
    "Crew1_BROKEN": "Crew 1 broken flag",
    "Crew2Die1": "Crew 2 die 1",
    "Crew2Die2": "Crew 2 die 2",
    "Crew2_Stress": "Crew 2 stress",
    "Crew2_BROKEN": "Crew 2 broken flag",
    "Rig_Stress": "Rig (ship) stress",
    # Contracts
    "CONTRACT_COMPLETED": "Contracts completed (total)",
    "CONTRACT_FAILED": "Contracts failed (total)",
    # UI / misc
    "MOOD": "Mood",
    "SaveSlot": "Save slot index",
    "DIFFICULTY": "Difficulty",
    "INV_New": "Has new item (HUD flag)",
    "ContinueAvailable": "Continue-available HUD flag",
    "INTROTUTORIAL": "Intro tutorial completed",
    "CHECKTUTORIAL": "Skill-check tutorial flag",
    "SKILLCHECK_TUTORIAL": "Skill-check tutorial flag",
    "RIGTUTORIAL": "Rig tutorial completed",
    "TUTORIALSOFF": "Tutorials disabled",
    # Endings / story state
    "NEWGAME": "New-game flag",
    "BADEND": "Bad-end flag",
    "CRISIS": "Crisis flag",
    "DeathTrigger": "Death trigger",
    "INK_OUTCOME": "Ink outcome (last narrative choice)",
}

_CS2_FEATURED: tuple[str, ...] = (
    "Player_Bits",
    "Player_Energy",
    "Player_Fuel",
    "Player_Supplies",
    "Player_Stress",
    "Player_Push",
    "Player_Glitch",
    "Player_UpgradePoints",
    "Cycle",
    "Die1",
    "Die2",
    "Die3",
    "Die4",
    "Die5",
    "Die1_Health",
    "Die2_Health",
    "Die3_Health",
    "Die4_Health",
    "Die5_Health",
    "INTUIT",
    "INTERFACE",
    "ENGINEER",
    "ENDURE",
    "ENGAGE",
    "CrewNumber",
    "CrewActions",
    "Crew1Die1",
    "Crew1Die2",
    "Crew1_Stress",
    "Crew2Die1",
    "Crew2Die2",
    "Crew2_Stress",
    "Rig_Stress",
    "MOOD",
)


CS1 = GameConfig(
    id="cs1",
    title="Citizen Sleeper",
    release_year=2022,
    save_dir_candidates=(
        Path("~/Library/Application Support/com.JumpOvertheAge.CitizenSleeper"),
        Path("~/AppData/LocalLow/Jump Over the Age/Citizen Sleeper"),
        Path("~/.config/unity3d/Jump Over the Age/Citizen Sleeper"),
    ),
    # CS1 has no auto-backup or saveinfo files alongside its save_N.dat.
    slot_pattern=re.compile(r"^save_\d+\.dat$"),
    known_stats=_CS1_KNOWN_STATS,
    featured_keys=_CS1_FEATURED,
    steam_appid=1578650,
)

CS2 = GameConfig(
    id="cs2",
    title="Citizen Sleeper 2: Starward Vector",
    release_year=2025,
    save_dir_candidates=(
        Path("~/Library/Application Support/com.Jump-Over-the-Age.Citizen-Sleeper-2"),
        Path("~/AppData/LocalLow/Jump Over the Age/Citizen Sleeper 2 Starward Vector"),
        Path("~/.config/unity3d/Jump Over the Age/Citizen Sleeper 2 Starward Vector"),
    ),
    # Reject CS2's rolling auto-backups (save_1.backup.dat, .backup2.dat,
    # .backup3.dat) and the saveinfo.dat menu-metadata file.
    slot_pattern=re.compile(r"^save_\d+\.dat$"),
    known_stats=_CS2_KNOWN_STATS,
    featured_keys=_CS2_FEATURED,
    contract_prefix="C_",
    steam_appid=2442460,
)


GAMES: dict[str, GameConfig] = {CS1.id: CS1, CS2.id: CS2}


def detect_game(preferred: str | None = None) -> GameConfig:
    """Pick a :class:`GameConfig`.

    Resolution order:

    1. If ``preferred`` is given, return that game (``KeyError`` if unknown).
    2. If exactly one game's save directory exists on disk, return it.
    3. If multiple games' save directories exist, return CS2 (the newer
       game — favoured because that's likely what's actively being played).
       Callers that need to disambiguate should pass ``preferred`` or use
       :func:`available_games`.
    4. Otherwise return CS2 as the default starting point so file pickers
       open in a sensible location.
    """
    if preferred is not None:
        return GAMES[preferred]
    have = available_games()
    if len(have) == 1:
        return have[0]
    if CS2 in have:
        return CS2
    return CS2


def available_games() -> list[GameConfig]:
    """Return every game whose save directory currently exists on disk."""
    return [
        g for g in GAMES.values() if any(c.expanduser().is_dir() for c in g.save_dir_candidates)
    ]
