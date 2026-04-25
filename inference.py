"""
Baseline inference agent for the Undercover Agent City environment.

Two-stage architecture:
 1. System prompt: defines the agent's strategic persona (spy game expert).
 2. Per-turn action selection: LLM reads the observation message and picks
    the best numbered action (1-8).

Supports local (direct import) and remote (via EnvClient) execution.
Run: python inference.py --task first_contact --episodes 5
"""

import argparse
import json
import os
import random
import re
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")
EPISODES_PER_TASK = int(os.getenv("EPISODES_PER_TASK", "3"))
INFERENCE_TEMPERATURE = float(os.getenv("INFERENCE_TEMPERATURE", "0.1"))

ALL_TASKS = [
    "tutorial_persona",
    "tutorial_consistency",
    "first_contact",
    "earn_trust",
    "full_job",
]

BENCHMARK_NAME = "undercover_agent_city"
SUCCESS_SCORE_THRESHOLD = 0.30

# ---------------------------------------------------------------------------
# System prompt -- the "plan" stage (constant across all turns)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an undercover agent infiltrating a criminal gang in a city. /no_think\n"
    "Pick the BEST action number. \n"
    "TOUGH with gang, FORMAL with police, CASUAL with civilians. \n"
    "Keep your cover story CONSISTENT — never contradict what you told same-faction NPCs.\n"
    "Output ONLY a single number. Nothing else."
)

# ---------------------------------------------------------------------------
# LLM Backend
# ---------------------------------------------------------------------------


class LLMBackend:
    """Text-generation backend interface."""

    provider_name: str = "unknown"

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8,
    ) -> str:
        raise NotImplementedError


class OpenAICompatibleBackend(LLMBackend):
    provider_name = "openai_compatible"

    def __init__(self, client: Any, model_name: str):
        self.client = client
        self.model_name = model_name

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        # Newer models (gpt-5+, o-series) require max_completion_tokens
        is_new_model = any(
            self.model_name.startswith(p) for p in ("gpt-5", "o1", "o3", "o4")
        )
        token_param = "max_completion_tokens" if is_new_model else "max_tokens"
        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            token_param: max_tokens,
        }
        if not is_new_model or INFERENCE_TEMPERATURE == 1.0:
            kwargs["temperature"] = INFERENCE_TEMPERATURE
        try:
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as exc:
            print(f"[DEBUG] LLM API error: {exc}", flush=True)
            return ""


def create_llm_backend() -> LLMBackend:
    """Build the OpenAI-compatible backend from env vars."""
    if not HF_TOKEN:
        raise RuntimeError(
            "Missing API credentials. Set HF_TOKEN or OPENAI_API_KEY before running inference.py."
        )
    from openai import OpenAI

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    return OpenAICompatibleBackend(client=client, model_name=MODEL_NAME)


# ---------------------------------------------------------------------------
# Action parsing (handles Qwen3 <think> tags)
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_action_number(raw: str, num_actions: int) -> int:
    """Extract an integer action from LLM output.

    Strips <think>...</think> blocks (Qwen3 models), then finds
    the first integer in the remaining text. Falls back to 1 if parsing fails.
    Returns a valid 1-indexed action clamped to [1, num_actions].
    """
    cleaned = _THINK_RE.sub("", raw).strip()
    # Find the first integer in the cleaned text
    match = re.search(r"\b(\d+)\b", cleaned)
    if match:
        val = int(match.group(1))
        return max(1, min(val, num_actions))
    return 1  # Safe fallback


# ---------------------------------------------------------------------------
# Structured logging (matches vendor_negotiation_gym pattern)
# ---------------------------------------------------------------------------


def log_start(task: str, env_name: str, model: str) -> None:
    print(f"[START] task={task} env={env_name} model={model}", flush=True)


def log_step(
    step: int, action: int, reward: float, done: bool, error: Optional[str]
) -> None:
    error_val = error if error else "null"
    done_val = str(bool(done)).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Environment interface (local or remote)
# ---------------------------------------------------------------------------


def create_env(env_url: str, use_local: bool = False):
    """Create either a local CityEnvironment or a remote CityEnv client.

    Returns a context-manager-compatible env object with reset/step/state/grade.
    """
    if use_local:
        return LocalEnvWrapper()
    return RemoteEnvWrapper(env_url)


class LocalEnvWrapper:
    """Wrapper around CityEnvironment for direct (in-process) usage."""

    def __init__(self):
        from undercover_agent_city.server.city_environment import CityEnvironment

        self._env = CityEnvironment()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def reset(self, seed: int = 42, task: str = "first_contact"):
        obs = self._env.reset(seed=seed, task=task)
        return _obs_to_dict(obs)

    def step(self, action: int):
        from undercover_agent_city.models import CityAction

        obs = self._env.step(CityAction(action=action))
        return _obs_to_dict(obs)

    def grade(self) -> float:
        return self._env.grade_episode()


class RemoteEnvWrapper:
    """Wrapper around CityEnv (EnvClient) for remote server usage."""

    def __init__(self, env_url: str):
        self._env_url = env_url
        self._client = None

    def __enter__(self):
        from undercover_agent_city import CityEnv

        self._client = CityEnv(base_url=self._env_url).sync()
        self._client.__enter__()
        return self

    def __exit__(self, *args):
        if self._client:
            self._client.__exit__(*args)

    def reset(self, seed: int = 42, task: str = "first_contact"):
        result = self._client.reset(seed=seed, task=task)
        obs = result.observation
        return {
            "message": obs.message,
            "available_actions": obs.available_actions,
            "done": getattr(obs, "done", False) or result.done,
            "reward": float(result.reward or 0.0),
            "turn": obs.turn,
            "max_turns": obs.max_turns,
            "cover_intact": obs.cover_intact,
            "intel_gathered": obs.intel_gathered,
            "reported_to_handler": obs.reported_to_handler,
            "current_task": obs.current_task,
        }

    def step(self, action: int):
        from undercover_agent_city.models import CityAction

        result = self._client.step(CityAction(action=action))
        obs = result.observation
        return {
            "message": obs.message,
            "available_actions": obs.available_actions,
            "done": getattr(obs, "done", False) or result.done,
            "reward": float(result.reward or 0.0),
            "turn": obs.turn,
            "max_turns": obs.max_turns,
            "cover_intact": obs.cover_intact,
            "intel_gathered": obs.intel_gathered,
            "reported_to_handler": obs.reported_to_handler,
            "current_task": obs.current_task,
        }

    def grade(self) -> float:
        """Get grade from server state. Falls back to reward-based estimate."""
        try:
            state = self._client.state()
            # CityState doesn't have grade_score -- compute from total_reward
            total_reward = getattr(state, "total_reward", 0.0)
            # Normalize: clamp to [0, 1] range
            return max(0.0, min(1.0, total_reward))
        except Exception:
            return 0.0


def _obs_to_dict(obs) -> dict:
    """Convert a CityObservation to a plain dict for uniform handling."""
    return {
        "message": obs.message,
        "available_actions": obs.available_actions,
        "done": getattr(obs, "done", False),
        "reward": float(getattr(obs, "reward", 0.0) or 0.0),
        "turn": obs.turn,
        "max_turns": obs.max_turns,
        "cover_intact": obs.cover_intact,
        "intel_gathered": obs.intel_gathered,
        "reported_to_handler": obs.reported_to_handler,
        "current_task": obs.current_task,
    }


# ---------------------------------------------------------------------------
# Episode runners
# ---------------------------------------------------------------------------


def _run_llm_episode(
    env,
    llm: LLMBackend,
    task: str,
    seed: int,
    model_name: str,
) -> float:
    """Run one episode with the LLM agent. Returns grade score."""
    log_start(task=task, env_name=BENCHMARK_NAME, model=model_name)

    rewards: List[float] = []
    steps_taken = 0
    score = 0.001
    success = False

    try:
        obs = env.reset(seed=seed, task=task)
        step_idx = 0

        while not obs["done"]:
            num_actions = len(obs["available_actions"])
            if num_actions == 0:
                break

            # Build the user prompt from the observation message
            prompt = obs["message"]

            # Get LLM response
            raw_response = llm.generate_text(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=16,  # Allow a bit more for <think> models
            )

            action = parse_action_number(raw_response, num_actions)
            obs = env.step(action)
            step_idx += 1
            steps_taken = step_idx

            reward = obs["reward"]
            rewards.append(reward)

            log_step(
                step=step_idx,
                action=action,
                reward=reward,
                done=obs["done"],
                error=None,
            )

        # Get final grade
        score = env.grade()
        score = max(0.001, min(0.999, score))
        success = score >= SUCCESS_SCORE_THRESHOLD
        return score

    except Exception as exc:
        print(f"[DEBUG] Episode failed: {exc}", flush=True)
        traceback.print_exc()
        return max(score, 0.001)

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


def _run_random_episode(env, task: str, seed: int) -> float:
    """Run one episode with random action selection. Returns grade score."""
    log_start(task=task, env_name=BENCHMARK_NAME, model="random_baseline")

    rewards: List[float] = []
    steps_taken = 0
    score = 0.001
    success = False
    rng = random.Random(seed)

    try:
        obs = env.reset(seed=seed, task=task)
        step_idx = 0

        while not obs["done"]:
            num_actions = len(obs["available_actions"])
            if num_actions == 0:
                break

            action = rng.randint(1, num_actions)
            obs = env.step(action)
            step_idx += 1
            steps_taken = step_idx

            reward = obs["reward"]
            rewards.append(reward)

            log_step(
                step=step_idx,
                action=action,
                reward=reward,
                done=obs["done"],
                error=None,
            )

        score = env.grade()
        score = max(0.001, min(0.999, score))
        success = score >= SUCCESS_SCORE_THRESHOLD
        return score

    except Exception as exc:
        print(f"[DEBUG] Random episode failed: {exc}", flush=True)
        return max(score, 0.001)

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_inference(
    tasks: List[str],
    episodes: int,
    use_local: bool = False,
    run_random: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Run LLM agent (and optionally random baseline) across tasks.

    Returns:
        Dict mapping task_id -> {"llm": {...}, "random": {...}} with scores.
    """
    llm = create_llm_backend()
    all_results: Dict[str, Dict[str, Any]] = {}

    with create_env(ENV_URL, use_local=use_local) as env:
        for task in tasks:
            print(f"\n{'='*60}", flush=True)
            print(f"  Task: {task}  |  Episodes: {episodes}", flush=True)
            print(f"{'='*60}", flush=True)

            # --- LLM Agent ---
            llm_scores: List[float] = []
            for ep in range(episodes):
                print(f"\n--- LLM Episode {ep+1}/{episodes} ---", flush=True)
                ep_score = _run_llm_episode(
                    env=env,
                    llm=llm,
                    task=task,
                    seed=ep,
                    model_name=MODEL_NAME,
                )
                llm_scores.append(ep_score)

            llm_avg = sum(llm_scores) / len(llm_scores) if llm_scores else 0.0

            task_result: Dict[str, Any] = {
                "llm": {
                    "average_score": round(llm_avg, 4),
                    "scores": [round(s, 4) for s in llm_scores],
                    "model": MODEL_NAME,
                },
            }

            # --- Random Baseline ---
            if run_random:
                random_scores: List[float] = []
                for ep in range(episodes):
                    print(f"\n--- Random Episode {ep+1}/{episodes} ---", flush=True)
                    ep_score = _run_random_episode(
                        env=env,
                        task=task,
                        seed=ep,
                    )
                    random_scores.append(ep_score)

                random_avg = (
                    sum(random_scores) / len(random_scores) if random_scores else 0.0
                )
                task_result["random"] = {
                    "average_score": round(random_avg, 4),
                    "scores": [round(s, 4) for s in random_scores],
                }

            all_results[task] = task_result

    # --- Summary Table ---
    print(f"\n{'='*72}", flush=True)
    print(f"  FINAL RESULTS  |  Model: {MODEL_NAME}", flush=True)
    print(f"{'='*72}", flush=True)
    header = f"{'Task':<25} {'LLM Avg':>10} {'Random Avg':>12} {'Improvement':>12}"
    print(header, flush=True)
    print("-" * 72, flush=True)

    for task, result in all_results.items():
        llm_avg = result["llm"]["average_score"]
        random_avg = result.get("random", {}).get("average_score", 0.0)
        improvement = llm_avg - random_avg
        sign = "+" if improvement >= 0 else ""
        print(
            f"{task:<25} {llm_avg:>10.4f} {random_avg:>12.4f} {sign}{improvement:>11.4f}",
            flush=True,
        )

    print("-" * 72, flush=True)

    # Overall averages
    all_llm = [r["llm"]["average_score"] for r in all_results.values()]
    all_random = [
        r.get("random", {}).get("average_score", 0.0) for r in all_results.values()
    ]
    overall_llm = sum(all_llm) / len(all_llm) if all_llm else 0.0
    overall_random = sum(all_random) / len(all_random) if all_random else 0.0
    overall_imp = overall_llm - overall_random
    sign = "+" if overall_imp >= 0 else ""
    print(
        f"{'OVERALL':<25} {overall_llm:>10.4f} {overall_random:>12.4f} {sign}{overall_imp:>11.4f}",
        flush=True,
    )

    print(f"\n[SUMMARY] results={json.dumps(all_results)}", flush=True)
    return all_results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Undercover Agent City -- Baseline Inference Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python inference.py                                    # Run all 5 tasks, 3 episodes each
  python inference.py --task first_contact --episodes 5  # Single task
  python inference.py --task earn_trust --no-random       # Skip random baseline
  python inference.py --local                             # Use local env (no server)
""",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        choices=ALL_TASKS,
        help="Run a single task (default: all tasks)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help=f"Episodes per task (default: {EPISODES_PER_TASK}, or EPISODES_PER_TASK env var)",
    )
    parser.add_argument(
        "--no-random",
        action="store_true",
        help="Skip the random baseline comparison",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local CityEnvironment directly (no server needed)",
    )
    parser.add_argument(
        "--env-url",
        type=str,
        default=None,
        help=f"Environment server URL (default: {ENV_URL}, or ENV_URL env var)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Model name (default: {MODEL_NAME}, or MODEL_NAME env var)",
    )

    args = parser.parse_args()

    # Apply CLI overrides to globals
    global ENV_URL, MODEL_NAME, EPISODES_PER_TASK
    if args.env_url:
        ENV_URL = args.env_url
    if args.model:
        MODEL_NAME = args.model

    tasks = [args.task] if args.task else ALL_TASKS
    episodes = args.episodes if args.episodes is not None else EPISODES_PER_TASK

    print(f"Undercover Agent City Inference Agent", flush=True)
    print(f"  Model:    {MODEL_NAME}", flush=True)
    print(f"  API Base: {API_BASE_URL}", flush=True)
    print(f"  Env URL:  {ENV_URL}", flush=True)
    print(f"  Tasks:    {', '.join(tasks)}", flush=True)
    print(f"  Episodes: {episodes}", flush=True)
    print(f"  Random:   {'yes' if not args.no_random else 'no'}", flush=True)
    print(f"  Local:    {'yes' if args.local else 'no'}", flush=True)
    print("", flush=True)

    start_time = time.time()

    results = run_inference(
        tasks=tasks,
        episodes=episodes,
        use_local=args.local,
        run_random=not args.no_random,
    )

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
