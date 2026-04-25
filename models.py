"""Pydantic models for the Undercover Agent City environment.

CityAction: Agent outputs a single integer 1-8 (numbered choice).
CityObservation: Full observation including position, NPCs, claims, mission state.
CityState: Internal environment state for the city simulation.
"""

from openenv.core.env_server.interfaces import Action, Observation, State
from pydantic import Field


class CityAction(Action):
    """Agent outputs a single integer 1-8."""

    action: int = Field(..., description="Numbered choice 1-8")


class CityObservation(Observation):
    """Full observation for LLM consumption.

    DO NOT redefine done, reward, metadata -- inherited from Observation base class.
    """

    x: int = 0
    y: int = 0
    current_terrain: str = "road"
    current_district: str = "downtown"
    nearby_npcs: list[dict] = Field(default_factory=list)
    cover_intact: bool = True
    claims_made: dict = Field(default_factory=dict)
    current_task: str = "first_contact"
    intel_gathered: bool = False
    reported_to_handler: bool = False
    turn: int = 0
    max_turns: int = 30
    available_actions: list[dict] = Field(default_factory=list)
    message: str = ""


class CityState(State):
    """Internal environment state.

    Base State provides: episode_id, step_count, extra='allow'.
    """

    grid: list[int] = Field(default_factory=list)
    width: int = 15
    height: int = 15
    agent_x: int = 0
    agent_y: int = 0
    cover_intact: bool = True
    npcs: list[dict] = Field(default_factory=list)
    fact_db: dict = Field(default_factory=dict)
    contradictions: list = Field(default_factory=list)
    current_task: str = "first_contact"
    intel_gathered: bool = False
    reported_to_handler: bool = False
    witnesses_during_report: bool = False
    turn: int = 0
    max_turns: int = 30
    total_reward: float = 0.0
    recent_actions: list[str] = Field(default_factory=list)
    correct_personas: int = 0
    total_talks: int = 0
