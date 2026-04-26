"""Static game data for the Undercover Agent City environment.

Contains: terrain enums, grid layout, NPC roster, claim options, task configs,
NPC dialogue templates. This is the single source of truth for all constants.
"""

import copy
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Terrain(str, Enum):
    ROAD = "road"
    BUILDING = "building"
    ALLEY = "alley"
    SHOP = "shop"
    PARK = "park"
    HIDEOUT = "hideout"
    POLICE_STATION = "police"
    WAREHOUSE = "warehouse"
    SAFE_HOUSE = "safe_house"


class District(str, Enum):
    DOWNTOWN = "downtown"       # rows 0-4
    DOCKS = "docks"             # rows 5-9
    RESIDENTIAL = "residential"  # rows 10-14


class Faction(str, Enum):
    GANG = "gang"
    POLICE = "police"
    CIVILIAN = "civilian"


# Terrain enum to int index mapping
TERRAIN_INDEX = {t: i for i, t in enumerate(Terrain)}
INDEX_TERRAIN = {i: t for t, i in TERRAIN_INDEX.items()}


def get_terrain_name(terrain_int: int) -> str:
    """Map terrain index to its string name."""
    return INDEX_TERRAIN.get(terrain_int, Terrain.ROAD).value


def get_district(y: int) -> District:
    """Return district based on row (y coordinate)."""
    if y <= 4:
        return District.DOWNTOWN
    elif y <= 9:
        return District.DOCKS
    else:
        return District.RESIDENTIAL


# ---------------------------------------------------------------------------
# Grid layout — 15x15 deterministic city (from design doc ASCII map)
# ---------------------------------------------------------------------------

def build_grid() -> list[int]:
    """Build a 15x15 city grid as a flat list of terrain indices.

    Grid layout matches the design doc ASCII map exactly.
    Index = y * 15 + x (row-major order).

    Road rows (full): 2, 5, 8, 11
    Road columns: 4, 8
    Special locations at exact coordinates from the map.
    """
    B = TERRAIN_INDEX[Terrain.BUILDING]
    R = TERRAIN_INDEX[Terrain.ROAD]

    # Start with all buildings
    grid = [B] * 225

    # Main road ROWS (full road): y = 2, 5, 8, 11
    for y in (2, 5, 8, 11):
        for x in range(15):
            grid[y * 15 + x] = R

    # Main road COLUMNS: x = 4, x = 8
    for x in (4, 8):
        for y in range(15):
            grid[y * 15 + x] = R

    # Row 0: cols 4-8 are roads (entrance roads at top)
    for x in range(4, 9):
        grid[0 * 15 + x] = R

    # Row 1: col 4 and col 8 are roads (vertical road continuations)
    # (already set by column roads above)

    # Special locations (x, y) -> Terrain
    specials = {
        (1, 1): Terrain.SHOP,           # Bank/shop
        (11, 1): Terrain.SHOP,          # Shop
        (6, 3): Terrain.SHOP,           # Shop
        (2, 4): Terrain.PARK,           # Park
        (5, 13): Terrain.PARK,          # Park
        (1, 7): Terrain.HIDEOUT,        # Gang hideout
        (11, 10): Terrain.HIDEOUT,      # Gang hideout
        (1, 13): Terrain.POLICE_STATION,  # Police station
        (6, 9): Terrain.WAREHOUSE,      # Warehouse (intel location)
        (12, 4): Terrain.SAFE_HOUSE,    # Safe house
        (13, 13): Terrain.SAFE_HOUSE,   # Safe house
    }
    for (x, y), terrain in specials.items():
        grid[y * 15 + x] = TERRAIN_INDEX[terrain]

    return grid


# ---------------------------------------------------------------------------
# NPC Roster — 8 NPCs across 3 factions
# ---------------------------------------------------------------------------

NPC_ROSTER = [
    # Gang (3) — targets for infiltration
    {
        "id": "razor", "name": "Razor", "faction": "gang",
        "x": 7, "y": 1,
        "has_intel": True, "expected_persona": "tough",
        "trust_threshold": 60,
        "trust": 0, "suspicion": 0,
        "facts_heard": {}, "patrol_route": [], "is_witness": False,
    },
    {
        "id": "whisper", "name": "Whisper", "faction": "gang",
        "x": 8, "y": 8,  # Moved to Docks road intersection — reachable from start in 4 moves
        "has_intel": True, "expected_persona": "formal",  # Whisper is the intellectual
        "trust_threshold": 50,
        "trust": 0, "suspicion": 0,
        "facts_heard": {}, "patrol_route": [], "is_witness": False,
    },
    {
        "id": "fang", "name": "Fang", "faction": "gang",
        "x": 4, "y": 5,  # Moved to main road intersection — agent encounters gang early
        "has_intel": False, "expected_persona": "tough",
        "trust_threshold": 999,
        "trust": 0, "suspicion": 0,
        "facts_heard": {}, "patrol_route": [], "is_witness": False,
    },
    # Police (2)
    {
        "id": "handler", "name": "Handler Chen", "faction": "police",
        "x": 13, "y": 1,
        "has_intel": False, "expected_persona": "formal",
        "trust_threshold": 0,
        "trust": 80, "suspicion": 0,
        "facts_heard": {}, "patrol_route": [], "is_witness": False,
    },
    {
        "id": "patrol", "name": "Officer Diaz", "faction": "police",
        "x": 2, "y": 2,
        "has_intel": False, "expected_persona": "formal",
        "trust_threshold": 999,
        "trust": 0, "suspicion": 0,
        "facts_heard": {},
        "patrol_route": [(2, 2), (2, 5), (2, 8), (2, 11), (2, 8), (2, 5)],
        "is_witness": False,
    },
    # Civilians (3)
    {
        "id": "merchant", "name": "Old Man Liu", "faction": "civilian",
        "x": 3, "y": 6,
        "has_intel": False, "expected_persona": "casual",
        "trust_threshold": 999,
        "trust": 0, "suspicion": 0,
        "facts_heard": {}, "patrol_route": [], "is_witness": False,
    },
    {
        "id": "sara", "name": "Sara", "faction": "civilian",
        "x": 4, "y": 12,
        "has_intel": False, "expected_persona": "casual",
        "trust_threshold": 999,
        "trust": 0, "suspicion": 0,
        "facts_heard": {}, "patrol_route": [], "is_witness": False,
    },
    {
        "id": "ravi", "name": "Kid Ravi", "faction": "civilian",
        "x": 4, "y": 11,  # Moved to residential district — away from starting area
        "has_intel": False, "expected_persona": "tough",  # Kid Ravi wants to seem cool
        "trust_threshold": 999,
        "trust": 0, "suspicion": 0,
        "facts_heard": {}, "patrol_route": [], "is_witness": False,
    },
]


def fresh_npcs() -> list[dict]:
    """Return a deep copy of NPC_ROSTER for each episode reset."""
    return copy.deepcopy(NPC_ROSTER)


# ---------------------------------------------------------------------------
# Cover story topics and claim options (5 topics, 4 options each)
# ---------------------------------------------------------------------------

COVER_TOPICS = ["origin", "job", "boss", "reason", "history"]

CLAIM_OPTIONS = {
    "origin": ["southside", "downtown", "out_of_town", "docks"],
    "job": ["smuggler", "driver", "enforcer", "freelancer"],
    "boss": ["solo", "works_for_razor", "works_for_vince", "independent"],
    "reason": ["money", "revenge", "loyalty", "hiding"],
    "history": ["veteran", "newcomer", "returning", "referred"],
}


# ---------------------------------------------------------------------------
# Task configurations
# ---------------------------------------------------------------------------

TASK_CONFIGS = {
    "tutorial_persona": {
        "max_turns": 1,
        "description": "Tutorial: Persona Selection",
        "tutorial": True,
        "spawn_next_to": "razor",  # Start adjacent to a gang NPC
    },
    "tutorial_consistency": {
        "max_turns": 5,
        "description": "Tutorial: Stay Consistent",
        "tutorial": True,
        "spawn_next_to": "razor",  # Start adjacent to gang NPC
    },
    "first_contact": {"max_turns": 30, "description": "First Contact"},
    "earn_trust": {"max_turns": 50, "description": "Earn Trust"},
    "full_job": {"max_turns": 80, "description": "The Full Job"},
}


# ---------------------------------------------------------------------------
# NPC Dialogue Templates — spy-thriller tone
# ---------------------------------------------------------------------------

# Keyed by (trust_level_bucket, persona_correct: bool)
# trust_level_bucket: "low" (0-30), "mid" (31-60), "high" (61-100)
# Uses seeded random.choice in the environment for variety.

NPC_RESPONSES = {
    # --- Correct persona ---
    ("low", True): [
        '{name} looks you over. "You talk the talk. We\'ll see if you walk it."',
        '{name} nods slowly. "Alright. I\'m listening."',
        '{name} leans against the wall. "New face. Let\'s see what you\'re about."',
        '{name} eyes you coldly. "Speak. But choose your words carefully."',
    ],
    ("mid", True): [
        '{name} cracks a thin smile. "You\'re growing on me. Keep it up."',
        '{name} relaxes slightly. "You check out... for now."',
        '{name} gestures you closer. "Word is you\'re solid. I like that."',
        '{name} nods with respect. "Consistent. That matters around here."',
    ],
    ("high", True): [
        '{name} grins. "You\'ve earned your spot. I got something for you."',
        '{name} clasps your shoulder. "Welcome to the inside."',
        '{name} drops their voice. "Listen close. There\'s a job..."',
        '{name} looks both ways. "You\'ve proven yourself. Time for real business."',
    ],
    # --- Wrong persona ---
    ("low", False): [
        '{name} frowns. "Something\'s off about you."',
        '{name} stiffens. "That\'s not how people talk around here."',
        '{name} narrows their eyes. "You don\'t sound like one of us."',
        '{name} steps back. "Watch your tone."',
    ],
    ("mid", False): [
        '{name} scowls. "I thought you were solid. What\'s with the act?"',
        '{name} crosses arms. "That didn\'t sound right. Try again."',
        '{name} looks suspicious. "You slipping, or is this who you really are?"',
    ],
    ("high", False): [
        '{name}\'s expression hardens. "After everything... that\'s how you talk to me?"',
        '{name} looks betrayed. "Something changed. I don\'t like it."',
        '{name} takes a step back. "You\'re not who I thought you were."',
    ],
}


def get_trust_bucket(trust: int) -> str:
    """Classify trust into low/mid/high bucket for dialogue lookup."""
    if trust <= 30:
        return "low"
    elif trust <= 60:
        return "mid"
    else:
        return "high"
