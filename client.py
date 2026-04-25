"""Thin client for the Undercover Agent City environment.

CityEnv connects to the server via WebSocket. All game logic is server-side.
The client only handles serialization/deserialization of actions and observations.
"""

from openenv.core.client_types import StepResult
from openenv.core.env_client import EnvClient

from .models import CityAction, CityObservation, CityState


class CityEnv(EnvClient[CityAction, CityObservation, CityState]):
    """Thin client for Undercover Agent City environment.

    Connects to server via WebSocket. All game logic is server-side.

    Example:
        >>> with CityEnv(base_url="http://localhost:8000") as env:
        ...     result = env.reset()
        ...     print(result.observation.message)
        ...     result = env.step(CityAction(action=1))
    """

    def _step_payload(self, action: CityAction) -> dict:
        """Convert CityAction to wire format. Per D-07: single integer."""
        return {"action": action.action}

    def _parse_result(self, payload: dict) -> StepResult[CityObservation]:
        """Parse server response into StepResult with CityObservation."""
        obs = CityObservation(**payload["observation"])
        return StepResult(
            observation=obs,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: dict) -> CityState:
        """Parse full state from server (used for debugging/visualization)."""
        return CityState(**payload)
