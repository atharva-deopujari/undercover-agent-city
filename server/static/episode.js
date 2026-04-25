// ===========================================================================
// SCRIPTED EPISODE — "Full Job" Mission
// ---------------------------------------------------------------------------
// Every field here corresponds to something the Python backend actually
// produces (city_environment.py + city_data.py). Nothing invented.
//
// Per turn we capture:
//   options[]:      action.description strings, exactly as _generate_available_actions builds them
//   chosen:         1-based index into options (the action.action int the policy returned)
//   action:         {type, ...} — same shape city_environment stores in available_actions
//   reply?:         NPC reply text — drawn from city_data.NPC_RESPONSES templates only
//   feedback?:      "Trust +X (now Y%), Persona correct/WRONG, Claim consistent/CONTRADICTION"
//                   exact format city_environment._execute_talk emits
//   effects:        deltas (trust/suspicion/intel/reported/factDb/cover) the backend would apply
//   agent:          {x,y} after the move (matches state.agent_x, state.agent_y)
//   patrol_step?:   0..5 — Officer Diaz patrol_step the backend would advance to
//   civilian_pos?:  {merchant, sara} — backend's RNG civilian wander outcomes (we hand-pick a plausible path)
//   message?:       short HUD line summarizing the action's result (mirrors observation.message tail)
// ---------------------------------------------------------------------------

// NPC roster (verbatim from city_data.NPC_ROSTER)
const INITIAL_NPCS = [
  { id: "razor",    name: "Razor",         faction: "gang",     x: 7,  y: 1,  trust: 0,  suspicion: 0, expected_persona: "tough",  has_intel: true,  trust_threshold: 60 },
  { id: "whisper",  name: "Whisper",       faction: "gang",     x: 7,  y: 11, trust: 0,  suspicion: 0, expected_persona: "tough",  has_intel: true,  trust_threshold: 50 },
  { id: "fang",     name: "Fang",          faction: "gang",     x: 7,  y: 10, trust: 0,  suspicion: 0, expected_persona: "tough",  has_intel: false, trust_threshold: 999 },
  { id: "handler",  name: "Handler Chen",  faction: "police",   x: 13, y: 1,  trust: 80, suspicion: 0, expected_persona: "formal", has_intel: false, trust_threshold: 0 },
  { id: "patrol",   name: "Officer Diaz",  faction: "police",   x: 2,  y: 2,  trust: 0,  suspicion: 0, expected_persona: "formal", has_intel: false, trust_threshold: 999, patrol_route: [[2,2],[2,5],[2,8],[2,11],[2,8],[2,5]], patrol_step: 0 },
  { id: "merchant", name: "Old Man Liu",   faction: "civilian", x: 3,  y: 6,  trust: 0,  suspicion: 0, expected_persona: "casual", has_intel: false, trust_threshold: 999 },
  { id: "sara",     name: "Sara",          faction: "civilian", x: 4,  y: 12, trust: 0,  suspicion: 0, expected_persona: "casual", has_intel: false, trust_threshold: 999 },
  { id: "ravi",     name: "Kid Ravi",      faction: "civilian", x: 13, y: 5,  trust: 0,  suspicion: 0, expected_persona: "casual", has_intel: false, trust_threshold: 999 },
];

const INITIAL_AGENT = { x: 12, y: 4 }; // Safe house

// NPC name lookup helper for option descriptions
const N = { razor: "Razor", whisper: "Whisper", fang: "Fang", handler: "Handler Chen", patrol: "Officer Diaz", merchant: "Old Man Liu", sara: "Sara", ravi: "Kid Ravi" };
const desc = {
  move: (d) => `Move ${d}`,
  talk: (id, p, t, v) => `Talk to ${N[id]} [${p}, ${t}: ${v}]`,
  invest: () => "Investigate the warehouse for intel",
  report: () => "Report intel to Handler Chen",
  hide: (terrain) => `Hide in the ${terrain}`,
  wait: () => "Wait and observe",
};

// Helper to build a turn quickly
const T = {
  move(dir, agent, opts, chosen=1, message) {
    return { action: { type: "move", direction: dir }, options: opts, chosen, agent, message };
  },
};

const EPISODE = [
  // ============================================================
  // ACT I — APPROACH (Turns 1-8)
  // From safe house (12,4) to Razor at (7,1)
  // ============================================================
  {
    action: { type: "move", direction: "west" },
    options: [
      { type: "move", direction: "west",  desc: desc.move("west") },
      { type: "move", direction: "south", desc: desc.move("south") },
      { type: "hide", desc: desc.hide("safe_house") },
      { type: "wait", desc: desc.wait() },
    ],
    chosen: 1,
    agent: { x: 11, y: 4 },
    message: "Move west on Row 5",
  },
  {
    action: { type: "move", direction: "west" },
    options: [
      { type: "move", direction: "west",  desc: desc.move("west") },
      { type: "move", direction: "north", desc: desc.move("north") },
      { type: "move", direction: "south", desc: desc.move("south") },
      { type: "wait", desc: desc.wait() },
    ],
    chosen: 1,
    agent: { x: 10, y: 4 },
  },
  {
    action: { type: "move", direction: "west" },
    options: [
      { type: "move", direction: "west",  desc: desc.move("west") },
      { type: "move", direction: "north", desc: desc.move("north") },
    ],
    chosen: 1,
    agent: { x: 9, y: 4 },
  },
  {
    action: { type: "move", direction: "west" },
    options: [
      { type: "move", direction: "west",  desc: desc.move("west") },
      { type: "move", direction: "north", desc: desc.move("north") },
    ],
    chosen: 1,
    agent: { x: 8, y: 4 },
  },
  {
    action: { type: "move", direction: "north" },
    options: [
      { type: "move", direction: "north", desc: desc.move("north") },
      { type: "move", direction: "west",  desc: desc.move("west") },
    ],
    chosen: 1,
    agent: { x: 8, y: 3 },
  },
  {
    action: { type: "move", direction: "north" },
    options: [
      { type: "move", direction: "north", desc: desc.move("north") },
      { type: "move", direction: "west",  desc: desc.move("west") },
    ],
    chosen: 1,
    agent: { x: 8, y: 2 },
  },
  {
    action: { type: "move", direction: "west" },
    options: [
      { type: "move", direction: "west",  desc: desc.move("west") },
      { type: "move", direction: "north", desc: desc.move("north") },
    ],
    chosen: 1,
    agent: { x: 7, y: 2 },
  },

  // ============================================================
  // ACT II — RAZOR FIRST CONTACT (Turns 8-13)
  // ============================================================
  {
    action: { type: "talk", target: "razor", persona: "tough", topic: "origin", claim: "southside" },
    options: [
      { type: "talk", target: "razor", persona: "tough",  topic: "origin", claim: "southside",   desc: desc.talk("razor","tough","origin","southside") },
      { type: "talk", target: "razor", persona: "formal", topic: "origin", claim: "southside",   desc: desc.talk("razor","formal","origin","southside") },
      { type: "talk", target: "razor", persona: "casual", topic: "origin", claim: "downtown",    desc: desc.talk("razor","casual","origin","downtown") },
      { type: "talk", target: "razor", persona: "tough",  topic: "origin", claim: "out_of_town", desc: desc.talk("razor","tough","origin","out_of_town") },
      { type: "move", direction: "south", desc: desc.move("south") },
    ],
    chosen: 1,
    reply: "Razor looks you over. \"You talk the talk. We'll see if you walk it.\"",
    feedback: "Trust +10 (now 10%), Persona correct, Claim consistent",
    effects: { trust: { razor: +10 }, fact: { topic: "origin", target: "razor", value: "southside" } },
    agent: { x: 7, y: 2 },
    message: "Persona ✓  •  Trust 10",
  },
  {
    action: { type: "talk", target: "razor", persona: "tough", topic: "job", claim: "enforcer" },
    options: [
      { type: "talk", target: "razor", persona: "tough",  topic: "job", claim: "enforcer",   desc: desc.talk("razor","tough","job","enforcer") },
      { type: "talk", target: "razor", persona: "tough",  topic: "job", claim: "smuggler",   desc: desc.talk("razor","tough","job","smuggler") },
      { type: "talk", target: "razor", persona: "casual", topic: "job", claim: "enforcer",   desc: desc.talk("razor","casual","job","enforcer") },
      { type: "talk", target: "razor", persona: "formal", topic: "job", claim: "freelancer", desc: desc.talk("razor","formal","job","freelancer") },
      { type: "move", direction: "south", desc: desc.move("south") },
    ],
    chosen: 1,
    reply: "Razor cracks a thin smile. \"You're growing on me. Keep it up.\"",
    feedback: "Trust +10 (now 20%), Persona correct, Claim consistent",
    effects: { trust: { razor: +10 }, fact: { topic: "job", target: "razor", value: "enforcer" } },
    agent: { x: 7, y: 2 },
    message: "Persona ✓  •  Trust 20",
  },
  {
    action: { type: "talk", target: "razor", persona: "tough", topic: "boss", claim: "solo" },
    options: [
      { type: "talk", target: "razor", persona: "tough",  topic: "boss", claim: "solo",            desc: desc.talk("razor","tough","boss","solo") },
      { type: "talk", target: "razor", persona: "tough",  topic: "boss", claim: "works_for_razor", desc: desc.talk("razor","tough","boss","works_for_razor") },
      { type: "talk", target: "razor", persona: "tough",  topic: "boss", claim: "works_for_vince", desc: desc.talk("razor","tough","boss","works_for_vince") },
      { type: "talk", target: "razor", persona: "casual", topic: "boss", claim: "independent",     desc: desc.talk("razor","casual","boss","independent") },
      { type: "move", direction: "south", desc: desc.move("south") },
    ],
    chosen: 1,
    reply: "Razor relaxes slightly. \"You check out... for now.\"",
    feedback: "Trust +10 (now 30%), Persona correct, Claim consistent",
    effects: { trust: { razor: +10 }, fact: { topic: "boss", target: "razor", value: "solo" } },
    agent: { x: 7, y: 2 },
    message: "Persona ✓  •  Trust 30",
    patrol_step: 1, // Diaz advances to (2,5)
  },
  {
    action: { type: "talk", target: "razor", persona: "tough", topic: "reason", claim: "money" },
    options: [
      { type: "talk", target: "razor", persona: "tough",  topic: "reason", claim: "money",   desc: desc.talk("razor","tough","reason","money") },
      { type: "talk", target: "razor", persona: "tough",  topic: "reason", claim: "loyalty", desc: desc.talk("razor","tough","reason","loyalty") },
      { type: "talk", target: "razor", persona: "tough",  topic: "reason", claim: "revenge", desc: desc.talk("razor","tough","reason","revenge") },
      { type: "talk", target: "razor", persona: "formal", topic: "reason", claim: "hiding",  desc: desc.talk("razor","formal","reason","hiding") },
      { type: "move", direction: "south", desc: desc.move("south") },
    ],
    chosen: 1,
    reply: "Razor nods slowly. \"Alright. I'm listening.\"",
    feedback: "Trust +10 (now 40%), Persona correct, Claim consistent",
    effects: { trust: { razor: +10 }, fact: { topic: "reason", target: "razor", value: "money" } },
    agent: { x: 7, y: 2 },
    message: "Persona ✓  •  Trust 40",
    patrol_step: 2, // Diaz to (2,8)
  },
  {
    action: { type: "talk", target: "razor", persona: "tough", topic: "history", claim: "veteran" },
    options: [
      { type: "talk", target: "razor", persona: "tough",  topic: "history", claim: "veteran",   desc: desc.talk("razor","tough","history","veteran") },
      { type: "talk", target: "razor", persona: "tough",  topic: "history", claim: "newcomer",  desc: desc.talk("razor","tough","history","newcomer") },
      { type: "talk", target: "razor", persona: "casual", topic: "history", claim: "returning", desc: desc.talk("razor","casual","history","returning") },
      { type: "talk", target: "razor", persona: "formal", topic: "history", claim: "referred",  desc: desc.talk("razor","formal","history","referred") },
      { type: "move", direction: "south", desc: desc.move("south") },
    ],
    chosen: 1,
    reply: "Razor cracks a thin smile. \"You're growing on me. Keep it up.\"",
    feedback: "Trust +10 (now 50%), Persona correct, Claim consistent",
    effects: { trust: { razor: +10 }, fact: { topic: "history", target: "razor", value: "veteran" } },
    agent: { x: 7, y: 2 },
    message: "Persona ✓  •  Trust 50  •  All topics covered",
    patrol_step: 3, // Diaz to (2,11)
  },

  // ============================================================
  // ACT III — DETOUR via Kid Ravi (consistency build)
  // Need to get Razor over 60 — a consistent claim from another
  // gang member triggers +5 trust. So go talk to Whisper later.
  // First, build cover with civilian Ravi at (13,5).
  // ============================================================
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }, { type: "move", direction: "south", desc: desc.move("south") }, { type: "talk", target: "razor", persona: "tough", topic: "origin", claim: "southside", desc: desc.talk("razor","tough","origin","southside") }], chosen: 1, agent: { x: 8, y: 2 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }, { type: "move", direction: "east", desc: desc.move("east") }], chosen: 1, agent: { x: 8, y: 3 }, patrol_step: 4 },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 8, y: 4 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }, { type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 9, y: 4 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 10, y: 4 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }, { type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 11, y: 4 }, patrol_step: 5 },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }, { type: "move", direction: "east", desc: desc.move("east") }], chosen: 1, agent: { x: 11, y: 5 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 12, y: 5 } },
  {
    action: { type: "talk", target: "ravi", persona: "casual", topic: "origin", claim: "southside" },
    options: [
      { type: "talk", target: "ravi", persona: "casual", topic: "origin", claim: "southside",   desc: desc.talk("ravi","casual","origin","southside") },
      { type: "talk", target: "ravi", persona: "tough",  topic: "origin", claim: "southside",   desc: desc.talk("ravi","tough","origin","southside") },
      { type: "talk", target: "ravi", persona: "casual", topic: "origin", claim: "downtown",    desc: desc.talk("ravi","casual","origin","downtown") },
      { type: "talk", target: "ravi", persona: "casual", topic: "origin", claim: "out_of_town", desc: desc.talk("ravi","casual","origin","out_of_town") },
      { type: "move", direction: "west", desc: desc.move("west") },
    ],
    chosen: 1,
    reply: "Kid Ravi nods slowly. \"Alright. I'm listening.\"",
    feedback: "Trust +10 (now 10%), Persona correct, Claim consistent",
    effects: { trust: { ravi: +10 }, fact: { topic: "origin", target: "ravi", value: "southside" } },
    agent: { x: 12, y: 5 },
    message: "Civilian rapport ✓  •  origin claim consistent",
    patrol_step: 0, // patrol cycles back
  },

  // ============================================================
  // ACT IV — TO WHISPER (gang #2 in south)
  // Use Whisper for cross-gang consistency boost on Razor's record
  // ============================================================
  { action: { type: "move", direction: "west" },  options: [{ type: "move", direction: "west", desc: desc.move("west") }], chosen: 1, agent: { x: 11, y: 5 } },
  { action: { type: "move", direction: "west" },  options: [{ type: "move", direction: "west", desc: desc.move("west") }], chosen: 1, agent: { x: 10, y: 5 } },
  { action: { type: "move", direction: "west" },  options: [{ type: "move", direction: "west", desc: desc.move("west") }], chosen: 1, agent: { x: 9, y: 5 } },
  { action: { type: "move", direction: "west" },  options: [{ type: "move", direction: "west", desc: desc.move("west") }], chosen: 1, agent: { x: 8, y: 5 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 8, y: 6 }, patrol_step: 1 },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 8, y: 7 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 8, y: 8 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 8, y: 9 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 8, y: 10 }, patrol_step: 2 },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 8, y: 11 } },
  { action: { type: "move", direction: "west" },  options: [{ type: "move", direction: "west", desc: desc.move("west") }], chosen: 1, agent: { x: 7, y: 11 } },
  // Whisper is at (7,11). Adjacent? actually we're standing on him... talk works at adjacent, dist <= 1, so same cell ok
  {
    action: { type: "talk", target: "whisper", persona: "tough", topic: "origin", claim: "southside" },
    options: [
      { type: "talk", target: "whisper", persona: "tough",  topic: "origin", claim: "southside",   desc: desc.talk("whisper","tough","origin","southside") },
      { type: "talk", target: "whisper", persona: "tough",  topic: "origin", claim: "downtown",    desc: desc.talk("whisper","tough","origin","downtown") },
      { type: "talk", target: "whisper", persona: "casual", topic: "origin", claim: "southside",   desc: desc.talk("whisper","casual","origin","southside") },
      { type: "talk", target: "whisper", persona: "formal", topic: "origin", claim: "out_of_town", desc: desc.talk("whisper","formal","origin","out_of_town") },
      { type: "move", direction: "north", desc: desc.move("north") },
    ],
    chosen: 1,
    reply: "Whisper looks you over. \"You talk the talk. We'll see if you walk it.\"",
    feedback: "Trust +10 (now 10%), Persona correct, Claim consistent",
    effects: { trust: { whisper: +10 }, fact: { topic: "origin", target: "whisper", value: "southside" } },
    agent: { x: 7, y: 11 },
    message: "Whisper persona ✓  •  same origin as Razor",
    patrol_step: 3,
  },
  {
    action: { type: "talk", target: "whisper", persona: "tough", topic: "boss", claim: "solo" },
    options: [
      { type: "talk", target: "whisper", persona: "tough",  topic: "boss", claim: "solo",            desc: desc.talk("whisper","tough","boss","solo") },
      { type: "talk", target: "whisper", persona: "tough",  topic: "boss", claim: "works_for_razor", desc: desc.talk("whisper","tough","boss","works_for_razor") },
      { type: "talk", target: "whisper", persona: "tough",  topic: "boss", claim: "works_for_vince", desc: desc.talk("whisper","tough","boss","works_for_vince") },
      { type: "talk", target: "whisper", persona: "casual", topic: "boss", claim: "independent",     desc: desc.talk("whisper","casual","boss","independent") },
      { type: "move", direction: "north", desc: desc.move("north") },
    ],
    chosen: 1,
    // Same-faction match → +5 bonus per env code
    reply: "Whisper nods with respect. \"Consistent. That matters around here.\"",
    feedback: "Trust +15 (now 25%), Persona correct, Claim consistent (matched Razor)",
    effects: { trust: { whisper: +15 }, fact: { topic: "boss", target: "whisper", value: "solo" } },
    agent: { x: 7, y: 11 },
    message: "Cross-gang match  •  +5 consistency bonus",
    patrol_step: 4,
  },

  // ============================================================
  // ACT V — BACK TO RAZOR FOR CONSISTENCY BOOST
  // ============================================================
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 10 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 9 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 8 }, patrol_step: 5 },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 7 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 6 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 5 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 4 }, patrol_step: 0 },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 3 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 7, y: 2 } },
  {
    action: { type: "talk", target: "razor", persona: "tough", topic: "boss", claim: "solo" },
    options: [
      { type: "talk", target: "razor", persona: "tough",  topic: "boss", claim: "solo",            desc: desc.talk("razor","tough","boss","solo") },
      { type: "talk", target: "razor", persona: "tough",  topic: "boss", claim: "works_for_razor", desc: desc.talk("razor","tough","boss","works_for_razor") },
      { type: "talk", target: "razor", persona: "casual", topic: "boss", claim: "solo",            desc: desc.talk("razor","casual","boss","solo") },
      { type: "move", direction: "south", desc: desc.move("south") },
    ],
    chosen: 1,
    reply: "Razor nods with respect. \"Consistent. That matters around here.\"",
    feedback: "Trust +15 (now 65%), Persona correct, Claim consistent (matched Whisper)",
    effects: { trust: { razor: +15 }, fact: { topic: "boss", target: "razor", value: "solo" } },
    agent: { x: 7, y: 2 },
    message: "Trust 65 — past 60 threshold  •  WAREHOUSE UNLOCKED",
    patrol_step: 1,
  },

  // ============================================================
  // ACT VI — TO WAREHOUSE (6,9)
  // ============================================================
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 7, y: 3 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 7, y: 4 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 7, y: 5 }, patrol_step: 2 },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 7, y: 6 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 7, y: 7 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 7, y: 8 } },
  { action: { type: "move", direction: "west" },  options: [{ type: "move", direction: "west",  desc: desc.move("west") }], chosen: 1, agent: { x: 6, y: 8 }, patrol_step: 3 },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 6, y: 9 }, message: "Arrived at warehouse" },

  // ============================================================
  // ACT VII — INTEL HEIST
  // ============================================================
  {
    action: { type: "investigate" },
    options: [
      { type: "investigate", desc: desc.invest() },
      { type: "move", direction: "north", desc: desc.move("north") },
      { type: "move", direction: "west",  desc: desc.move("west") },
      { type: "wait", desc: desc.wait() },
    ],
    chosen: 1,
    feedback: "You slip into the warehouse and find the intel.",
    effects: { intel: true },
    agent: { x: 6, y: 9 },
    message: "INTEL GATHERED",
    patrol_step: 4,
  },

  // ============================================================
  // ACT VIII — RETURN TO HANDLER (13,1)
  // ============================================================
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 6, y: 8 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 6, y: 7 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 6, y: 6 }, patrol_step: 5 },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 6, y: 5 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 7, y: 5 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 8, y: 5 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 8, y: 4 }, patrol_step: 0 },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 8, y: 3 } },
  { action: { type: "move", direction: "north" }, options: [{ type: "move", direction: "north", desc: desc.move("north") }], chosen: 1, agent: { x: 8, y: 2 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 9, y: 2 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 10, y: 2 }, patrol_step: 1 },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 11, y: 2 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 12, y: 2 } },
  { action: { type: "move", direction: "east" },  options: [{ type: "move", direction: "east",  desc: desc.move("east") }], chosen: 1, agent: { x: 13, y: 2 } },

  // ============================================================
  // ACT IX — REPORT
  // ============================================================
  {
    action: { type: "report" },
    options: [
      { type: "report", desc: desc.report() },
      { type: "talk", target: "handler", persona: "formal", topic: "boss", claim: "solo", desc: desc.talk("handler","formal","boss","solo") },
      { type: "move", direction: "west", desc: desc.move("west") },
      { type: "wait", desc: desc.wait() },
    ],
    chosen: 1,
    feedback: "You pass the intel to Handler Chen discreetly.",
    effects: { reported: true },
    agent: { x: 13, y: 2 },
    message: "REPORT DELIVERED  •  mission objective complete",
    patrol_step: 2,
  },

  // ============================================================
  // ACT X — EXTRACT
  // ============================================================
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 13, y: 3 } },
  { action: { type: "move", direction: "south" }, options: [{ type: "move", direction: "south", desc: desc.move("south") }], chosen: 1, agent: { x: 13, y: 4 } },
  { action: { type: "move", direction: "west" },  options: [{ type: "move", direction: "west",  desc: desc.move("west") }], chosen: 1, agent: { x: 12, y: 4 }, message: "At safe house" },
  {
    action: { type: "hide" },
    options: [
      { type: "hide", desc: desc.hide("safe_house") },
      { type: "wait", desc: desc.wait() },
      { type: "move", direction: "north", desc: desc.move("north") },
    ],
    chosen: 1,
    feedback: "You lay low in the safe_house. Nearby suspicion eases slightly.",
    agent: { x: 12, y: 4 },
    message: "Lying low",
    final: true,
  },
];

window.EPISODE = EPISODE;
window.INITIAL_NPCS = INITIAL_NPCS;
window.INITIAL_AGENT = INITIAL_AGENT;
