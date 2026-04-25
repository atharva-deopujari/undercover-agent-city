// ===========================================================================
// Main App — orchestrates episode playback, manages state, renders layout
// ===========================================================================

const { useState: useS, useEffect: useE, useRef: useR, useMemo: useM } = React;

// --------------------------------------------------------------------------
// Episode runner — derives full state at any turn index by replaying effects
// --------------------------------------------------------------------------
function deriveStateAt(turnIdx) {
  const npcs = window.INITIAL_NPCS.map(n => ({
    ...n,
    facts_heard: {},
    patrol_step: n.patrol_route ? 0 : undefined,
    suspicion: n.suspicion,
    trust: n.trust,
  }));
  let agent = { ...window.INITIAL_AGENT };
  let intelGathered = false;
  let reportedToHandler = false;
  let coverIntact = true;
  let factDb = {};
  let totalReward = 0;
  let actionLogs = [];
  let history = []; // {turn, npcId, trust, suspicion}
  let lastPersona = null;

  // Initial snapshot
  for (const n of npcs) {
    history.push({ turn: 0, npcId: n.id, trust: n.trust, suspicion: n.suspicion });
  }

  for (let i = 0; i < turnIdx; i++) {
    const t = window.EPISODE[i];
    if (!t) break;
    // Apply effects
    if (t.effects) {
      if (t.effects.trust) {
        for (const [id, d] of Object.entries(t.effects.trust)) {
          const npc = npcs.find(n => n.id === id);
          if (npc) npc.trust = Math.max(0, Math.min(100, npc.trust + d));
        }
      }
      if (t.effects.suspicion) {
        for (const [id, d] of Object.entries(t.effects.suspicion)) {
          const npc = npcs.find(n => n.id === id);
          if (npc) npc.suspicion = Math.max(0, Math.min(100, npc.suspicion + d));
        }
      }
      if (t.effects.fact) {
        const { topic, target, value } = t.effects.fact;
        if (!factDb[topic]) factDb[topic] = {};
        factDb[topic][target] = value;
        const npc = npcs.find(n => n.id === target);
        if (npc) npc.facts_heard[topic] = value;
      }
      if (t.effects.intel) intelGathered = true;
      if (t.effects.reported) reportedToHandler = true;
      if (t.effects.coverBlown) coverIntact = false;
    }
    // Apply agent move
    if (t.agent) agent = { ...t.agent };
    // Apply patrol
    if (t.patrol_step !== undefined) {
      const patrol = npcs.find(n => n.id === "patrol");
      if (patrol && patrol.patrol_route) {
        patrol.patrol_step = t.patrol_step;
        patrol.x = patrol.patrol_route[t.patrol_step][0];
        patrol.y = patrol.patrol_route[t.patrol_step][1];
      }
    }
    // Track persona for status display
    if (t.action.type === "talk" && t.action.persona) {
      lastPersona = t.action.persona;
    }
    // Compute approximate reward (matches rubric ballpark)
    let r = 0;
    if (t.action.type === "talk") {
      const npc = npcs.find(n => n.id === t.action.target);
      if (npc && t.action.persona === npc.expected_persona) r += 0.2;
      if (t.feedback && t.feedback.includes("Trust +15")) r += 0.15;
    }
    if (t.effects?.intel) r += 1.0;
    if (t.effects?.reported) r += 1.5;
    if (t.action.type === "move") r += 0.01;
    totalReward += r;

    // Build summary
    let summary = "";
    if (t.action.type === "move") summary = `move ${t.action.direction}`;
    else if (t.action.type === "talk") {
      const tgt = npcs.find(n => n.id === t.action.target)?.name || t.action.target;
      summary = `${tgt} · ${t.action.persona} · ${t.action.topic}=${t.action.claim}`;
    }
    else if (t.action.type === "investigate") summary = "investigate warehouse";
    else if (t.action.type === "report") summary = "report to handler";
    else if (t.action.type === "hide") summary = "hide";
    else summary = t.action.type;

    actionLogs.push({ turn: i + 1, action: t.action, summary, reward: r, message: t.message });

    // Snapshot for history
    for (const n of npcs) {
      history.push({ turn: i + 1, npcId: n.id, trust: n.trust, suspicion: n.suspicion });
    }
  }

  return { npcs, agent, intelGathered, reportedToHandler, coverIntact, factDb, totalReward, actionLogs, history, lastPersona };
}

// --------------------------------------------------------------------------
// Live mode — connect to a running Python server's WebSocket
// --------------------------------------------------------------------------
function useLiveConnection(enabled, url) {
  const [state, setState] = useS(null);
  const [connected, setConnected] = useS(false);
  const [error, setError] = useS(null);
  useE(() => {
    if (!enabled) { setConnected(false); setState(null); return; }
    let ws; let reconnectTimer;
    function connect() {
      try {
        ws = new WebSocket(url);
        ws.onopen = () => { setConnected(true); setError(null); fetch(url.replace(/^ws/, "http").replace("/ws/ui", "/web/state")).then(r=>r.json()).then(setState).catch(()=>{}); };
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            if (data.type === "state_update") {
              fetch(url.replace(/^ws/, "http").replace("/ws/ui", "/web/state")).then(r=>r.json()).then(setState).catch(()=>{});
            }
          } catch {}
        };
        ws.onerror = () => { setError("connection error"); };
        ws.onclose = () => { setConnected(false); reconnectTimer = setTimeout(connect, 3000); };
      } catch (e) { setError(String(e)); }
    }
    connect();
    return () => { clearTimeout(reconnectTimer); try { ws?.close(); } catch {} };
  }, [enabled, url]);
  return { state, connected, error };
}

// --------------------------------------------------------------------------
// Speech bubble manager — auto-fade after a few seconds
// --------------------------------------------------------------------------
function useSpeechBubbles() {
  const [bubbles, setBubbles] = useS([]);
  function spawn(items) {
    const now = Date.now();
    const newBubbles = items.map((b, i) => ({ ...b, id: `${now}-${i}`, ts: now }));
    setBubbles(newBubbles);
  }
  function clear() { setBubbles([]); }
  return [bubbles, spawn, clear];
}

// --------------------------------------------------------------------------
// Tweaks defaults
// --------------------------------------------------------------------------
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "showCoordinates": true,
  "speechAutoHide": 2400,
  "showFog": false,
  "accentHue": 38,
  "compactPanels": false
}/*EDITMODE-END*/;

// --------------------------------------------------------------------------
// Main App
// --------------------------------------------------------------------------
function App() {
  const [tweaks, setTweaks] = window.useTweaks
    ? window.useTweaks(TWEAK_DEFAULTS)
    : [TWEAK_DEFAULTS, () => {}];

  const [turnIdx, setTurnIdx] = useS(0);
  const [playing, setPlaying] = useS(false);
  const [speed, setSpeed] = useS(0.25);
  const [autoPauseOnTalk, setAutoPauseOnTalk] = useS(true);
  const [transcript, setTranscript] = useS([]); // [{turn, speaker, line, kind}]
  const [focusNpc, setFocusNpc] = useS(null);
  const [chartMode, setChartMode] = useS("trust"); // "trust" or "suspicion"
  const [mode, setMode] = useS("demo");
  const [leftOpen, setLeftOpen] = useS(true);
  const [rightOpen, setRightOpen] = useS(true);


  // Live mode (only attempts if user toggles)
  const liveUrl = `${window.location.protocol === "https:" ? "wss" : "ws"}://localhost:8000/ws/ui`;
  const { state: liveState, connected: liveConnected } = useLiveConnection(mode === "live", liveUrl);

  // Derive the world state for the current turn
  const derived = useM(() => {
    if (mode === "live" && liveState) {
      // Map server state to our shape
      const npcs = (liveState.npcs || []).map(n => ({
        id: n.id, name: n.name, faction: n.faction,
        x: n.x, y: n.y,
        trust: n.trust, suspicion: n.suspicion,
        expected_persona: n.expected_persona || "casual",
        has_intel: n.has_intel,
        trust_threshold: n.trust_threshold ?? 999,
        facts_heard: n.facts_heard || {},
      }));
      return {
        npcs,
        agent: { x: liveState.agent_x, y: liveState.agent_y },
        intelGathered: liveState.intel_gathered,
        reportedToHandler: liveState.reported_to_handler,
        coverIntact: liveState.cover_intact,
        factDb: liveState.fact_db || {},
        totalReward: liveState.total_reward || 0,
        actionLogs: (liveState.action_logs || []).map((l, i) => ({
          turn: l.step_count || i + 1,
          action: l.action || {},
          summary: JSON.stringify(l.action || {}),
          reward: l.reward,
          message: "",
        })),
        history: [],
        lastPersona: null,
      };
    }
    return deriveStateAt(turnIdx);
  }, [turnIdx, mode, liveState]);

  // Current turn data (for action deck + bubble triggers)
  const currentTurnData = mode === "demo" && turnIdx > 0 ? window.EPISODE[turnIdx - 1] : null;
  const upcomingTurnData = mode === "demo" ? window.EPISODE[turnIdx] : null;

  // Rebuild conversation transcript whenever turnIdx changes in demo mode.
  // Transcript covers all turns 1..turnIdx.
  useE(() => {
    if (mode !== "demo") { setTranscript([]); return; }
    const out = [];
    for (let i = 0; i < turnIdx; i++) {
      const t = window.EPISODE[i];
      if (!t) continue;
      const turnNum = i + 1;
      if (t.action.type === "talk") {
        out.push({
          turn: turnNum, kind: "talk",
          speaker: "agent",
          targetId: t.action.target,
          persona: t.action.persona,
          topic: t.action.topic,
          line: t.action.claim,
        });
        if (t.reply) {
          out.push({
            turn: turnNum, kind: "reply",
            speaker: t.action.target,
            line: t.reply,
          });
        }
      } else if (t.action.type === "report") {
        out.push({ turn: turnNum, kind: "report", speaker: "agent", line: "[REPORT TO HANDLER]", topic: t.action.topic });
        if (t.feedback) out.push({ turn: turnNum, kind: "report-reply", speaker: "handler", line: t.feedback });
      } else if (t.action.type === "investigate" && t.feedback) {
        out.push({ turn: turnNum, kind: "investigate", speaker: "agent", line: t.feedback });
      } else if (t.action.type === "hide" && t.feedback) {
        out.push({ turn: turnNum, kind: "hide", speaker: "agent", line: t.feedback });
      }
      // movement turns are intentionally omitted — the transcript is for dialogue
    }
    setTranscript(out);
  }, [turnIdx, mode]);

  // Active speaker on the CURRENT turn (for spotlight)
  const activeSpeakerId = useM(() => {
    const t = currentTurnData;
    if (!t) return null;
    if (t.action.type === "talk") return t.action.target;     // npc replied last; spotlight them
    if (t.action.type === "report") return "handler";
    return "agent";
  }, [currentTurnData]);

  // Bubbles to show on the current turn — agent line + npc reply for talks.
  // Each bubble has {x, y, side, text, speakerId} so the renderer can stack
  // them above the right entity without overlap.
  const currentBubbles = useM(() => {
    const t = currentTurnData;
    if (!t) return [];
    const out = [];
    if (t.action.type === "talk") {
      const npc = derived.npcs.find(n => n.id === t.action.target);
      if (derived.agent) {
        out.push({
          x: derived.agent.x, y: derived.agent.y,
          side: "agent",
          speakerId: "agent",
          text: t.action.claim || "",
        });
      }
      if (npc && t.reply) {
        out.push({
          x: npc.x, y: npc.y,
          side: "npc",
          speakerId: npc.id,
          text: t.reply,
        });
      }
    }
    return out;
  }, [currentTurnData, derived.agent, derived.npcs]);

  // Auto-pause after a talk turn so user can read what was said
  useE(() => {
    if (!autoPauseOnTalk) return;
    if (mode !== "demo") return;
    const t = currentTurnData;
    if (!t) return;
    if (playing && (t.action.type === "talk" || t.action.type === "report")) {
      setPlaying(false);
    }
  }, [turnIdx]);

  // Auto-play
  useE(() => {
    if (!playing || mode !== "demo") return;
    if (turnIdx >= window.EPISODE.length) { setPlaying(false); return; }
    // Base 2200ms — at 0.5× → 4.4s/turn (readable), 1× → 2.2s, 2× → 1.1s
    const ms = 2200 / speed;
    const id = setTimeout(() => setTurnIdx(t => t + 1), ms);
    return () => clearTimeout(id);
  }, [playing, turnIdx, speed, mode]);

  const focused = focusNpc ? derived.npcs.find(n => n.id === focusNpc) : null;
  const totalTurns = window.EPISODE.length;

  return (
    <div className="app" data-compact={tweaks.compactPanels}>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◆</span>
          <span className="brand-name mono">UNDERCOVER CITY</span>
          <span className="brand-sub mono dim small">spectator · v1.0</span>
        </div>
        <window.StatusBar
          turn={turnIdx}
          maxTurns={totalTurns}
          coverIntact={derived.coverIntact}
          intelGathered={derived.intelGathered}
          reportedToHandler={derived.reportedToHandler}
          currentTask="full_job"
          persona={derived.lastPersona}
          totalReward={derived.totalReward}
          mode={mode}
          onModeChange={setMode}
          connected={liveConnected}
        />
      </header>

      <main className="layout">
        {/* LEFT: action deck */}
        <aside className={`col col-l ${leftOpen ? "" : "collapsed"}`}>
          <window.ActionDeck
            options={(currentTurnData || upcomingTurnData)?.options || []}
            chosen={currentTurnData?.chosen || 0}
            executing={playing}
          />
          <window.FactTracker factDb={derived.factDb} npcs={derived.npcs} />
        </aside>
        <button className={`col-toggle col-toggle-l ${leftOpen ? "open" : ""}`} onClick={() => setLeftOpen(o => !o)} title={leftOpen ? "Collapse left panel" : "Expand left panel"}>
          {leftOpen ? "‹" : "›"}
        </button>

        {/* CENTER: city map */}
        <section className="col col-c">
          <window.CityGrid
            agent={derived.agent}
            npcs={derived.npcs}
            activeSpeakerId={activeSpeakerId}
            bubbles={currentBubbles}
            focusNpc={focusNpc}
            onSelectNpc={setFocusNpc}
            coverBlown={!derived.coverIntact}
            intelGathered={derived.intelGathered}
            reportedToHandler={derived.reportedToHandler}
          />
          <PlaybackControls
            turnIdx={turnIdx}
            totalTurns={totalTurns}
            playing={playing}
            speed={speed}
            onPlay={() => setPlaying(p => !p)}
            onStep={(d) => setTurnIdx(t => Math.max(0, Math.min(totalTurns, t + d)))}
            onScrub={(v) => { setPlaying(false); setTurnIdx(v); }}
            onReset={() => { setPlaying(false); setTurnIdx(0); }}
            onSpeed={setSpeed}
            currentMessage={currentTurnData?.message}
            disabled={mode === "live"}
          />
        </section>

        {/* RIGHT: charts + dossier + log */}
        <aside className={`col col-r ${rightOpen ? "" : "collapsed"}`}>
          <window.ConversationTranscript entries={transcript} npcs={derived.npcs} currentTurn={turnIdx} />
          <window.MeterList title="TRUST" npcs={derived.npcs} kind="trust" />
          <window.MeterList title="SUSPICION" npcs={derived.npcs} kind="suspicion" threshold={80} />
          <div className="chart-tabs">
            <button className={chartMode === "trust" ? "active" : ""} onClick={() => setChartMode("trust")}>TRUST CHART</button>
            <button className={chartMode === "suspicion" ? "active" : ""} onClick={() => setChartMode("suspicion")}>SUSPICION CHART</button>
          </div>
          <window.TrustHistoryChart history={derived.history} npcs={derived.npcs} kind={chartMode} />
          <window.NpcInspector npc={focused} history={derived.history} factDb={derived.factDb} agentClaims={{}} onClose={() => setFocusNpc(null)} />
          <window.ActionLog logs={derived.actionLogs} />
        </aside>
        <button className={`col-toggle col-toggle-r ${rightOpen ? "open" : ""}`} onClick={() => setRightOpen(o => !o)} title={rightOpen ? "Collapse right panel" : "Expand right panel"}>
          {rightOpen ? "›" : "‹"}
        </button>
      </main>

      {!derived.coverIntact && <CoverBlownOverlay />}
    </div>
  );
}

// --------------------------------------------------------------------------
// Playback controls
// --------------------------------------------------------------------------
function PlaybackControls({ turnIdx, totalTurns, playing, speed, onPlay, onStep, onScrub, onReset, onSpeed, currentMessage, disabled }) {
  return (
    <div className="playback">
      <div className="playback-row">
        <button className="pb-btn" onClick={onReset} disabled={disabled} title="Reset">⟲</button>
        <button className="pb-btn" onClick={() => onStep(-1)} disabled={disabled || turnIdx <= 0} title="Step back">‹</button>
        <button className="pb-btn pb-play" onClick={onPlay} disabled={disabled || turnIdx >= totalTurns}>
          {playing ? "❚❚ PAUSE" : "▶ PLAY"}
        </button>
        <button className="pb-btn" onClick={() => onStep(1)} disabled={disabled || turnIdx >= totalTurns} title="Step forward">›</button>
        <div className="speed-group">
          <span className="dim mono small">SPEED</span>
          {[0.25, 0.5, 1, 2, 4].map(s => (
            <button key={s} className={`speed-btn ${speed === s ? "active" : ""}`} onClick={() => onSpeed(s)} disabled={disabled}>
              {s}×
            </button>
          ))}
        </div>
      </div>
      <div className="scrub-row">
        <span className="mono small dim">T{turnIdx.toString().padStart(2,"0")}</span>
        <input
          type="range"
          min="0" max={totalTurns} step="1"
          value={turnIdx}
          onChange={(e) => onScrub(parseInt(e.target.value))}
          disabled={disabled}
          className="scrub"
        />
        <span className="mono small dim">T{totalTurns}</span>
      </div>
      {currentMessage && (
        <div className="now-row mono small">
          <span className="now-tag">→</span> {currentMessage}
        </div>
      )}
      {disabled && (
        <div className="dim small mono center">— LIVE MODE: playback disabled, mirroring server state —</div>
      )}
    </div>
  );
}

function CoverBlownOverlay() {
  return (
    <div className="cover-blown-overlay">
      <div className="cb-pulse" />
      <div className="cb-text">
        <div className="cb-line-1">▲ COVER BLOWN ▲</div>
        <div className="cb-line-2 mono small">Suspicion ≥ 80 · Episode terminated</div>
      </div>
    </div>
  );
}

// Mount
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
