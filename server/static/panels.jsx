// ===========================================================================
// Side panels — Status, Action Deck, NPC Inspector, Trust/Suspicion Charts,
// Action Log, Fact Tracker.
// All data shown here corresponds to fields produced by the Python backend.
// ===========================================================================

const { useState: useState2, useMemo: useMemo2, useEffect: useEffect2, useRef: useRef2 } = React;

// ---------------------------------------------------------------------------
// Status pill — turn / cover / mission progress
// ---------------------------------------------------------------------------
function StatusBar({ turn, maxTurns, coverIntact, intelGathered, reportedToHandler, currentTask, persona, totalReward, mode, onModeChange, connected }) {
  return (
    <div className="status-bar">
      <div className="status-cell">
        <div className="status-label">MISSION</div>
        <div className="status-value mono">{currentTask}</div>
      </div>
      <div className="status-cell">
        <div className="status-label">TURN</div>
        <div className="status-value mono">{turn.toString().padStart(2,"0")} <span className="dim">/ {maxTurns}</span></div>
      </div>
      <div className="status-cell">
        <div className="status-label">COVER</div>
        <div className={`status-value mono ${coverIntact ? "ok" : "bad"}`}>{coverIntact ? "INTACT" : "BLOWN"}</div>
      </div>
      <div className="status-cell">
        <div className="status-label">PERSONA</div>
        <div className={`status-value mono persona-${persona || "none"}`}>{(persona || "—").toUpperCase()}</div>
      </div>
      <div className="status-cell">
        <div className="status-label">INTEL</div>
        <div className={`status-value mono ${intelGathered ? "ok" : "dim"}`}>{intelGathered ? "✓ GATHERED" : "PENDING"}</div>
      </div>
      <div className="status-cell">
        <div className="status-label">REPORT</div>
        <div className={`status-value mono ${reportedToHandler ? "ok" : "dim"}`}>{reportedToHandler ? "✓ DELIVERED" : "PENDING"}</div>
      </div>
      <div className="status-cell">
        <div className="status-label">REWARD</div>
        <div className="status-value mono">{(totalReward ?? 0).toFixed(2)}</div>
      </div>
      <div className="status-cell" style={{marginLeft:"auto"}}>
        <div className="status-label">MODE</div>
        <div className="mode-toggle">
          <button className={mode === "demo" ? "active" : ""} onClick={() => onModeChange("demo")}>DEMO</button>
          <button className={mode === "live" ? "active" : ""} onClick={() => onModeChange("live")}>LIVE {connected && mode==="live" ? "●" : ""}</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Action deck — list of available actions, with the chosen one highlighted
// ---------------------------------------------------------------------------
function ActionDeck({ options, chosen, executing }) {
  if (!options || options.length === 0) return (
    <div className="panel">
      <div className="panel-header">AVAILABLE ACTIONS</div>
      <div className="panel-body dim small">Awaiting policy step…</div>
    </div>
  );
  return (
    <div className="panel">
      <div className="panel-header">
        <span>AVAILABLE ACTIONS</span>
        <span className="mono dim small">{options.length} option{options.length===1?"":"s"}</span>
      </div>
      <div className="panel-body action-list">
        {options.map((opt, i) => {
          const idx = i + 1;
          const isChosen = idx === chosen;
          return (
            <div key={i} className={`action-row ${isChosen ? "chosen" : ""} ${executing && isChosen ? "executing" : ""}`}>
              <div className="action-num mono">{idx}</div>
              <div className="action-type-tag" data-type={opt.type}>{opt.type}</div>
              <div className="action-desc mono small">{opt.desc}</div>
              {isChosen && <div className="action-mark mono">▶ CHOSEN</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Action log (recent actions ticker, mirrors action_logs from backend)
// ---------------------------------------------------------------------------
function ActionLog({ logs }) {
  return (
    <div className="panel action-log-panel-react">
      <div className="panel-header">
        <span>ACTION LOG</span>
        <span className="mono dim small">{logs.length}</span>
      </div>
      <div className="panel-body log-body">
        {logs.length === 0 && <div className="dim small">No actions yet.</div>}
        {[...logs].reverse().slice(0, 40).map((l, i) => (
          <div key={l.turn + "-" + i} className="log-row">
            <span className="mono dim small log-turn">T{l.turn.toString().padStart(2,"0")}</span>
            <span className={`action-type-tag inline`} data-type={l.action.type}>{l.action.type}</span>
            <span className="mono small log-action">{l.summary}</span>
            {l.reward != null && (
              <span className={`mono small log-reward ${l.reward > 0 ? "ok" : l.reward < 0 ? "bad" : "dim"}`}>
                {l.reward >= 0 ? "+" : ""}{l.reward.toFixed(2)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NPC inspector — click an NPC for a deep dive
// ---------------------------------------------------------------------------
function NpcInspector({ npc, history, factDb, agentClaims, onClose }) {
  if (!npc) {
    return (
      <div className="panel">
        <div className="panel-header">DOSSIER</div>
        <div className="panel-body dim small">Click an NPC on the map to inspect.</div>
      </div>
    );
  }
  const trustHist = history.filter(h => h.npcId === npc.id).map(h => h.trust);
  const suspHist = history.filter(h => h.npcId === npc.id).map(h => h.suspicion);

  // What this NPC has been told (from facts_heard equivalent)
  const heard = Object.entries(npc.facts_heard || {});

  return (
    <div className="panel">
      <div className="panel-header">
        <span>DOSSIER · {npc.name.toUpperCase()}</span>
        <button className="close-x" onClick={onClose}>×</button>
      </div>
      <div className="panel-body">
        <div className="dossier-grid">
          <div className="d-cell"><div className="d-k">FACTION</div><div className={`d-v faction-${npc.faction}`}>{npc.faction.toUpperCase()}</div></div>
          <div className="d-cell"><div className="d-k">EXPECTS</div><div className={`d-v persona-${npc.expected_persona}`}>{npc.expected_persona.toUpperCase()}</div></div>
          <div className="d-cell"><div className="d-k">POSITION</div><div className="d-v mono">({npc.x},{npc.y})</div></div>
          <div className="d-cell"><div className="d-k">TRUST</div><div className="d-v mono ok">{npc.trust}%</div></div>
          <div className="d-cell"><div className="d-k">SUSPICION</div><div className={`d-v mono ${npc.suspicion > 50 ? "bad" : "dim"}`}>{npc.suspicion}%</div></div>
          <div className="d-cell"><div className="d-k">THRESHOLD</div><div className="d-v mono">{npc.trust_threshold === 999 ? "—" : npc.trust_threshold + "%"}</div></div>
        </div>

        <div className="d-section-title">CLAIMS HEARD FROM AGENT</div>
        {heard.length === 0 ? (
          <div className="dim small mono">— Has heard nothing —</div>
        ) : (
          <table className="d-table">
            <thead><tr><th>TOPIC</th><th>CLAIM</th></tr></thead>
            <tbody>
              {heard.map(([topic, val]) => (
                <tr key={topic}>
                  <td className="mono dim">{topic}</td>
                  <td className="mono">{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {trustHist.length > 0 && (
          <>
            <div className="d-section-title">TRUST OVER TIME</div>
            <Sparkline values={trustHist} max={100} color="#3acc78" />
            <div className="d-section-title">SUSPICION OVER TIME</div>
            <Sparkline values={suspHist} max={100} color="#ff4040" threshold={80} />
          </>
        )}
      </div>
    </div>
  );
}

function Sparkline({ values, max, color, threshold }) {
  const W = 240, H = 56, P = 4;
  if (values.length === 0) return <div className="dim small">no data</div>;
  const step = (W - P*2) / Math.max(values.length - 1, 1);
  const pts = values.map((v, i) => `${P + i*step},${H - P - (v/max)*(H - P*2)}`).join(" ");
  return (
    <svg width={W} height={H} className="sparkline">
      <rect x="0" y="0" width={W} height={H} fill="#0a0e18" stroke="#1a2238" />
      {threshold && (
        <line
          x1={P} x2={W-P}
          y1={H - P - (threshold/max)*(H - P*2)} y2={H - P - (threshold/max)*(H - P*2)}
          stroke="#ff4040" strokeDasharray="3,2" strokeWidth="0.8" opacity="0.6"
        />
      )}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" />
      {values.map((v, i) => (
        <circle key={i} cx={P + i*step} cy={H - P - (v/max)*(H - P*2)} r="1.5" fill={color} />
      ))}
      <text x={W-P-2} y={H-P-2} fontSize="9" fill={color} textAnchor="end" fontFamily="JetBrains Mono, monospace">
        {values[values.length-1]}%
      </text>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Trust & Suspicion bar lists — quick-glance for all NPCs
// ---------------------------------------------------------------------------
function MeterList({ title, npcs, kind, threshold }) {
  return (
    <div className="panel">
      <div className="panel-header">{title}</div>
      <div className="panel-body meter-body">
        {npcs.map(n => {
          const v = n[kind];
          const color = kind === "trust" ? "#3acc78" : "#ff4040";
          const danger = kind === "suspicion" && v >= 60;
          return (
            <div key={n.id} className="meter-row">
              <div className={`meter-label faction-${n.faction}`}>
                <span className="mono small">{n.name}</span>
              </div>
              <div className={`meter ${danger ? "meter-danger" : ""}`}>
                <div className="meter-fill" style={{ width: `${v}%`, background: color }} />
                {threshold && (
                  <div className="meter-threshold" style={{ left: `${threshold}%` }} />
                )}
                {kind === "trust" && n.trust_threshold !== 999 && n.trust_threshold > 0 && (
                  <div className="meter-threshold" style={{ left: `${n.trust_threshold}%` }} title={`Threshold ${n.trust_threshold}`} />
                )}
              </div>
              <div className="meter-num mono small">{v.toString().padStart(2,"0")}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fact tracker (mirrors fact_db from backend)
// ---------------------------------------------------------------------------
function FactTracker({ factDb, npcs }) {
  const topics = ["origin", "job", "boss", "reason", "history"];
  const npcMap = Object.fromEntries(npcs.map(n => [n.id, n]));
  return (
    <div className="panel">
      <div className="panel-header">FACT TRACKER</div>
      <div className="panel-body">
        <table className="d-table">
          <thead><tr><th>TOPIC</th><th>CLAIM</th><th>TOLD TO</th><th>STATUS</th></tr></thead>
          <tbody>
            {topics.map(t => {
              const claims = factDb[t] || {};
              const entries = Object.entries(claims);
              if (entries.length === 0) {
                return (
                  <tr key={t}>
                    <td className="mono dim">{t}</td>
                    <td className="mono dim">—</td>
                    <td className="mono dim">—</td>
                    <td className="mono dim">—</td>
                  </tr>
                );
              }
              const values = [...new Set(entries.map(([,v]) => v))];
              const consistent = values.length <= 1;
              const toldTo = entries.map(([id]) => npcMap[id]?.name || id).join(", ");
              return (
                <tr key={t}>
                  <td className="mono dim">{t}</td>
                  <td className="mono">{values.join(" / ")}</td>
                  <td className="mono small">{toldTo}</td>
                  <td className={`mono small ${consistent ? "ok" : "bad"}`}>{consistent ? "OK" : "CONFLICT"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trust history line chart — all NPCs in one chart
// ---------------------------------------------------------------------------
function TrustHistoryChart({ history, npcs, kind = "trust" }) {
  const W = 380, H = 130, P = 22;
  const turns = [...new Set(history.map(h => h.turn))].sort((a,b) => a - b);
  const maxTurn = Math.max(turns[turns.length-1] || 1, 5);
  const factionColor = { gang: "#ff5959", police: "#5b8cff", civilian: "#cdd2dd" };
  // for each npc, compute series
  const series = npcs.map(n => {
    const points = history.filter(h => h.npcId === n.id);
    return { id: n.id, name: n.name, faction: n.faction, points };
  }).filter(s => s.points.length > 0);

  return (
    <div className="panel">
      <div className="panel-header">{kind === "trust" ? "TRUST" : "SUSPICION"} OVER TIME</div>
      <div className="panel-body">
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="trust-chart">
          {/* axes */}
          <line x1={P} x2={W-4} y1={H-P} y2={H-P} stroke="#1a2238" strokeWidth="1" />
          <line x1={P} x2={P}   y1={4}    y2={H-P} stroke="#1a2238" strokeWidth="1" />
          {/* gridlines at 25/50/75/100 */}
          {[25,50,75,100].map(g => (
            <g key={g}>
              <line
                x1={P} x2={W-4}
                y1={H - P - (g/100)*(H - P - 4)} y2={H - P - (g/100)*(H - P - 4)}
                stroke="#1a2238" strokeDasharray="2,3" strokeWidth="0.5"
              />
              <text x={P-3} y={H - P - (g/100)*(H - P - 4) + 3} fontSize="8" fill="#5a6478" textAnchor="end" fontFamily="JetBrains Mono, monospace">{g}</text>
            </g>
          ))}
          {kind === "suspicion" && (
            <line
              x1={P} x2={W-4}
              y1={H - P - 0.8*(H - P - 4)} y2={H - P - 0.8*(H - P - 4)}
              stroke="#ff4040" strokeWidth="1" strokeDasharray="3,3" opacity="0.6"
            />
          )}
          {/* x-axis turn markers */}
          <text x={P} y={H-6} fontSize="8" fill="#5a6478" fontFamily="JetBrains Mono, monospace">T0</text>
          <text x={W-4} y={H-6} fontSize="8" fill="#5a6478" textAnchor="end" fontFamily="JetBrains Mono, monospace">T{maxTurn}</text>

          {/* series */}
          {series.map(s => {
            const pts = s.points.map(p => {
              const x = P + (p.turn / Math.max(maxTurn,1)) * (W - P - 4);
              const y = H - P - (p[kind] / 100) * (H - P - 4);
              return `${x},${y}`;
            }).join(" ");
            const color = factionColor[s.faction];
            return (
              <g key={s.id}>
                <polyline points={pts} fill="none" stroke={color} strokeWidth="1.4" opacity="0.9" />
                {/* end-point label */}
                {s.points.length > 0 && (() => {
                  const lp = s.points[s.points.length-1];
                  const x = P + (lp.turn / Math.max(maxTurn,1)) * (W - P - 4);
                  const y = H - P - (lp[kind] / 100) * (H - P - 4);
                  return (
                    <g>
                      <circle cx={x} cy={y} r="2" fill={color} />
                      <text x={x+4} y={y+3} fontSize="8" fill={color} fontFamily="JetBrains Mono, monospace">{s.name}</text>
                    </g>
                  );
                })()}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

window.StatusBar = StatusBar;
window.ActionDeck = ActionDeck;
window.ActionLog = ActionLog;
window.NpcInspector = NpcInspector;
window.MeterList = MeterList;
window.FactTracker = FactTracker;
window.TrustHistoryChart = TrustHistoryChart;

// ---------------------------------------------------------------------------
// Conversation Transcript — chat-style log of what was said this episode.
// Each turn that was a `talk` produces 2 lines: the agent's structured claim
// and the NPC's reply. `report` produces handler exchange. Pure movements
// are skipped. Auto-scrolls to bottom on update.
// ---------------------------------------------------------------------------
function ConversationTranscript({ entries, npcs, currentTurn }) {
  const scrollRef = useRef2(null);
  useEffect2(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries.length]);

  const nameOf = (id) => {
    if (id === "agent") return "AGENT";
    if (id === "handler") return "HANDLER";
    const n = npcs.find(x => x.id === id);
    return n ? n.name.toUpperCase() : id?.toUpperCase?.() || "?";
  };
  const colorOf = (id) => {
    if (id === "agent") return "#ffc14a";
    if (id === "handler") return "#5b8cff";
    const n = npcs.find(x => x.id === id);
    if (!n) return "#cdd2dd";
    return { gang: "#ff5959", police: "#5b8cff", civilian: "#cdd2dd" }[n.faction] || "#cdd2dd";
  };

  return (
    <div className="panel transcript-panel">
      <div className="panel-header">
        <span className="panel-title mono">CONVERSATION</span>
        <span className="panel-sub mono dim small">{entries.length} lines</span>
      </div>
      <div className="transcript-scroll" ref={scrollRef}>
        {entries.length === 0 && (
          <div className="dim small mono center" style={{padding:"12px"}}>— no dialogue yet —</div>
        )}
        {entries.map((e, i) => {
          const c = colorOf(e.speaker);
          const target = e.targetId ? nameOf(e.targetId) : null;
          const isAgentish = e.speaker === "agent";
          return (
            <div key={i} className={`tr-row ${isAgentish ? "tr-right" : "tr-left"}`}>
              <div className="tr-head mono small">
                <span className="tr-turn dim">T{e.turn.toString().padStart(2,"0")}</span>
                <span className="tr-name" style={{color: c}}>{nameOf(e.speaker)}</span>
                {target && <span className="tr-arrow dim">→ {target}</span>}
                {e.persona && <span className="tr-tag" style={{borderColor: c, color: c}}>{e.persona}</span>}
                {e.topic && <span className="tr-topic dim">·{e.topic}</span>}
                {e.kind && <span className="tr-kind dim">{e.kind}</span>}
              </div>
              <div className="tr-bubble" style={{borderColor: c}}>
                {e.line}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

window.ConversationTranscript = ConversationTranscript;
