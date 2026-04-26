"""Core game engine for the Undercover Agent City environment.

Implements the complete game loop: reset(), step(), state property,
action generation, NPC behavior, fact tracking, contradiction detection,
observation rendering, and task graders.
"""

import copy
import random as stdlib_random
import uuid
from typing import Any, Optional

from openenv.core.env_server.interfaces import Environment

from ..models import CityAction, CityObservation, CityState
from .city_data import (
    CLAIM_OPTIONS,
    COVER_TOPICS,
    NPC_RESPONSES,
    TASK_CONFIGS,
    Terrain,
    TERRAIN_INDEX,
    build_grid,
    fresh_npcs,
    get_district,
    get_terrain_name,
    get_trust_bucket,
)

# Lazy import rubrics -- Plan 03 creates rubrics.py
try:
    from .rubrics import UndercoverRubric

    HAS_RUBRICS = True
except ImportError:
    HAS_RUBRICS = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRID_WIDTH = 15
GRID_HEIGHT = 15
SUSPICION_THRESHOLD = 80
CROSS_REF_INTERVAL = 5

# Safe house starting position (Docks district, near gang NPCs and civilians)
START_X = 8
START_Y = 5

# Warehouse coordinates (intel location)
WAREHOUSE_X = 6
WAREHOUSE_Y = 9

# Handler Chen NPC id
HANDLER_ID = "handler"

# Direction offsets: (dx, dy)
DIRECTION_OFFSETS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}


class CityEnvironment(Environment):
    """Core Undercover Agent City game engine.

    Implements OpenEnv Environment interface with reset(), step(), state property.
    All game mechanics: movement, talk with persona/claim tracking, NPC behavior,
    contradiction detection, cover blown mechanic, and task grading.
    """

    def __init__(self):
        super().__init__()
        if HAS_RUBRICS:
            self.rubric = UndercoverRubric()
        self._state: Optional[CityState] = None
        self._available_actions: list[dict] = []
        self._grid: list[int] = []
        self.rng: stdlib_random.Random = stdlib_random.Random(42)

    # ------------------------------------------------------------------
    # OpenEnv interface: reset
    # ------------------------------------------------------------------

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> CityObservation:
        """Reset the environment for a new episode.

        Args:
            seed: Random seed for deterministic episodes.
            episode_id: Optional episode identifier.
            **kwargs: Must include task name. Supported tasks:
                'tutorial_persona', 'tutorial_consistency',
                'first_contact', 'earn_trust', 'full_job'.
        """
        task = kwargs.get("task", "first_contact")
        self.rng = stdlib_random.Random(seed if seed is not None else 42)

        # Build grid and NPC roster
        self._grid = build_grid()
        npcs = fresh_npcs()

        # Task config
        task_cfg = TASK_CONFIGS.get(task, TASK_CONFIGS["first_contact"])
        max_turns = task_cfg["max_turns"]
        self._is_tutorial = task_cfg.get("tutorial", False)

        # Determine starting position
        spawn_npc_id = task_cfg.get("spawn_next_to")
        if spawn_npc_id:
            # Tutorial mode: place agent adjacent to the target NPC
            target_npc = next(
                (n for n in npcs if n["id"] == spawn_npc_id), None
            )
            if target_npc:
                # Place agent 1 cell west of target NPC (on a road)
                start_x = target_npc["x"] - 1
                start_y = target_npc["y"]
                # Ensure it's a valid position
                if (
                    0 <= start_x < GRID_WIDTH
                    and 0 <= start_y < GRID_HEIGHT
                ):
                    pass  # Good position
                else:
                    start_x, start_y = START_X, START_Y
            else:
                start_x, start_y = START_X, START_Y
        else:
            start_x, start_y = START_X, START_Y

        # Build initial state
        self._state = CityState.model_construct(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            grid=self._grid,
            width=GRID_WIDTH,
            height=GRID_HEIGHT,
            agent_x=start_x,
            agent_y=start_y,
            cover_intact=True,
            npcs=npcs,
            fact_db={},
            contradictions=[],
            current_task=task,
            intel_gathered=False,
            reported_to_handler=False,
            witnesses_during_report=False,
            turn=0,
            max_turns=max_turns,
            total_reward=0.0,
            recent_actions=[],
            correct_personas=0,
            total_talks=0,
        )

        # Initialize navigation shaping tracker
        self._prev_mission_dist = self._compute_nearest_mission_dist()

        # Track trust milestones already awarded
        self._trust_milestones_awarded = set()
        # Track NPCs talked to for ExplorationRubric
        self._npcs_talked_to = set()
        self._last_talked_npc_id = ""

        # Reset rubric state
        self._reset_rubric()

        # Generate initial actions and build observation
        self._available_actions = self._generate_available_actions()
        obs = self._make_observation()
        return obs

    # ------------------------------------------------------------------
    # OpenEnv interface: step
    # ------------------------------------------------------------------

    def step(
        self,
        action: CityAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> CityObservation:
        """Execute one game turn.

        Args:
            action: CityAction with action int (1-indexed).
            timeout_s: Unused.
        """
        st = self._state
        action_idx = action.action - 1  # Convert 1-indexed to 0-indexed

        # Metadata defaults
        action_type = "invalid"
        persona_correct = False
        trust_delta = 0
        target_trust = 0
        new_contradictions = 0
        just_gathered_intel = False
        just_reported = False
        response_text = ""

        # Validate action index (T-01-02 mitigation)
        if action_idx < 0 or action_idx >= len(self._available_actions):
            # Invalid action: penalty, turn advances, error message
            response_text = (
                f"Invalid action {action.action}. "
                f"Choose 1-{len(self._available_actions)}."
            )
            action_type = "invalid"
            st.turn += 1
            st.step_count += 1
            st.total_reward -= 0.05
            self._track_recent_action("invalid")
            self._available_actions = self._generate_available_actions()
            obs = self._make_observation(extra_message=response_text)
            obs.metadata = self._build_metadata(
                action_type, persona_correct, new_contradictions,
                trust_delta, target_trust, just_gathered_intel,
                just_reported,
            )
            obs.reward = self._apply_rubric(action, obs)
            st.total_reward += obs.reward
            obs.done = self._check_done()
            return obs

        # Resolve action
        resolved = self._available_actions[action_idx]
        action_type = resolved["type"]

        # ----------------------------------------------------------
        # Execute by action type
        # ----------------------------------------------------------

        if action_type == "move":
            response_text = self._execute_move(resolved)

        elif action_type == "navigate":
            response_text = self._execute_navigate(resolved)

        elif action_type == "talk":
            (
                persona_correct,
                trust_delta,
                target_trust,
                new_contradictions,
                response_text,
            ) = self._execute_talk(resolved)
            # Track which NPC was talked to for ExplorationRubric
            self._last_talked_npc_id = resolved.get("target_npc", "")

        elif action_type == "investigate":
            just_gathered_intel = self._execute_investigate()
            response_text = (
                "You slip into the warehouse and find the intel."
                if just_gathered_intel
                else "The warehouse yields nothing new."
            )

        elif action_type == "report":
            just_reported = self._execute_report()
            response_text = (
                "You pass the intel to Handler Chen discreetly."
                if just_reported
                else "Handler Chen nods. Nothing to report."
            )

        elif action_type == "hide":
            response_text = self._execute_hide()

        elif action_type == "wait":
            response_text = "You wait and observe."

        # Track recent actions
        self._track_recent_action(action_type)

        # Advance turn
        st.turn += 1
        st.step_count += 1

        # Advance NPC positions (D-20)
        self._advance_npcs()

        # Circumstantial suspicion: suspicious locations (Mechanic 4)
        warehouse_x, warehouse_y = WAREHOUSE_X, WAREHOUSE_Y
        dist_to_warehouse = abs(st.agent_x - warehouse_x) + abs(st.agent_y - warehouse_y)
        if dist_to_warehouse <= 2 and not st.intel_gathered:
            for npc in self._get_nearby_npcs(radius=3):
                if npc["faction"] == "gang":
                    n = self._get_npc_mutable(npc["id"])
                    n["suspicion"] = min(100, n["suspicion"] + 3)

        police_station_x, police_station_y = 1, 13
        dist_to_police = abs(st.agent_x - police_station_x) + abs(st.agent_y - police_station_y)
        if dist_to_police <= 2:
            for npc in self._get_nearby_npcs(radius=3):
                if npc["faction"] == "gang":
                    n = self._get_npc_mutable(npc["id"])
                    n["suspicion"] = min(100, n["suspicion"] + 5)

        # Cross-reference check every 10 turns (D-14)
        if st.turn % CROSS_REF_INTERVAL == 0 and st.turn > 0:
            self._do_cross_reference()

        # Check cover blown (D-05)
        self._check_cover_blown()

        # Generate new available actions
        self._available_actions = self._generate_available_actions()

        # Build observation with metadata
        obs = self._make_observation(extra_message=response_text)
        obs.metadata = self._build_metadata(
            action_type, persona_correct, new_contradictions,
            trust_delta, target_trust, just_gathered_intel,
            just_reported,
        )

        # Apply rubric (D-17) -- metadata must be set BEFORE this call
        obs.reward = self._apply_rubric(action, obs)
        st.total_reward += obs.reward

        # Update previous mission distance for next step's shaping reward
        self._prev_mission_dist = self._compute_nearest_mission_dist()

        # Check done conditions (D-06: cover blown = episode ends)
        obs.done = self._check_done()

        return obs

    # ------------------------------------------------------------------
    # OpenEnv interface: state property
    # ------------------------------------------------------------------

    @property
    def state(self) -> CityState:
        """Return current environment state."""
        return self._state

    # ------------------------------------------------------------------
    # Action execution helpers
    # ------------------------------------------------------------------

    def _execute_move(self, action_dict: dict) -> str:
        """Move agent in the specified direction."""
        st = self._state
        direction = action_dict["direction"]
        dx, dy = DIRECTION_OFFSETS[direction]
        new_x = st.agent_x + dx
        new_y = st.agent_y + dy

        # Bounds and passability check
        if (
            0 <= new_x < GRID_WIDTH
            and 0 <= new_y < GRID_HEIGHT
            and self._grid[new_y * GRID_WIDTH + new_x]
            != TERRAIN_INDEX[Terrain.BUILDING]
        ):
            st.agent_x = new_x
            st.agent_y = new_y
            terrain = get_terrain_name(self._grid[new_y * GRID_WIDTH + new_x])
            district = get_district(new_y).value
            return f"You move {direction} to {terrain} in {district}."
        else:
            return f"You can't move {direction} -- blocked."

    def _execute_navigate(self, action_dict: dict) -> str:
        """Navigate one cell closer to the target NPC."""
        target_x = action_dict["target_x"]
        target_y = action_dict["target_y"]
        target_name = action_dict["target_name"]
        self._move_toward(target_x, target_y)
        st = self._state
        terrain = get_terrain_name(self._grid[st.agent_y * GRID_WIDTH + st.agent_x])
        district = get_district(st.agent_y).value
        return f"You navigate toward {target_name} ({terrain} in {district})."

    def _move_toward(self, target_x: int, target_y: int) -> None:
        """Move one cell toward target, preferring roads."""
        st = self._state
        best_pos = (st.agent_x, st.agent_y)
        best_dist = abs(target_x - st.agent_x) + abs(target_y - st.agent_y)

        for direction, (dx, dy) in DIRECTION_OFFSETS.items():
            nx, ny = st.agent_x + dx, st.agent_y + dy
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                if self._grid[ny * GRID_WIDTH + nx] != TERRAIN_INDEX[Terrain.BUILDING]:
                    dist = abs(target_x - nx) + abs(target_y - ny)
                    if dist < best_dist:
                        best_dist = dist
                        best_pos = (nx, ny)

        st.agent_x, st.agent_y = best_pos

    def _execute_talk(self, action_dict: dict) -> tuple:
        """Execute a talk action with persona and claim.

        Returns:
            (persona_correct, trust_delta, target_trust, new_contradictions, response_text)
        """
        st = self._state
        npc_id = action_dict["target_npc"]
        persona = action_dict["persona"]
        topic = action_dict["claim_topic"]
        claim_value = action_dict["claim_value"]

        npc = self._get_npc_mutable(npc_id)
        trust_delta = 0
        new_contradictions = 0

        # Check persona correctness (D-10)
        persona_correct = persona == npc["expected_persona"]

        # Update trust/suspicion (D-02)
        if persona_correct:
            npc["trust"] = min(100, npc["trust"] + 10)
            trust_delta += 10
        else:
            npc["suspicion"] = min(100, npc["suspicion"] + 8)

        # Record claim in fact_db
        if topic not in st.fact_db:
            st.fact_db[topic] = {}

        # Check consistency with same-faction NPCs BEFORE recording (D-13)
        faction = npc["faction"]
        existing_claims = st.fact_db.get(topic, {})
        is_consistent = True
        for other_id, other_value in existing_claims.items():
            other_npc = self._get_npc(other_id)
            if other_npc and other_npc["faction"] == faction and other_value != claim_value:
                is_consistent = False
                new_contradictions += 1

        if is_consistent and len(existing_claims) > 0:
            # Check if any same-faction NPC already heard the same value
            for other_id, other_value in existing_claims.items():
                other_npc = self._get_npc(other_id)
                if (
                    other_npc
                    and other_npc["faction"] == faction
                    and other_value == claim_value
                    and other_id != npc_id
                ):
                    # Consistent claim with same-faction NPC: +5 trust
                    npc["trust"] = min(100, npc["trust"] + 5)
                    trust_delta += 5
                    break

        # Store the claim
        st.fact_db[topic][npc_id] = claim_value
        npc["facts_heard"][topic] = claim_value

        # Track personas and talks for graders
        st.total_talks += 1
        if persona_correct:
            st.correct_personas += 1

        target_trust = npc["trust"]

        # Witness check (NPC-06): nearby NPCs see wrong-persona talk
        if not persona_correct:
            for witness in self._get_nearby_npcs(radius=2):
                if witness["id"] != npc_id:
                    w = self._get_npc_mutable(witness["id"])
                    w["suspicion"] = min(100, w["suspicion"] + 10)

        # Generate NPC response text
        trust_bucket = get_trust_bucket(npc["trust"])
        templates = NPC_RESPONSES.get(
            (trust_bucket, persona_correct),
            NPC_RESPONSES.get(("low", persona_correct), ["{name} says nothing."]),
        )
        response_text = self.rng.choice(templates).format(name=npc["name"])

        # Add feedback line
        persona_mark = "correct" if persona_correct else "WRONG"
        consist_mark = "consistent" if is_consistent else "CONTRADICTION"
        response_text += (
            f"\n  -> Trust {'+' if trust_delta >= 0 else ''}{trust_delta} "
            f"(now {npc['trust']}%), "
            f"Persona {persona_mark}, Claim {consist_mark}"
        )

        # NPC probe: same-faction NPCs compare notes (Mechanic 2)
        if npc["trust"] > 20 and self.rng.random() < 0.3:
            faction_claims = {}
            for t, claims in st.fact_db.items():
                for nid, val in claims.items():
                    other = self._get_npc(nid)
                    if other and other["faction"] == npc["faction"] and nid != npc_id:
                        faction_claims[t] = (nid, val)
            if faction_claims:
                probe_topic = self.rng.choice(list(faction_claims.keys()))
                ref_npc_id, ref_value = faction_claims[probe_topic]
                ref_npc = self._get_npc(ref_npc_id)
                my_claim = st.fact_db.get(probe_topic, {}).get(npc_id)
                if my_claim and my_claim != ref_value:
                    npc["suspicion"] = min(100, npc["suspicion"] + 20)
                    response_text += f"\n  !! {npc['name']} narrows eyes: \"{ref_npc['name']} told me something different about your {probe_topic}...\""
                elif my_claim and my_claim == ref_value:
                    npc["trust"] = min(100, npc["trust"] + 3)
                    trust_delta += 3
                    response_text += f"\n  {npc['name']} nods: \"{ref_npc['name']} mentioned the same thing.\""

        return persona_correct, trust_delta, target_trust, new_contradictions, response_text

    def _execute_investigate(self) -> bool:
        """Attempt to gather intel at the warehouse."""
        st = self._state
        if st.intel_gathered:
            return False
        # Check agent at warehouse and trust condition
        if st.agent_x == WAREHOUSE_X and st.agent_y == WAREHOUSE_Y:
            # Need any gang NPC with trust >= their threshold
            for npc in st.npcs:
                if npc["faction"] == "gang" and npc["trust"] >= npc.get("trust_threshold", 999):
                    st.intel_gathered = True
                    return True
        return False

    def _execute_report(self) -> bool:
        """Report intel to handler."""
        st = self._state
        if st.reported_to_handler or not st.intel_gathered:
            return False

        handler = self._get_npc(HANDLER_ID)
        if not handler:
            return False

        # Check adjacent to handler (Manhattan distance <= 1)
        dist = abs(st.agent_x - handler["x"]) + abs(st.agent_y - handler["y"])
        if dist > 1:
            return False

        st.reported_to_handler = True

        # Check for witnesses within 2 cells (NPC-06)
        witnesses = [
            n for n in self._get_nearby_npcs(radius=2)
            if n["id"] != HANDLER_ID
        ]
        if witnesses:
            st.witnesses_during_report = True

        return True

    def _execute_hide(self) -> str:
        """Hide in alley/hideout -- reduce nearby NPC suspicion by 5."""
        st = self._state
        terrain_idx = self._grid[st.agent_y * GRID_WIDTH + st.agent_x]
        terrain = get_terrain_name(terrain_idx)

        if terrain in ("alley", "hideout", "safe_house"):
            for npc in self._get_nearby_npcs(radius=3):
                n = self._get_npc_mutable(npc["id"])
                n["suspicion"] = max(0, n["suspicion"] - 5)
            return f"You lay low in the {terrain}. Nearby suspicion eases slightly."
        else:
            return "Not a great place to hide, but you keep a low profile."

    # ------------------------------------------------------------------
    # NPC movement (D-20)
    # ------------------------------------------------------------------

    def _advance_npcs(self) -> None:
        """Advance NPC positions each turn."""
        st = self._state
        for npc in st.npcs:
            faction = npc["faction"]

            if faction == "police" and npc.get("patrol_route"):
                # Police patrol: advance along route
                route = npc["patrol_route"]
                if not route:
                    continue
                # Find current position in route
                patrol_step = npc.get("patrol_step", 0)
                patrol_step = (patrol_step + 1) % len(route)
                npc["patrol_step"] = patrol_step
                npc["x"], npc["y"] = route[patrol_step]

            elif faction == "gang":
                # Gang: stationary
                pass

            elif faction == "civilian":
                # Civilians: 50% chance to move to random adjacent road cell
                if self.rng.random() < 0.5:
                    directions = list(DIRECTION_OFFSETS.values())
                    self.rng.shuffle(directions)
                    for dx, dy in directions:
                        nx, ny = npc["x"] + dx, npc["y"] + dy
                        if (
                            0 <= nx < GRID_WIDTH
                            and 0 <= ny < GRID_HEIGHT
                            and self._grid[ny * GRID_WIDTH + nx]
                            != TERRAIN_INDEX[Terrain.BUILDING]
                        ):
                            npc["x"] = nx
                            npc["y"] = ny
                            break

        # Cross-faction gossip: suspicious civilians report to nearby police (Mechanic 3)
        patrol_npc = self._get_npc_mutable("patrol")
        if patrol_npc:
            for npc in st.npcs:
                if npc["faction"] == "civilian" and npc["suspicion"] >= 30:
                    dist = abs(npc["x"] - patrol_npc["x"]) + abs(npc["y"] - patrol_npc["y"])
                    if dist <= 4:
                        patrol_npc["suspicion"] = min(100, patrol_npc["suspicion"] + 8)
                        npc["suspicion"] = max(0, npc["suspicion"] - 10)  # civilian feels "reported"

    # ------------------------------------------------------------------
    # Cross-reference (D-14)
    # ------------------------------------------------------------------

    def _do_cross_reference(self) -> None:
        """Same-faction NPCs compare notes. Contradictions => +30 suspicion."""
        st = self._state
        for topic, claims in st.fact_db.items():
            npc_ids = list(claims.keys())
            for i in range(len(npc_ids)):
                for j in range(i + 1, len(npc_ids)):
                    id_a, id_b = npc_ids[i], npc_ids[j]
                    if claims[id_a] != claims[id_b]:
                        npc_a = self._get_npc(id_a)
                        npc_b = self._get_npc(id_b)
                        if npc_a and npc_b and npc_a["faction"] == npc_b["faction"]:
                            # Check if already recorded
                            contradiction = (topic, id_a, id_b)
                            if contradiction not in st.contradictions:
                                st.contradictions.append(contradiction)
                                ma = self._get_npc_mutable(id_a)
                                mb = self._get_npc_mutable(id_b)
                                ma["suspicion"] = min(100, ma["suspicion"] + 30)
                                mb["suspicion"] = min(100, mb["suspicion"] + 30)

    # ------------------------------------------------------------------
    # Cover blown check (D-05)
    # ------------------------------------------------------------------

    def _check_cover_blown(self) -> None:
        """Probabilistic cover detection (Mechanic 5).

        Higher suspicion = higher chance per turn.
        At 80+: guaranteed blown. At 60-79: increasing probability each turn.
        """
        st = self._state
        for npc in st.npcs:
            if npc["suspicion"] >= SUSPICION_THRESHOLD:
                st.cover_intact = False
                return
            elif npc["suspicion"] >= 70:
                # Probabilistic: (suspicion - 60) / 100 chance per turn
                blow_chance = (npc["suspicion"] - 60) / 100.0
                if self.rng.random() < blow_chance:
                    st.cover_intact = False
                    return

    def _check_done(self) -> bool:
        """Check if episode is over."""
        st = self._state
        if not st.cover_intact:
            return True
        if st.turn >= st.max_turns:
            return True
        return False

    # ------------------------------------------------------------------
    # Action generation (ACT-02, ACT-03)
    # ------------------------------------------------------------------

    def _generate_available_actions(self) -> list[dict]:
        """Build context-dependent action list, capped at 8.

        In tutorial mode, restricts to persona-choice-only actions so
        the model learns the core skill before anything else.
        """
        st = self._state

        # --- TUTORIAL MODE: persona-only choices ---
        if self._is_tutorial:
            return self._generate_tutorial_actions()

        actions: list[dict] = []

        # 1. Navigate-to-NPC options (replace low-level movement)
        # List NPCs within vision range (~7 cells) but NOT adjacent (adjacent => use talk)
        navigate_actions = []
        adjacent_ids = {n["id"] for n in self._get_adjacent_npcs()}
        vision_npcs = self._get_nearby_npcs(radius=7)
        for npc in vision_npcs:
            if npc["id"] in adjacent_ids:
                continue  # Adjacent NPCs get talk actions, not navigate
            dist = abs(npc["x"] - st.agent_x) + abs(npc["y"] - st.agent_y)
            direction = self._get_direction_to(
                st.agent_x, st.agent_y, npc["x"], npc["y"]
            )
            desc = (
                f"Go to {npc['name']} "
                f"({npc['faction']}, {dist} cells {direction})"
            )
            navigate_actions.append({
                "type": "navigate",
                "target_npc": npc["id"],
                "target_name": npc["name"],
                "target_x": npc["x"],
                "target_y": npc["y"],
                "description": desc,
            })

        # 2. Talk options for adjacent NPCs
        talk_actions = []
        correct_talk_actions = []
        adjacent_npcs = self._get_adjacent_npcs()

        # Semi-opaque approach labels: descriptive enough for an LLM to reason
        # about social dynamics, but not a direct "use X for faction Y" mapping.
        # The agent must learn that "street-smart" works for SOME gang members
        # but not all (Whisper prefers "measured"), creating a real learning challenge.
        _APPROACH_LABELS = {
            "tough": "street-smart and blunt",
            "formal": "measured and respectful",
            "casual": "easygoing and chatty",
        }

        for npc in adjacent_npcs:
            # Determine next topic for this NPC
            topic = self._get_next_topic(npc["id"])

            for persona in ["tough", "formal", "casual"]:
                for claim_value in CLAIM_OPTIONS[topic]:
                    approach = _APPROACH_LABELS[persona]
                    desc = (
                        f"Talk to {npc['name']} about {topic} "
                        f"({claim_value}) — {approach}"
                    )
                    talk_act = {
                        "type": "talk",
                        "target_npc": npc["id"],
                        "persona": persona,
                        "claim_topic": topic,
                        "claim_value": claim_value,
                        "description": desc,
                    }
                    # Prioritize correct persona
                    if persona == npc["expected_persona"]:
                        correct_talk_actions.append(talk_act)
                    else:
                        talk_actions.append(talk_act)

        # 3. Special actions
        special_actions = []
        if self._can_investigate():
            special_actions.append({
                "type": "investigate",
                "description": "Investigate the warehouse for intel",
            })
        if self._can_report():
            special_actions.append({
                "type": "report",
                "description": "Report intel to Handler Chen",
            })

        # 4. Hide (if in alley/hideout/safe_house)
        terrain_idx = self._grid[st.agent_y * GRID_WIDTH + st.agent_x]
        terrain_name = get_terrain_name(terrain_idx)
        if terrain_name in ("alley", "hideout", "safe_house"):
            special_actions.append({
                "type": "hide",
                "description": f"Hide in the {terrain_name}",
            })

        # 5. Wait (always available)
        wait_action = {"type": "wait", "description": "Wait and observe"}

        # Assemble actions: mix correct and wrong persona talks equally
        # so random baseline has ~33% persona accuracy, not 85%.
        self.rng.shuffle(navigate_actions)
        self.rng.shuffle(special_actions)

        # Mix talk actions: interleave correct and wrong to ensure balanced representation
        all_talks = correct_talk_actions + talk_actions
        self.rng.shuffle(all_talks)

        # Build priority list
        if navigate_actions:
            actions.append(navigate_actions[0])
            remaining_navigates = navigate_actions[1:]
        else:
            remaining_navigates = []

        # Add special actions
        actions.extend(special_actions)
        # Add mixed talk actions (correct and wrong interleaved)
        actions.extend(all_talks)
        # Add remaining navigate options
        actions.extend(remaining_navigates)
        # Add wait last
        actions.append(wait_action)

        # Cap at 8 (D-07)
        actions = actions[:8]

        # Final shuffle to prevent position bias (Pitfall 4)
        self.rng.shuffle(actions)

        # Assign 1-indexed numbers and descriptions
        for i, act in enumerate(actions, 1):
            act["index"] = i

        return actions

    def _generate_tutorial_actions(self) -> list[dict]:
        """Generate simplified actions for tutorial tasks.

        tutorial_persona: Only 3 choices — pick the right persona for the
        adjacent NPC. One turn, pure classification task.

        tutorial_consistency: Same persona choices but across multiple turns
        with multiple NPCs — must keep claims consistent.
        """
        st = self._state
        adjacent = self._get_adjacent_npcs()

        if not adjacent:
            # Shouldn't happen if spawn_next_to works, but fallback
            return [{"index": 1, "type": "wait", "description": "Wait and observe"}]

        npc = adjacent[0]
        topic = self._get_next_topic(npc["id"])
        # Pick one claim value (consistent if already told this faction)
        claim = self._get_consistent_claim(topic, npc)

        _APPROACH_LABELS = {
            "tough": "street-smart and blunt",
            "formal": "measured and respectful",
            "casual": "easygoing and chatty",
        }
        actions = []
        for persona in ["tough", "formal", "casual"]:
            approach = _APPROACH_LABELS[persona]
            desc = f"Talk to {npc['name']} about {topic} ({claim}) — {approach}"
            actions.append({
                "type": "talk",
                "target_npc": npc["id"],
                "persona": persona,
                "claim_topic": topic,
                "claim_value": claim,
                "description": desc,
            })

        # Shuffle to prevent position bias
        self.rng.shuffle(actions)

        # Assign indices
        for i, act in enumerate(actions, 1):
            act["index"] = i

        return actions

    def _get_consistent_claim(self, topic: str, npc: dict) -> str:
        """Get a claim value that's consistent with what we already told
        same-faction NPCs, or pick a random one if first time."""
        st = self._state
        npc_faction = npc.get("faction", "")

        # Check if we already told a same-faction NPC about this topic
        if topic in st.fact_db:
            for told_npc_id, told_value in st.fact_db[topic].items():
                told_npc = self._get_npc(told_npc_id)
                if told_npc and told_npc.get("faction") == npc_faction:
                    return told_value  # Use the same claim for consistency

        # First time — pick random
        return self.rng.choice(CLAIM_OPTIONS[topic])

    def _get_next_topic(self, npc_id: str) -> str:
        """Get the next undiscussed topic for an NPC, or random if all discussed."""
        st = self._state
        npc = self._get_npc(npc_id)
        if not npc:
            return COVER_TOPICS[0]

        discussed = set(npc.get("facts_heard", {}).keys())
        for topic in COVER_TOPICS:
            if topic not in discussed:
                return topic

        # All discussed -- pick random
        return self.rng.choice(COVER_TOPICS)

    # ------------------------------------------------------------------
    # Condition checks
    # ------------------------------------------------------------------

    def _can_investigate(self) -> bool:
        """Check if agent can investigate the warehouse."""
        st = self._state
        if st.intel_gathered:
            return False
        if st.agent_x != WAREHOUSE_X or st.agent_y != WAREHOUSE_Y:
            return False
        for npc in st.npcs:
            if npc["faction"] == "gang" and npc["trust"] >= npc.get("trust_threshold", 999):
                return True
        return False

    def _can_report(self) -> bool:
        """Check if agent can report to handler."""
        st = self._state
        if st.reported_to_handler or not st.intel_gathered:
            return False
        handler = self._get_npc(HANDLER_ID)
        if not handler:
            return False
        dist = abs(st.agent_x - handler["x"]) + abs(st.agent_y - handler["y"])
        return dist <= 1

    # ------------------------------------------------------------------
    # Observation rendering (OBS-02, OBS-03)
    # ------------------------------------------------------------------

    def _make_observation(self, extra_message: str = "") -> CityObservation:
        """Build the full observation including natural language message."""
        st = self._state

        # Nearby NPCs for observation
        nearby = self._get_nearby_npcs(radius=5)
        nearby_dicts = []
        for npc in nearby:
            dist = abs(npc["x"] - st.agent_x) + abs(npc["y"] - st.agent_y)
            nearby_dicts.append({
                "id": npc["id"],
                "name": npc["name"],
                "faction": npc["faction"],
                "trust": npc["trust"],
                "suspicion": npc["suspicion"],
                "distance": dist,
                "has_intel": npc.get("has_intel", False),
                "x": npc["x"],
                "y": npc["y"],
            })

        # Terrain info
        terrain_idx = self._grid[st.agent_y * GRID_WIDTH + st.agent_x]
        terrain = get_terrain_name(terrain_idx)
        district = get_district(st.agent_y).value

        # Build natural language message
        message = self._render_message(
            terrain, district, nearby_dicts, extra_message
        )

        obs = CityObservation.model_construct(
            done=False,
            reward=0.0,
            metadata={},
            x=st.agent_x,
            y=st.agent_y,
            current_terrain=terrain,
            current_district=district,
            nearby_npcs=nearby_dicts,
            cover_intact=st.cover_intact,
            claims_made=copy.deepcopy(st.fact_db),
            current_task=st.current_task,
            intel_gathered=st.intel_gathered,
            reported_to_handler=st.reported_to_handler,
            turn=st.turn,
            max_turns=st.max_turns,
            available_actions=[
                {"index": a["index"], "description": a["description"]}
                for a in self._available_actions
            ],
            message=message,
        )
        return obs

    def _render_message(
        self,
        terrain: str,
        district: str,
        nearby_npcs: list[dict],
        extra_message: str,
    ) -> str:
        """Render the natural language observation message for the LLM."""
        st = self._state
        lines: list[str] = []

        # Last action result
        if extra_message:
            lines.append(extra_message)
            lines.append("")

        # Location
        lines.append(
            f"LOCATION: {district.title()} district, "
            f"{terrain} ({st.agent_x},{st.agent_y})"
        )

        # Nearby NPCs — show faction + raw trust/suspicion for clear RL signal
        if nearby_npcs:
            npc_lines = []
            for npc in nearby_npcs:
                dist = npc["distance"]
                direction = self._get_direction_to(
                    st.agent_x, st.agent_y,
                    npc["x"], npc["y"],
                )
                adj = "adjacent" if dist <= 1 else f"{dist} cells {direction}"
                npc_lines.append(
                    f"  {npc['name']} ({npc['faction']}) "
                    f"-- {adj} -- trust:{npc['trust']} suspicion:{npc['suspicion']}"
                )
            lines.append("NEARBY:\n" + "\n".join(npc_lines))
        else:
            lines.append("NEARBY: No one visible.")

        # Heat indicators (Mechanic 5 companion)
        max_sus = max((n["suspicion"] for n in st.npcs), default=0)
        if max_sus >= 60:
            lines.append("WARNING: Someone is very suspicious of you. Watch your step.")
        elif max_sus >= 40:
            lines.append("CAUTION: You're attracting attention.")

        # Cover story summary — show what you claimed but NOT who you told.
        # The agent must track per-NPC consistency from memory/context.
        if st.fact_db:
            claims = []
            for topic, npc_claims in st.fact_db.items():
                vals = list(set(npc_claims.values()))
                val_str = "/".join(vals)
                n_told = len(npc_claims)
                claims.append(f"{topic}={val_str} (told to {n_told} people)")
            lines.append("COVER STORY: " + "; ".join(claims))
        else:
            lines.append("COVER STORY: None yet -- you haven't told anyone anything.")

        # Mission status
        task_desc = TASK_CONFIGS.get(st.current_task, {}).get(
            "description", st.current_task
        )
        mission_parts = [f"MISSION: {task_desc}"]
        if st.intel_gathered:
            mission_parts.append("Intel: GATHERED")
        if st.reported_to_handler:
            mission_parts.append("Report: DELIVERED")
        if not st.cover_intact:
            mission_parts.append("COVER BLOWN!")
        lines.append(" | ".join(mission_parts))

        lines.append(f"Turn: {st.turn}/{st.max_turns}")
        lines.append("")

        # Available actions
        lines.append("Available actions:")
        for act in self._available_actions:
            lines.append(f"  - {act['description']}")
        lines.append("")
        lines.append("Reply with the EXACT text of your chosen action:")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Metadata for rubrics (Pattern 6)
    # ------------------------------------------------------------------

    def _build_metadata(
        self,
        action_type: str,
        persona_correct: bool,
        new_contradictions: int,
        trust_delta: int,
        target_trust: int,
        just_gathered_intel: bool,
        just_reported: bool,
    ) -> dict:
        """Build metadata dict for rubric consumption."""
        st = self._state

        # Compute nearest mission-relevant NPC distance for navigation shaping
        mission_factions = {"gang"} if st.current_task in (
            "first_contact", "earn_trust", "full_job"
        ) else set()
        nearest_mission_dist = 999
        for npc in st.npcs:
            if npc["faction"] in mission_factions:
                d = abs(npc["x"] - st.agent_x) + abs(npc["y"] - st.agent_y)
                nearest_mission_dist = min(nearest_mission_dist, d)

        # Max gang trust for milestone rewards
        max_gang_trust = max(
            (n["trust"] for n in st.npcs if n["faction"] == "gang"), default=0
        )

        # Compute distance delta for NavigationRubric
        prev_dist = getattr(self, "_prev_mission_dist", nearest_mission_dist)
        gang_distance_delta = nearest_mission_dist - prev_dist  # negative = got closer
        self._prev_mission_dist = nearest_mission_dist

        # Trust milestones — fire once per NPC
        trust_milestone_30 = False
        trust_milestone_60 = False
        if action_type == "talk" and trust_delta > 0:
            prev_trust = target_trust - trust_delta
            if prev_trust < 30 <= target_trust:
                trust_milestone_30 = True
            if prev_trust < 60 <= target_trust:
                trust_milestone_60 = True

        # First interaction tracking for ExplorationRubric
        first_interaction = False
        if action_type == "talk":
            talked_npc_id = getattr(self, "_last_talked_npc_id", None)
            if talked_npc_id:
                talked_before = getattr(self, "_npcs_talked_to", set())
                if talked_npc_id not in talked_before:
                    first_interaction = True
                    talked_before.add(talked_npc_id)
                    self._npcs_talked_to = talked_before

        return {
            "was_talk_action": action_type == "talk",
            "persona_correct": persona_correct,
            "new_contradictions": new_contradictions,
            "trust_delta": trust_delta,
            "target_npc_trust": target_trust,
            "just_gathered_intel": just_gathered_intel,
            "just_reported_to_handler": just_reported,
            "cover_blown": not st.cover_intact,
            "action_type": action_type,
            "turn": st.turn,
            "repeated_action_count": self._count_repeated_actions(),
            "nearest_mission_npc_dist": nearest_mission_dist,
            "gang_distance_delta": gang_distance_delta,
            "trust_milestone_30": trust_milestone_30,
            "trust_milestone_60": trust_milestone_60,
            "first_interaction_with_npc": first_interaction,
            "current_task": st.current_task,
            "max_gang_trust": max_gang_trust,
            "intel_gathered": st.intel_gathered,
            "reported_to_handler": st.reported_to_handler,
            "agent_x": st.agent_x,
            "agent_y": st.agent_y,
            "max_suspicion": max(
                (n["suspicion"] for n in st.npcs), default=0
            ),
        }

    # ------------------------------------------------------------------
    # NPC lookup helpers
    # ------------------------------------------------------------------

    def _get_npc(self, npc_id: str) -> Optional[dict]:
        """Get NPC dict by id (read-only intent)."""
        for npc in self._state.npcs:
            if npc["id"] == npc_id:
                return npc
        return None

    def _get_npc_mutable(self, npc_id: str) -> dict:
        """Get NPC dict by id for mutation."""
        for npc in self._state.npcs:
            if npc["id"] == npc_id:
                return npc
        raise ValueError(f"NPC {npc_id} not found")

    def _get_nearby_npcs(self, radius: int = 5) -> list[dict]:
        """Get NPCs within Manhattan distance, sorted by distance."""
        st = self._state
        nearby = []
        for npc in st.npcs:
            dist = abs(npc["x"] - st.agent_x) + abs(npc["y"] - st.agent_y)
            if dist <= radius:
                nearby.append(npc)
        nearby.sort(key=lambda n: abs(n["x"] - st.agent_x) + abs(n["y"] - st.agent_y))
        return nearby

    def _get_adjacent_npcs(self) -> list[dict]:
        """Get NPCs with Manhattan distance <= 1."""
        return self._get_nearby_npcs(radius=1)

    def _get_direction_to(self, from_x: int, from_y: int, to_x: int, to_y: int) -> str:
        """Compute compass direction from one position to another."""
        dx = to_x - from_x
        dy = to_y - from_y
        if abs(dx) <= 1 and abs(dy) <= 1:
            return "adjacent"
        parts = []
        if dy < 0:
            parts.append("north")
        elif dy > 0:
            parts.append("south")
        if dx > 0:
            parts.append("east")
        elif dx < 0:
            parts.append("west")
        return "".join(parts) if parts else "here"

    def _get_disposition_cue(self, npc: dict) -> str:
        """Convert trust/suspicion to behavioral cues (partial observability).

        Agent must infer NPC disposition from these cues instead of seeing
        exact numbers. This tests real social intelligence.
        """
        trust = npc.get("trust", 0)
        suspicion = npc.get("suspicion", 0)

        # Trust cues
        if trust >= 60:
            trust_cue = "trusts you deeply"
        elif trust >= 40:
            trust_cue = "warming up to you"
        elif trust >= 20:
            trust_cue = "cautiously interested"
        elif trust > 0:
            trust_cue = "slightly curious"
        else:
            trust_cue = "guarded"

        # Suspicion cues
        if suspicion >= 60:
            sus_cue = "watching your every move"
        elif suspicion >= 40:
            sus_cue = "something feels off to them"
        elif suspicion >= 20:
            sus_cue = "slightly wary"
        elif suspicion > 0:
            sus_cue = "mildly alert"
        else:
            sus_cue = ""

        if sus_cue:
            return f"{trust_cue}, {sus_cue}"
        return trust_cue

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _track_recent_action(self, action_type: str) -> None:
        """Track last 5 actions for repetition detection."""
        st = self._state
        st.recent_actions.append(action_type)
        if len(st.recent_actions) > 5:
            st.recent_actions = st.recent_actions[-5:]

    def _count_repeated_actions(self) -> int:
        """Count consecutive repeated actions from the end."""
        actions = self._state.recent_actions
        if not actions:
            return 0
        last = actions[-1]
        count = 0
        for a in reversed(actions):
            if a == last:
                count += 1
            else:
                break
        return count

    def _compute_nearest_mission_dist(self) -> int:
        """Compute Manhattan distance to nearest mission-relevant NPC."""
        st = self._state
        mission_factions = {"gang"} if st.current_task in (
            "first_contact", "earn_trust", "full_job"
        ) else set()
        best = 999
        for npc in st.npcs:
            if npc["faction"] in mission_factions:
                d = abs(npc["x"] - st.agent_x) + abs(npc["y"] - st.agent_y)
                best = min(best, d)
        return best

    # ------------------------------------------------------------------
    # Task graders (TSK-01, TSK-02, TSK-03, GRD-01, GRD-02)
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp_grade(v: float) -> float:
        """Clamp grade to open interval [0.01, 0.99] for GRPO stability."""
        return max(0.01, min(0.99, v))

    def grade_episode(self) -> float:
        """Grade current episode based on task type. Returns [0.01-0.99]."""
        if self._state is None:
            return 0.01
        task = self._state.current_task
        if task == "tutorial_persona":
            return self._grade_tutorial_persona()
        elif task == "tutorial_consistency":
            return self._grade_tutorial_consistency()
        elif task == "first_contact":
            return self._grade_first_contact()
        elif task == "earn_trust":
            return self._grade_earn_trust()
        elif task == "full_job":
            return self._grade_full_job()
        return 0.01

    def _grade_tutorial_persona(self) -> float:
        """Grade tutorial_persona: pure persona accuracy (1 turn)."""
        st = self._state
        if st.total_talks == 0:
            return 0.01
        return self._clamp_grade(st.correct_personas / st.total_talks)

    def _grade_tutorial_consistency(self) -> float:
        """Grade tutorial_consistency: persona accuracy + consistency.

        Requires at least 3 talks out of 5 turns for full credit.
        """
        st = self._state
        if st.total_talks == 0:
            return 0.01
        engagement = min(0.99, st.total_talks / 3.0)
        persona_acc = st.correct_personas / max(1, st.total_talks)
        contradictions = len(st.contradictions)
        consistency = max(0.01, 1.0 - 0.3 * contradictions) if contradictions > 0 else 0.99
        return self._clamp_grade((0.50 * persona_acc + 0.50 * consistency) * engagement)

    def _grade_first_contact(self) -> float:
        """Grade Task 1: additive credit for each achievement.

        Random ~0.10-0.20, GPT-4o-mini ~0.35-0.55, Trained ~0.60-0.85
        """
        st = self._state
        if st.total_talks == 0:
            return 0.01

        persona_acc = st.correct_personas / max(1, st.total_talks)
        gang_npcs = [n for n in st.npcs if n["faction"] == "gang"]
        avg_gang_trust = sum(n["trust"] for n in gang_npcs) / max(1, len(gang_npcs))
        trust_score = min(0.99, avg_gang_trust / 40.0)
        contradiction_rate = len(st.contradictions) / max(1, st.total_talks)
        consistency = max(0.01, 1.0 - 2.0 * contradiction_rate)
        engagement = min(0.99, st.total_talks / 5.0)
        cover = 0.99 if st.cover_intact else 0.01

        return self._clamp_grade(
            0.30 * persona_acc
            + 0.30 * trust_score
            + 0.20 * consistency
            + 0.10 * engagement
            + 0.10 * cover
        )

    def _grade_earn_trust(self) -> float:
        """Grade Task 2: additive skill credits + mission milestones.

        Random ~0.05-0.15, GPT-4o-mini ~0.30-0.50, Trained ~0.55-0.80
        """
        st = self._state
        if st.total_talks == 0:
            return 0.01

        persona_acc = st.correct_personas / max(1, st.total_talks)
        gang_npcs = [n for n in st.npcs if n["faction"] == "gang"]
        avg_gang_trust = sum(n["trust"] for n in gang_npcs) / max(1, len(gang_npcs))
        trust_score = min(0.99, avg_gang_trust / 40.0)
        contradiction_rate = len(st.contradictions) / max(1, st.total_talks)
        consistency = max(0.01, 1.0 - 2.0 * contradiction_rate)
        engagement = min(0.99, st.total_talks / 8.0)
        cover = 0.99 if st.cover_intact else 0.01

        skill = (
            0.15 * persona_acc
            + 0.15 * trust_score
            + 0.10 * consistency
            + 0.05 * engagement
            + 0.05 * cover
        )

        max_gang_trust_val = max(
            (n["trust"] for n in st.npcs if n["faction"] == "gang"), default=0
        )
        mission = 0.0
        if max_gang_trust_val >= 60:
            mission += 0.25
        if st.intel_gathered:
            mission += 0.25

        return self._clamp_grade(skill + mission)

    def _grade_full_job(self) -> float:
        """Grade Task 3: additive skill credits + hard mission gates.

        Random ~0.03-0.12, GPT-4o-mini ~0.25-0.45, Trained ~0.50-0.80
        """
        st = self._state
        if st.total_talks == 0:
            return 0.01

        persona_acc = st.correct_personas / max(1, st.total_talks)
        gang_npcs = [n for n in st.npcs if n["faction"] == "gang"]
        avg_gang_trust = sum(n["trust"] for n in gang_npcs) / max(1, len(gang_npcs))
        trust_score = min(0.99, avg_gang_trust / 40.0)
        contradiction_rate = len(st.contradictions) / max(1, st.total_talks)
        consistency = max(0.01, 1.0 - 2.0 * contradiction_rate)
        engagement = min(0.99, st.total_talks / 10.0)
        cover = 0.99 if st.cover_intact else 0.01

        skill = (
            0.10 * persona_acc
            + 0.10 * trust_score
            + 0.05 * consistency
            + 0.05 * engagement
            + 0.05 * cover
        )

        max_gang_trust_val = max(
            (n["trust"] for n in st.npcs if n["faction"] == "gang"), default=0
        )
        mission = 0.0
        if max_gang_trust_val >= 60:
            mission += 0.15
        if st.intel_gathered:
            mission += 0.15
        if st.reported_to_handler:
            mission += 0.20
        if st.reported_to_handler and not st.witnesses_during_report:
            mission += 0.15

        return self._clamp_grade(skill + mission)
