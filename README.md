---
title: Undercover Agent City
emoji: "\U0001F575\uFE0F"
colorFrom: indigo
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: 'Train an LLM Spy — Social deception RL env'
---

# Undercover Agent City

**Train an LLM to be a Spy** — A social deception RL environment for the Meta OpenEnv Hackathon 2026

[Live Environment](https://huggingface.co/spaces/atharvadeopujari/undercover-agent-city) | [GitHub](https://github.com/atharva-deopujari/undercover-agent-city) | [Spectator UI](https://atharvadeopujari-undercover-agent-city.hf.space/spectator) | [Training Notebooks](undercover_agent_city_mixed_training_hf.ipynb)

![Spectator Demo](assets/spectator_demo.gif)

[![Presentation Deck](assets/ppt.png)](https://docs.google.com/presentation/d/1BlNIGa1F8K8l5HGxQ14G3P-tcsB2xtTc23yPU0yGSRI/edit?usp=sharing)

---

## The Problem

LLMs can write poetry and solve math, but ask them to maintain a cover story across multiple conversations with different people who compare notes? They contradict themselves within 3 turns.

**Undercover Agent City** is the first RL environment designed to train LLMs in social deception — reading people, choosing the right conversational approach, maintaining a consistent cover story, and completing spy missions without getting caught.

## How It Works

You're an undercover police agent infiltrating a criminal gang in a 15x15 city grid. 8 NPCs from 3 factions roam the streets — gang members, police contacts, and civilians.

**Your mission:** Build trust with the gang, gather intel from their warehouse, and report back to your handler. Get caught? Game over.

### The Social Challenge

Each NPC responds to a different conversational **approach** (tough, formal, casual) and the agent must figure out which works for whom. Every claim you make is tracked — tell Razor you're from southside, then tell Whisper you're from downtown? They compare notes. Contradiction detected. Suspicion skyrockets.

### Task Progression

| Task | Turns | Objective | Difficulty |
|------|-------|-----------|------------|
| `tutorial_persona` | 1 | Pick the right approach for one NPC | Entry |
| `first_contact` | 30 | Navigate city, talk to multiple NPCs | Medium |
| `earn_trust` | 50 | Build trust >= 60, gather intel | Hard |
| `full_job` | 80 | Full mission: trust + intel + report | Expert |

### Reward System

Composable rubrics following OpenEnv RFC 004:

| Rubric | Signal | Weight |
|--------|--------|--------|
| PersonaRubric | +0.3 correct / -0.5 wrong approach | 0.25 |
| ConsistencyRubric | +0.1 consistent / -1.0 contradiction | 0.35 |
| TrustBuildingRubric | +0.05 per trust point gained | 0.15 |
| MissionProgressRubric | +1.0 intel / +1.5 report delivered | 0.25 |
| NavigationRubric | +0.02 closer / -0.01 farther from target | additive |
| SubgoalRubric | +0.4 at trust 30 / +0.6 at trust 60 | additive |
| IdlePenaltyRubric | -0.02 scaling with turn count | additive |
| CoverBlownRubric | -2.0 (episode terminates) | gate |

## Training: The Curriculum That Failed

### Attempt 1: Sequential Curriculum

We designed a 3-phase curriculum — teach persona selection first (200 steps), then multi-NPC interaction (200 steps), then full trust-building (100 steps).

Phase 1 worked. Persona accuracy jumped from 30% to 60%. Then Phase 2 started on different data, and the model **forgot Phase 1 skills entirely**. By Phase 3, tutorial performance regressed below random.

![Curriculum Reward Curve](assets/plots/curriculum_reward_curve.png)
*Reward climbs during Phase 1, drops at each phase transition (red/blue lines). Classic catastrophic forgetting.*

![Phase Evaluation](assets/plots/curriculum_eval_by_phase.png)
*After Phase 3 (purple), tutorial_persona performance is WORSE than After Phase 1 (green). The model got dumber on easy tasks.*

### Attempt 2: Mixed Training (The Fix)

We scrapped the curriculum and combined all data into a single training run — 30% tutorial + 40% first_contact + 30% earn_trust, shuffled together, trained in one GRPOTrainer call.

No phase transitions. No forgetting. Clear upward reward signal.

![Training Progress](assets/plots/training_progress.png)
*Left: GRPO training loss. Right: Average reward climbs from -2.5 to +1.5, stabilizing in positive territory — the model learned to pick correct approaches and maintain consistency.*

## Results

**Model:** Qwen3-4B (4-bit quantized, LoRA r=32, alpha=64)  
**Training:** GRPO mixed dataset, Colab T4

![Before/After Comparison](assets/plots/mixed_eval_comparison.png)

| Task | Random | Untrained | Trained | Delta |
|------|--------|-----------|---------|-------|
| tutorial_persona (persona) | 43% | 30% | **100%** | +70% |
| tutorial_persona (grade) | 0.433 | 0.300 | **1.000** | +0.700 |
| first_contact (grade) | 0.713 | 0.518 | **0.996** | +0.478 |
| earn_trust (grade) | 0.239 | 0.150 | **0.822** | +0.672 |

The trained model achieves:
- **Perfect persona accuracy** on tutorial (100%, up from 30%)
- **Near-perfect first_contact grade** (0.996, up from 0.518)
- **3.5x improvement on earn_trust** (0.822 vs 0.239 random baseline)
- **Zero cover blown** across all evaluations

## Spectator UI

We built an isometric game-style visualization to watch the agent in action:

- **Isometric 3D city** with district-varied buildings (downtown towers, dock warehouses, residential houses)
- **Character sprites** per faction (gang in red, police in blue, civilians in white, agent in amber)
- **Real-time trust/suspicion rings** around each NPC
- **Speech bubbles** with anti-overlap stacking
- **Playback controls**: play/pause, speed (0.25x-4x), step forward/back, scrub bar
- **Collapsible HUD panels**: action deck, fact tracker, conversation transcript, trust charts
- **DEMO mode** (scripted episode) and **LIVE mode** (WebSocket to running server)
- **Cover-blown overlay** with dramatic red alarm flash

Access at: `/spectator` on the deployed Space

## Technical Stack

- **Environment:** OpenEnv (latest), FastAPI, Python 3.11
- **Training:** TRL GRPOTrainer + Unsloth (4-bit QLoRA)
- **Model:** Qwen3-4B
- **Frontend:** React 18 + isometric SVG rendering
- **Deployment:** HuggingFace Spaces (Docker)

## Running Locally

```bash
git clone https://huggingface.co/spaces/atharvadeopujari/undercover-agent-city
cd undercover-agent-city
pip install -e .

# Start server
ENABLE_WEB_INTERFACE=true uvicorn undercover_agent_city.server.app:app --port 7860

# Open spectator
open http://localhost:7860/spectator

# Run inference
python inference.py --local --task earn_trust --episodes 5
```

## Training

```bash
# Upload undercover_agent_city.zip to Google Colab
# Open undercover_agent_city_training.ipynb
# Run all cells (requires T4 GPU, ~2 hours)
```

Three training notebooks included:
- `undercover_agent_city_sequential_training.ipynb` — curriculum approach (demonstrates forgetting)
- `undercover_agent_city_training.ipynb` — mixed training for Colab T4
- `undercover_agent_city_training_hf.ipynb` — mixed training for HF JupyterLab (A100)

## API Endpoints

Standard OpenEnv interface:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Start new episode |
| `/step` | POST | Take an action |
| `/state` | GET | Current game state |
| `/metadata` | GET | Environment info |
| `/health` | GET | Health check |
| `/spectator` | GET | Isometric game UI |
| `/web` | GET | Grid-based web UI |

## Why This Matters

Social deception is one of the hardest challenges for AI. Unlike math or code where correctness is binary, social manipulation requires theory of mind, temporal consistency, risk management, and individual adaptation.

No prior work exists on RL training for LLM social deception. AvalonBench and Werewolf Arena only *evaluated* LLMs on social games — nobody trained them to improve. This environment opens a new research direction.

## What We Learned

1. **Curriculum learning causes catastrophic forgetting in GRPO** — mixed training eliminates it
2. **Reward function design is the real engineering challenge** — composable rubrics with multiple independent signals work better than monolithic scoring
3. **Social deception is genuinely hard for LLMs** — even with explicit persona labels, maintaining consistency across NPCs requires real learning
4. **The training curve tells the story** — judges (and researchers) want to see improvement over time, not just final numbers

## Developed by Atharva Deopujari | [GitHub](https://github.com/atharva-deopujari)