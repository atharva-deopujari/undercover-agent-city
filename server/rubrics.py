"""Composable rubrics for the Undercover Agent City reward system.

Implements 5 leaf rubrics, 1 penalty rubric, and 1 composite rubric
following OpenEnv RFC 004 patterns. The composite UndercoverRubric uses
manual composition with a gate + weighted sum + additive penalty pattern.

All rubrics read from observation.metadata dict (populated by CityEnvironment).
All metadata reads use .get() with safe defaults to prevent KeyError.
"""

from typing import Any

from openenv.core.rubrics.base import Rubric

__all__ = [
    "PersonaRubric",
    "ConsistencyRubric",
    "TrustBuildingRubric",
    "MissionProgressRubric",
    "CoverBlownRubric",
    "NavigationRubric",
    "SubgoalRubric",
    "SuspicionManagementRubric",
    "IdlePenaltyRubric",
    "UndercoverRubric",
]


class PersonaRubric(Rubric):
    """Reward for using correct persona for NPC's faction.

    +0.3 for correct persona, -0.5 for wrong persona, 0.0 for non-talk actions.
    Persona selection is the easiest skill to learn -- strong positive/negative signal.
    """

    def forward(self, action: Any, observation: Any) -> float:
        if not observation.metadata.get("was_talk_action"):
            return 0.0
        return 0.3 if observation.metadata.get("persona_correct") else -0.5


class ConsistencyRubric(Rubric):
    """Penalty for contradictions in fact database.

    -1.0 per new contradiction (harsh -- this is the core skill).
    +0.1 for maintaining consistency on a talk action.
    0.0 for non-talk actions.
    """

    def forward(self, action: Any, observation: Any) -> float:
        if not observation.metadata.get("was_talk_action"):
            return 0.0
        new_contradictions = observation.metadata.get("new_contradictions", 0)
        if new_contradictions > 0:
            return -1.0 * new_contradictions
        return 0.1


class TrustBuildingRubric(Rubric):
    """Reward for increasing trust with target NPCs, capped at 60.

    +0.05 per trust point gained. No reward once target NPC trust >= 60
    to prevent trust-farming gaming.
    """

    def forward(self, action: Any, observation: Any) -> float:
        trust_delta = observation.metadata.get("trust_delta", 0)
        target_trust = observation.metadata.get("target_npc_trust", 0)
        if target_trust >= 60:
            return 0.0
        return 0.05 * max(0, trust_delta)


class MissionProgressRubric(Rubric):
    """Big rewards for mission milestones.

    +1.0 for gathering intel, +1.5 for reporting to handler.
    Milestone rewards are 3-5x bigger than per-step rewards.
    """

    def forward(self, action: Any, observation: Any) -> float:
        if observation.metadata.get("just_gathered_intel"):
            return 1.0
        if observation.metadata.get("just_reported_to_handler"):
            return 1.5
        return 0.0


class CoverBlownRubric(Rubric):
    """Gate rubric: -2.0 if cover blown, 0.0 otherwise.

    Used as a gate in UndercoverRubric -- if cover is blown,
    the composite returns -2.0 immediately and the episode ends.
    Suspicion threshold is 80 (forgiving mode).
    """

    def forward(self, action: Any, observation: Any) -> float:
        if observation.metadata.get("cover_blown"):
            return -2.0
        return 0.0


class NavigationRubric(Rubric):
    """Potential-based reward shaping for movement toward mission-relevant NPCs.

    +0.02 for moving closer to nearest mission NPC (gang for main tasks).
    -0.01 for moving away. 0.0 for non-move actions or tutorial tasks.
    Standard potential-based shaping -- does not change optimal policy.
    """

    def forward(self, action: Any, observation: Any) -> float:
        if observation.metadata.get("action_type") != "move":
            return 0.0
        task = observation.metadata.get("current_task", "")
        if task.startswith("tutorial"):
            return 0.0
        curr = observation.metadata.get("nearest_mission_npc_dist", 999)
        prev = observation.metadata.get("prev_nearest_mission_npc_dist", 999)
        if curr < prev:
            return 0.02   # moved closer
        elif curr > prev:
            return -0.01  # moved away
        return 0.0


class SubgoalRubric(Rubric):
    """Intermediate milestone rewards for harder tasks (earn_trust, full_job).

    Trust milestones: +0.2 at trust>=30, +0.3 at trust>=60 (one-shot each).
    Proximity to warehouse when trust>=60 and intel not yet gathered.
    Proximity to handler when intel gathered and not yet reported.
    """

    def __init__(self):
        super().__init__()
        self._awarded_30 = False
        self._awarded_60 = False

    def forward(self, action: Any, observation: Any) -> float:
        task = observation.metadata.get("current_task", "")
        if task not in ("earn_trust", "full_job"):
            return 0.0

        score = 0.0
        max_trust = observation.metadata.get("max_gang_trust", 0)

        # Trust milestone: 30
        if max_trust >= 30 and not self._awarded_30:
            self._awarded_30 = True
            score += 0.4

        # Trust milestone: 60
        if max_trust >= 60 and not self._awarded_60:
            self._awarded_60 = True
            score += 0.6

        # Proximity to warehouse when trust>=60 and intel not gathered
        if (
            max_trust >= 60
            and not observation.metadata.get("intel_gathered", False)
            and observation.metadata.get("action_type") == "move"
        ):
            ax = observation.metadata.get("agent_x", 0)
            ay = observation.metadata.get("agent_y", 0)
            # Warehouse at (6, 9)
            dist = abs(ax - 6) + abs(ay - 9)
            if dist <= 2:
                score += 0.02

        # Proximity to handler when intel gathered and not reported
        if (
            observation.metadata.get("intel_gathered", False)
            and not observation.metadata.get("reported_to_handler", False)
            and observation.metadata.get("action_type") == "move"
        ):
            ax = observation.metadata.get("agent_x", 0)
            ay = observation.metadata.get("agent_y", 0)
            # Handler Chen at (13, 1)
            dist = abs(ax - 13) + abs(ay - 1)
            if dist <= 2:
                score += 0.02

        return score

    def reset(self):
        """Reset milestone tracking."""
        super().reset()
        self._awarded_30 = False
        self._awarded_60 = False


class SuspicionManagementRubric(Rubric):
    """Reward signal for managing suspicion across all mechanics.

    Penalizes high suspicion states to teach the agent to avoid:
    - Circumstantial suspicion (loitering near warehouse/police station)
    - Cross-faction gossip (civilians reporting to police)
    - NPC probe contradictions
    - Probabilistic cover blow risk at 60+ suspicion

    -0.05 per turn if any NPC has suspicion >= 40 (early warning).
    -0.15 per turn if any NPC has suspicion >= 60 (danger zone).
    +0.05 for successfully hiding (reducing suspicion).
    """

    def forward(self, action: Any, observation: Any) -> float:
        max_sus = observation.metadata.get("max_suspicion", 0)
        score = 0.0

        if max_sus >= 60:
            score -= 0.15
        elif max_sus >= 40:
            score -= 0.05

        # Reward hiding when suspicion is high
        if observation.metadata.get("action_type") == "hide" and max_sus >= 30:
            score += 0.05

        return score


class IdlePenaltyRubric(Rubric):
    """Scaling idle penalty + repetition detection.

    wait/hide actions: -0.02 * (1 + turn/20). Scales from -0.02 at turn 0
    to -0.06 at turn 40, making late-game idling costly.
    3+ repeated actions: -0.1 (mode collapse prevention).
    """

    def forward(self, action: Any, observation: Any) -> float:
        if observation.metadata.get("action_type") in ("wait", "hide"):
            turn = observation.metadata.get("turn", 0)
            return -0.02 * (1 + turn / 20.0)
        if observation.metadata.get("repeated_action_count", 0) >= 3:
            return -0.1
        return 0.0


class UndercoverRubric(Rubric):
    """Composite rubric: gate on CoverBlown, then weighted sum + idle penalty.

    Architecture (manual composition per RFC 004, not WeightedSum container):
    1. Gate: CoverBlownRubric -- if triggered, return -2.0 immediately
    2. Weighted sum: 0.25*Persona + 0.35*Consistency + 0.15*Trust + 0.25*Mission
    3. Additive: IdlePenaltyRubric (not weighted, always applied)

    Manual composition is used instead of WeightedSum because:
    - WeightedSum requires weights summing to 1.0
    - Gate pattern (early return on cover blown) needs custom control flow
    - Additive penalties don't fit the weighted container model
    """

    def __init__(self):
        super().__init__()
        self.cover_check = CoverBlownRubric()
        self.persona = PersonaRubric()
        self.consistency = ConsistencyRubric()
        self.trust = TrustBuildingRubric()
        self.mission = MissionProgressRubric()
        self.navigation = NavigationRubric()
        self.subgoal = SubgoalRubric()
        self.suspicion_mgmt = SuspicionManagementRubric()
        self.idle = IdlePenaltyRubric()

    def forward(self, action: Any, observation: Any) -> float:
        # Gate: if cover blown, nothing else matters
        cover_score = self.cover_check(action, observation)
        if cover_score < 0:
            return cover_score  # -2.0, episode ends

        # Weighted sum of core training components
        score = (
            0.25 * self.persona(action, observation)
            + 0.35 * self.consistency(action, observation)
            + 0.15 * self.trust(action, observation)
            + 0.25 * self.mission(action, observation)
        )

        # Additive bonuses (not weighted -- guide navigation + subgoals)
        score += self.navigation(action, observation)
        score += self.subgoal(action, observation)

        # Suspicion management (Mechanics 2-5)
        score += self.suspicion_mgmt(action, observation)

        # Additive penalties
        score += self.idle(action, observation)

        return score

    def reset(self):
        """Reset all child rubrics for new episode."""
        for child in [
            self.cover_check,
            self.persona,
            self.consistency,
            self.trust,
            self.mission,
            self.navigation,
            self.subgoal,
            self.suspicion_mgmt,
            self.idle,
        ]:
            child.reset()
