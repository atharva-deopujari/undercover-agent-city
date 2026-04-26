# Teaching an LLM to Be a Spy: Building the First Social Deception RL Environment

*Can you train a language model to lie convincingly — and get away with it?*

**[Full Presentation Deck](https://docs.google.com/presentation/d/1BlNIGa1F8K8l5HGxQ14G3P-tcsB2xtTc23yPU0yGSRI/edit?usp=sharing)**

---

## The Problem Nobody Is Training For

LLMs can solve differential equations, write legal briefs, and generate code that passes unit tests. But ask one to maintain a cover story across five different conversations with characters who compare notes? It contradicts itself within three turns.

This isn't a trivial failure. **Persona consistency under adversarial social pressure** is one of the unsolved challenges in AI. Research from NeurIPS 2025 shows that off-the-shelf LLMs drift from assigned personas, contradict earlier statements, and abandon role-appropriate behavior — reducing persona inconsistency by over 55% required dedicated multi-turn RL fine-tuning.

AvalonBench showed that ChatGPT achieves only 22% win rate in social deduction games — significantly worse than simple rule-based bots at 38%. Nobody has tried to *train* LLMs to get better at this. Until now.

## Undercover Agent City

**(Tbh I just wanted to build a Dhurandhar movie kind of scene where an undercover agent infiltrates a gang — but make the agent an LLM 😉)**

I built a social deception RL environment using Meta's OpenEnv framework. The premise: you're an undercover police agent infiltrating a criminal gang in a 15x15 city grid.

**8 NPCs. 3 factions. One mission.** Build trust with the gang, sneak into their warehouse for intel, and report back to your handler. Get caught? Game over.

### Why It's Genuinely Hard

This isn't Tic-Tac-Toe with extra steps. The environment creates real social dilemmas:

**The Persona Problem.** Each NPC responds best to a specific conversational approach — tough talk, measured respect, or casual chat. But it's not as simple as "gang = tough." Whisper is a gang member who prefers measured, respectful conversation. Kid Ravi is a civilian who responds to tough talk. The agent must learn *individual* preferences, not faction-level rules.

**The Consistency Trap.** Every claim the agent makes is recorded in a fact database. Tell Razor you're from southside, then tell Whisper you're from downtown — they're in the same faction. They compare notes. Contradiction detected. Suspicion spikes by 30 points. Three contradictions and your cover is blown.

**The Information Cascade.** Suspicious civilians report to patrolling police. A careless conversation with Old Man Liu can cascade into Officer Diaz tightening patrols around you. The agent must manage relationships across *all* factions, not just the target gang.

**The Ticking Clock.** Suspicion above 70 triggers probabilistic cover detection — every turn becomes a dice roll. The agent must balance mission progress against detection risk, knowing when to push forward and when to hide.

## The Reward Architecture

I designed 9 composable rubrics following OpenEnv's RFC 004 pattern — not a single monolithic reward function, but independent components that each capture one aspect of spy tradecraft:

| Component | What It Rewards | Signal Strength |
|-----------|----------------|-----------------|
| **Persona** | Matching your approach to the NPC | +0.3 / -0.5 |
| **Consistency** | Keeping your cover story straight | +0.1 / -1.0 per contradiction |
| **Trust Building** | Gaining NPC trust (capped at 60) | +0.05 per point |
| **Mission Progress** | Intel gathered, report delivered | +1.0 / +1.5 (milestone spikes) |
| **Navigation** | Moving toward mission-relevant NPCs | +0.02 / -0.01 |
| **Subgoal Milestones** | Trust thresholds reached | +0.4 at 30, +0.6 at 60 |
| **Idle Penalty** | Waiting or hiding too long | -0.02 scaling with turn |
| **Cover Blown** | Terminal failure gate | -2.0 |

The composite `UndercoverRubric` uses a gate-then-weighted-sum pattern: if cover is blown, return -2.0 immediately. Otherwise, compute the weighted sum of all components plus additive bonuses and penalties.

This architecture means the reward function is **hard to game**. An agent can't farm trust without risking contradictions. It can't hide to avoid suspicion without incurring idle penalties. It must actively engage with NPCs to score well — but every engagement carries risk.

## Preventing Reward Hacking: The Anti-Gaming Playbook

DeepMind's work on specification gaming taught me that RL agents will exploit every loophole in your reward function. I spent significant time adversarially testing my own environment before training. Here's what I found and how I fixed it:

### Hack #1: The Silent Agent
**Exploit:** An agent that never talks has perfect consistency (0 contradictions), perfect persona accuracy (0/0 = undefined), and keeps cover intact. It scores well by doing nothing.

**Fix:** Engagement-gated grading. Zero talks = 0.01 grade. The grading formula includes a `social_volume` component — `min(1.0, total_talks / (max_turns * 0.2))` — so agents MUST interact to score. I also added a scaling idle penalty that increases with turn count (`-0.02 * (1 + turn/20)`), making late-game passivity increasingly costly.

### Hack #2: The Trust Farmer
**Exploit:** Talk to one easy NPC repeatedly with the correct persona. Trust hits 100, grade is high, but the agent never actually completes the mission.

**Fix:** Trust reward is capped at 60 (`TrustBuildingRubric` returns 0.0 once target trust >= 60). The grading uses *average* gang trust across all gang NPCs, not max — so farming one NPC while ignoring others produces a lower score than spreading effort.

### Hack #3: The Action List Bias
**Exploit:** I discovered that my action generation was prioritizing correct-persona options (85% of talk actions had the right persona). A random agent scored 85% persona accuracy just by picking randomly — the action list was biased.

**Fix:** I shuffled all talk actions (correct and wrong personas together) before capping at 8 options. Random persona accuracy dropped to ~25% where it belongs.

### Hack #4: The Cover Story Leaker
**Exploit:** The observation showed exactly which NPC was told which claim — `"origin=southside (told to razor, whisper)"`. Consistency became trivial text matching rather than memory.

**Fix:** I removed per-NPC claim attribution from the observation. Now it shows `"origin=southside (told to 2 people)"` — the agent knows what it claimed but must track *who* it told from context and episode memory.

### Hack #5: The Faction Shortcut
**Exploit:** The observation showed NPC factions directly — `"Razor (gang)"`. Combined with the system prompt saying "TOUGH with gang," persona selection became a simple lookup table.

**Fix:** I removed the direct persona-faction mapping from the system prompt. The agent sees approaches described as "street-smart and blunt," "measured and respectful," and "easygoing and chatty" — it must learn through reward signal which approach each *individual* NPC prefers.

These anti-gaming measures are what separate a toy environment from one that genuinely teaches social intelligence. Each fix was motivated by actually catching the exploit in testing.

## The Training Journey: How I Broke It, Then Fixed It

### Attempt 1: Curriculum Learning (The Textbook Approach)

My plan was elegant: teach skills incrementally.

- **Phase 1** (200 steps): Tutorial — learn which approach works with one NPC
- **Phase 2** (200 steps): First Contact — navigate the city, talk to multiple NPCs  
- **Phase 3** (100 steps): Earn Trust — complete the full spy mission

Phase 1 worked beautifully. Persona accuracy jumped from 30% to 60% in 200 steps. The reward curve climbed steadily. I thought I'd cracked it.

Then Phase 2 started. Different data distribution, different NPCs, different observation patterns. Within 50 steps, the model **forgot Phase 1 entirely**. Persona accuracy crashed back to random. By the end of Phase 3, tutorial performance had regressed *below* the untrained baseline.

This is **catastrophic forgetting** in GRPO — a known theoretical risk, but experiencing it firsthand was sobering. The model literally got dumber at easy tasks after training on harder ones.

### Attempt 2: Mixed Training (The Fix That Worked)

I scrapped the curriculum. Combined all data — 30% tutorial, 40% first contact, 30% earn trust — into a single shuffled dataset. One GRPOTrainer call. No phase transitions.

The result: steady reward improvement with no drops. The model learned to handle all difficulty levels simultaneously without forgetting any.

### The Thinking Token Trap (The Bug That Almost Killed My Submission)

For hours, my training showed `reward_std = 0.000` on every step. All GRPO generations were producing identical outputs. Zero gradient. Zero learning. I tried everything — higher temperature, more generations, different sampling parameters.

The root cause was Qwen3's chat template. Without explicitly setting `enable_thinking=False`, the template prepends `<think>\n` to every generation. The model fills those tokens with internal reasoning. With `max_completion_length=12`, the thinking content consumed the entire budget — the actual action digit never got generated. `mask_truncated_completions=True` then zeroed out everything, making all generations appear identical.

The fix was two lines:
```python
generation_kwargs={"enable_thinking": False}
max_completion_length=32
```

Two lines. Hours of debugging. This is RL engineering.

## Results

**Model:** Qwen3-4B (4-bit quantized, LoRA r=32, alpha=64)

| Task | Random | Untrained | Trained | Improvement |
|------|--------|-----------|---------|-------------|
| Tutorial Persona | 0.433 | 0.300 | **1.000** | +233% |
| First Contact | 0.713 | 0.518 | **0.996** | +92% |
| Earn Trust | 0.239 | 0.150 | **0.822** | +448% |

The trained model achieves:
- **Perfect persona accuracy** on tutorial (100%, up from 30% untrained)
- **Near-perfect grade on first contact** (0.996 — the agent learned to navigate, talk, and maintain consistency)
- **4.5x improvement on the hardest task** (earn trust: 0.150 to 0.822)
- **Zero cover blown** across all evaluations

## The Spectator UI

I didn't just build an API. I built an isometric game visualization so you can actually *watch* the spy operate:

- Isometric 3D city with district-varied buildings
- Character sprites per faction with trust/suspicion ring indicators
- Real-time speech bubbles with anti-overlap stacking
- Playback controls: play/pause, speed (0.25x-4x), step, scrub
- Collapsible HUD panels: action deck, fact tracker, conversation transcript, trust charts
- DEMO mode with scripted episode and LIVE mode connected to the running server

Open it: [Spectator UI](https://atharvadeopujari-undercover-agent-city.hf.space/spectator)

## Why This Matters

Social deception sits at the intersection of several unsolved AI challenges:

- **Theory of mind** — modeling what others believe about you
- **Temporal consistency** — maintaining a coherent narrative across interactions  
- **Risk management** — balancing mission progress against detection probability
- **Individual adaptation** — learning that different people respond to different approaches

No prior work exists on RL training for LLM social deception. AvalonBench and Werewolf Arena only *evaluated* LLMs on social games. I believe this is the first attempt to *train* a model to improve at it.

The environment is open source, OpenEnv-compliant, and deployed on HuggingFace Spaces. Try it, train on it, break it.

## Links

- **Live Environment:** [HuggingFace Space](https://huggingface.co/spaces/atharvadeopujari/undercover-agent-city)
- **Spectator UI:** [Watch the Spy](https://atharvadeopujari-undercover-agent-city.hf.space/spectator)
- **API Docs:** [Interactive Swagger](https://atharvadeopujari-undercover-agent-city.hf.space/docs)
- **Source Code:** [GitHub](https://github.com/atharva-deopujari/undercover-agent-city)
- **Presentation Deck:** [Google Slides](https://docs.google.com/presentation/d/1BlNIGa1F8K8l5HGxQ14G3P-tcsB2xtTc23yPU0yGSRI/edit?usp=sharing)
- **Training Notebooks:** Included in the repo (Colab T4 + HF A100 versions)

---

*Built by Atharva Deopujari | [GitHub](https://github.com/atharva-deopujari)*
