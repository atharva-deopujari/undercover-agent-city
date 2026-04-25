// ===========================================================================
// Isometric City Scene — proper game-style visualization
// Top-down isometric tiles, building blocks with rooftops, character sprites.
// ===========================================================================
const { useState, useEffect, useRef, useMemo } = React;

// Iso projection: flat tile (x,y,z=0) -> screen (sx, sy)
const TILE_W = 34;   // half-width of a diamond — bigger so characters don't dwarf tiles
const TILE_H = 17;   // half-height of a diamond
function iso(x, y, z = 0) {
  return {
    sx: (x - y) * TILE_W,
    sy: (x + y) * TILE_H - z,
  };
}

// City layout colors
const FACTION_COLOR = { gang: "#ff5959", police: "#5b8cff", civilian: "#cdd2dd", agent: "#ffc14a" };

// Grass-everywhere palette — only roads stay paved. Sidewalks become stone
// pavers laid over grass. Building/special bases sit on grass (the 3D blocks
// cover the tile anyway).
const GRASS_TOP  = "#1f3a22";
const GRASS_TOP2 = "#27462a";
const TERRAIN_FILL = {
  0: { top: "#3d4256", side: "#272a38" },          // road - asphalt
  1: { top: GRASS_TOP, side: "#142516" },          // building base — grass under 3D block
  2: { top: GRASS_TOP, side: "#142516" },          // alley — grass
  3: { top: GRASS_TOP, side: "#142516" },          // shop base — grass
  4: { top: GRASS_TOP2, side: "#142516" },         // park — slightly lighter grass
  5: { top: GRASS_TOP, side: "#142516" },          // hideout base
  6: { top: GRASS_TOP, side: "#142516" },          // police base
  7: { top: GRASS_TOP, side: "#142516" },          // warehouse base
  8: { top: GRASS_TOP, side: "#142516" },          // safe house base
  9: { top: "#27462a", side: "#142516" },          // "sidewalk" — slightly brighter grass strip beside roads
};

// Buildings rise from these tiles (with height in iso z-units)
const BUILDING_HEIGHT = 24;
const SPECIAL_BUILDING = {
  3: { color: "#a37018", roof: "#d4a040", height: 28, label: "SHOP" },
  5: { color: "#7a1a1a", roof: "#c44",   height: 32, label: "HIDE" },
  6: { color: "#1e3680", roof: "#5b8cff",height: 36, label: "POL"  },
  7: { color: "#4a4540", roof: "#9b9690",height: 30, label: "WHSE" },
  8: { color: "#1c5a36", roof: "#3acc78",height: 30, label: "SAFE" },
};

function CityScene({ agent, npcs, focusNpc, onSelectNpc, coverBlown, intelGathered, prevAgent, activeSpeakerId, bubbles }) {
  const W = window.GRID_W;
  const H = window.GRID_H;
  const grid = window.GRID;

  // Compute scene bounds for SVG viewBox
  // The iso projection of (0,0)..(W-1,H-1) gives:
  //   x extent: -(H-1)*TILE_W .. (W-1)*TILE_W
  //   y extent: 0 .. (W-1+H-1)*TILE_H + maxBuildingHeight
  const minX = -(H - 1) * TILE_W - TILE_W - 8;
  const maxX = (W - 1) * TILE_W + TILE_W + 8;
  const minY = -50;
  const maxY = (W + H - 2) * TILE_H + TILE_H + 16;

  // Group cells in painter's order (back to front): smaller (x+y) first
  const renderOrder = useMemo(() => {
    const cells = [];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) cells.push({ x, y });
    cells.sort((a, b) => (a.x + a.y) - (b.x + b.y));
    return cells;
  }, []);

  return (
    <div className="grid-wrap iso-wrap">
      <svg className="city-svg" viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`} preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#0a0e18" />
            <stop offset="1" stopColor="#040608" />
          </linearGradient>
          <radialGradient id="agent-glow" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#ffc14a" stopOpacity="0.6" />
            <stop offset="1" stopColor="#ffc14a" stopOpacity="0" />
          </radialGradient>
          <filter id="ds" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" floodOpacity="0.5" />
          </filter>
        </defs>

        {/* sky/background */}
        <rect x={minX} y={minY} width={maxX-minX} height={maxY-minY} fill="url(#sky)" />

        {/* Ground tiles + buildings, painter's order */}
        {renderOrder.map(({ x, y }) => {
          const t = grid[y * W + x];
          return <Tile key={`t-${x}-${y}`} x={x} y={y} terrain={t} />;
        })}

        {/* Road lane markings (subtle dashes on full road rows/cols) */}
        <RoadMarkings />

        {/* Trees on every empty grass tile (no building) — exclude NPC/agent tiles */}
        {(() => {
          const occupied = new Set();
          if (agent) occupied.add(`${agent.x},${agent.y}`);
          for (const n of (npcs || [])) occupied.add(`${n.x},${n.y}`);
          // Eligible terrains: park (4), alley (2), sidewalk grass band (9)
          // NOT building (1) or specials (3,5,6,7,8) or road (0)
          return renderOrder.filter(c => {
            const t = grid[c.y * W + c.x];
            if (t !== 2 && t !== 4 && t !== 9) return false;
            return !occupied.has(`${c.x},${c.y}`);
          }).map(c => (
            <Tree key={`tree-${c.x}-${c.y}`} x={c.x} y={c.y} />
          ));
        })()}

        {/* Combined entity + building pass, painter's order by depth.
            Each tile may produce a building, entities at that tile, or both.
            Entities sit on top of their own tile but behind buildings further from camera. */}
        {(() => {
          // PASS 1 — buildings only, painter's order
          const items = [];
          for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
              const t = grid[y * W + x];
              const spec = SPECIAL_BUILDING[t];
              if (spec) {
                items.push({ depth: x + y, key: `b-${x}-${y}`, kind: "building", x, y, spec, isSpecial: true });
              } else if (t === 1) {
                items.push({ depth: x + y, key: `gb-${x}-${y}`, kind: "districtBuilding", x, y });
              }
            }
          }
          items.sort((a, b) => a.depth - b.depth);
          return items.map(it => {
            if (it.kind === "building") {
              const t = grid[it.y*W+it.x];
              return <SpecialBuilding
                key={it.key} x={it.x} y={it.y}
                spec={it.spec}
                terrain={t}
                intelGathered={intelGathered}
              />;
            }
            return <DistrictBuilding key={it.key} x={it.x} y={it.y} />;
          });
        })()}

        {/* Active-speaker spotlight beam — drawn AFTER buildings, BEFORE characters
            so it falls on the ground and over building roofs */}
        {(() => {
          const target = activeSpeakerId === "agent"
            ? agent
            : npcs.find(n => n.id === activeSpeakerId);
          if (!target) return null;
          const { sx, sy } = iso(target.x, target.y);
          return (
            <g key={`spot-${activeSpeakerId}`}>
              {/* vertical beam */}
              <defs>
                <linearGradient id="beamGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ffd866" stopOpacity="0" />
                  <stop offset="60%" stopColor="#ffd866" stopOpacity="0.18" />
                  <stop offset="100%" stopColor="#ffd866" stopOpacity="0.45" />
                </linearGradient>
                <radialGradient id="diskGrad" cx="0.5" cy="0.5" r="0.5">
                  <stop offset="0%" stopColor="#ffd866" stopOpacity="0.7" />
                  <stop offset="100%" stopColor="#ffd866" stopOpacity="0" />
                </radialGradient>
              </defs>
              <polygon
                points={`${sx-TILE_W*0.55},${sy-200} ${sx+TILE_W*0.55},${sy-200} ${sx+TILE_W*0.85},${sy} ${sx-TILE_W*0.85},${sy}`}
                fill="url(#beamGrad)"
              />
              {/* ground glow ellipse */}
              <ellipse cx={sx} cy={sy} rx={TILE_W*0.95} ry={TILE_H*0.95} fill="url(#diskGrad)">
                <animate attributeName="rx" values={`${TILE_W*0.85};${TILE_W*1.05};${TILE_W*0.85}`} dur="2s" repeatCount="indefinite" />
                <animate attributeName="ry" values={`${TILE_H*0.85};${TILE_H*1.05};${TILE_H*0.85}`} dur="2s" repeatCount="indefinite" />
              </ellipse>
            </g>
          );
        })()}

        {(() => {
          // PASS 2 — characters in painter's order, drawn ON TOP of all buildings.
          // Each character gets a footplate disk so they're always legible.
          const chars = [];
          chars.push({ depth: agent.x + agent.y, key: "agent", kind: "agent" });
          for (const n of npcs) {
            chars.push({ depth: n.x + n.y, key: `npc-${n.id}`, kind: "npc", npc: n });
          }
          chars.sort((a, b) => a.depth - b.depth);
          return chars.map(it => {
            if (it.kind === "agent") {
              return (
                <g key={it.key}>
                  <Footplate x={agent.x} y={agent.y} color="#ffc14a" active={activeSpeakerId === "agent"} />
                  <AgentSprite x={agent.x} y={agent.y} coverBlown={coverBlown} />
                </g>
              );
            }
            const fc = FACTION_COLOR[it.npc.faction] || "#888";
            return (
              <g key={it.key}>
                <Footplate x={it.npc.x} y={it.npc.y} color={fc} active={activeSpeakerId === it.npc.id} />
                <NpcSprite npc={it.npc} isFocus={focusNpc === it.npc.id} onClick={() => onSelectNpc(it.npc.id)} />
              </g>
            );
          });
        })()}

        {/* Speech bubbles — anti-overlap stacked */}
        {(() => {
          if (!bubbles || bubbles.length === 0) return null;
          // Wrap each bubble's text into lines and compute its box height
          const charW = 5.6;
          const lineH = 11;
          const padX = 8, padY = 6;
          const maxChars = 26;
          const wrap = (txt) => {
            const words = (txt || "").split(" ");
            const out = []; let line = "";
            for (const w of words) {
              if ((line + " " + w).trim().length > maxChars) { out.push(line.trim()); line = w; }
              else { line = (line + " " + w).trim(); }
            }
            if (line) out.push(line);
            return out.length ? out : [""];
          };
          // Compute base anchor (the entity head) for each bubble
          const items = bubbles.map(b => {
            const lines = wrap(b.text);
            const boxW = Math.min(220, Math.max(...lines.map(l => l.length)) * charW + padX * 2);
            const boxH = lines.length * lineH + padY * 2;
            const { sx, sy } = iso(b.x, b.y);
            // depth used for sort: agent above NPC if same tile; otherwise by sy desc (further-down bubbles first)
            return { ...b, lines, boxW, boxH, anchorSx: sx, anchorSy: sy };
          });
          // Sort: render order — paint by decreasing y so higher (smaller sy) bubbles
          // are placed last and end up on top. For stacking we sort by depth.
          // Place each bubble; check against already-placed boxes for overlap; bump up by (boxH + 6) until clear.
          const placed = [];
          for (const it of items) {
            // Initial offset: bubble sits above the head (sy - 36 - boxH)
            let bx = it.anchorSx - it.boxW / 2;
            let by = it.anchorSy - 36 - it.boxH;
            // Check against placed; if overlap, push up
            let safety = 0;
            while (safety++ < 12) {
              let collided = false;
              for (const p of placed) {
                const overlapX = bx < p.bx + p.boxW + 4 && bx + it.boxW + 4 > p.bx;
                const overlapY = by < p.by + p.boxH + 4 && by + it.boxH + 4 > p.by;
                if (overlapX && overlapY) { collided = true; by = p.by - it.boxH - 6; break; }
              }
              if (!collided) break;
            }
            placed.push({ ...it, bx, by });
          }
          return placed.map((p, i) => (
            <SpeechBubble key={`bub-${p.speakerId}-${i}`} placed={p} padX={padX} padY={padY} lineH={lineH} />
          ));
        })()}

        {/* Cover blown overlay */}
        {coverBlown && (
          <rect x={minX} y={minY} width={maxX-minX} height={maxY-minY} fill="#c4202c" opacity="0.18">
            <animate attributeName="opacity" values="0.05;0.28;0.05" dur="0.8s" repeatCount="indefinite" />
          </rect>
        )}
      </svg>
    </div>
  );
}

// --- Tile (ground diamond) ---
function Tile({ x, y, terrain }) {
  const { sx, sy } = iso(x, y);
  const fill = TERRAIN_FILL[terrain] || TERRAIN_FILL[0];
  const points = `${sx},${sy - TILE_H} ${sx + TILE_W},${sy} ${sx},${sy + TILE_H} ${sx - TILE_W},${sy}`;
  // Grass tiles — building base, alley, special bases, parks, sidewalk-band
  // (everything except road) — speckled tufts.
  if (terrain !== 0) {
    const seed = (x * 13 + y * 7) % 6;
    const tufts = [];
    for (let i = 0; i < 5; i++) {
      const s = (seed + i * 5) % 11;
      const ox = ((s * 7) % (TILE_W * 1.3)) - TILE_W * 0.65;
      const oy = ((s * 11) % (TILE_H * 1.1)) - TILE_H * 0.55;
      tufts.push({ ox, oy, c: i % 2 === 0 ? "#2a5a2c" : "#3a7a3a" });
    }
    return (
      <g>
        <polygon points={points} fill={fill.top} stroke="#0a1a0e" strokeWidth="0.5" opacity="0.95" />
        {tufts.map((t, i) => (
          <circle key={i} cx={sx + t.ox} cy={sy + t.oy} r="0.7" fill={t.c} opacity="0.7" />
        ))}
      </g>
    );
  }
  // Road tiles — plain asphalt
  return (
    <g>
      <polygon points={points} fill={fill.top} stroke="#0a0e18" strokeWidth="0.5" opacity="0.95" />
    </g>
  );
}

// --- Plaza overlay: paves over a building-base tile when a character stands on it,
//     so they look like they're standing on a pedestrian alley/courtyard ---
function Plaza({ x, y }) {
  const { sx, sy } = iso(x, y);
  const points = `${sx},${sy - TILE_H} ${sx + TILE_W},${sy} ${sx},${sy + TILE_H} ${sx - TILE_W},${sy}`;
  return null; // deprecated
}

// --- Footplate: glowing disk under each character so they always read
//     clearly even when standing in front of a building ---
function Footplate({ x, y, color, active }) {
  const { sx, sy } = iso(x, y);
  const rx = TILE_W * (active ? 0.7 : 0.55);
  const ry = TILE_H * (active ? 0.7 : 0.55);
  return (
    <g>
      {/* shadow */}
      <ellipse cx={sx + 1.5} cy={sy + 1.5} rx={rx * 0.95} ry={ry * 0.95} fill="#000" opacity="0.35" />
      {/* main disk */}
      <ellipse cx={sx} cy={sy} rx={rx} ry={ry} fill="#0e1322" stroke={color} strokeWidth={active ? 1.4 : 0.9} opacity="0.9" />
      {/* inner highlight */}
      <ellipse cx={sx} cy={sy - 0.4} rx={rx * 0.7} ry={ry * 0.7} fill={color} opacity={active ? 0.18 : 0.08} />
      {active && (
        <ellipse cx={sx} cy={sy} rx={rx} ry={ry} fill="none" stroke={color} strokeWidth="0.6" opacity="0.6">
          <animate attributeName="rx" values={`${rx};${rx*1.3};${rx}`} dur="1.6s" repeatCount="indefinite" />
          <animate attributeName="ry" values={`${ry};${ry*1.3};${ry}`} dur="1.6s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.6;0;0.6" dur="1.6s" repeatCount="indefinite" />
        </ellipse>
      )}
    </g>
  );
}

// --- Road lane dashes (subtle) ---
function RoadMarkings() {
  // Only on row 5 and col 8 — main arterials
  const elems = [];
  // Row 5 horizontal dashes
  for (let x = 0; x < window.GRID_W; x++) {
    const { sx, sy } = iso(x, 5);
    elems.push(
      <line key={`rh-${x}`} x1={sx - TILE_W*0.3} y1={sy} x2={sx + TILE_W*0.3} y2={sy} stroke="#ffc14a" strokeWidth="1" opacity="0.4" strokeDasharray="2,3" />
    );
  }
  // Col 8 vertical dashes (in iso = diagonal)
  for (let y = 0; y < window.GRID_H; y++) {
    const { sx, sy } = iso(8, y);
    elems.push(
      <circle key={`rv-${y}`} cx={sx} cy={sy} r="1" fill="#ffc14a" opacity="0.5" />
    );
  }
  return <g>{elems}</g>;
}

// --- Helpers for drawing iso prisms ---
function isoBox(sx, sy, height, color) {
  const top    = `${sx},${sy - TILE_H - height} ${sx + TILE_W},${sy - height} ${sx},${sy + TILE_H - height} ${sx - TILE_W},${sy - height}`;
  const right  = `${sx + TILE_W},${sy - height} ${sx},${sy + TILE_H - height} ${sx},${sy + TILE_H} ${sx + TILE_W},${sy}`;
  const left   = `${sx - TILE_W},${sy - height} ${sx},${sy + TILE_H - height} ${sx},${sy + TILE_H} ${sx - TILE_W},${sy}`;
  return { top, right, left, rightShade: shade(color, -0.18), leftShade: shade(color, -0.34) };
}

// --- District-varied generic building (terrain=1 fills) ---
function DistrictBuilding({ x, y }) {
  const { sx, sy } = iso(x, y);
  const district = window.getDistrict(y);
  const seed = (x * 73 + y * 31 + 7) % 1000;
  // Stable pseudo-random
  const rnd = (n) => ((seed * (n+1) * 1103515245 + 12345) % 2147483647) / 2147483647;

  if (district === "downtown") {
    return <DowntownTower x={x} y={y} sx={sx} sy={sy} seed={seed} rnd={rnd} />;
  }
  if (district === "docks") {
    return <DocksWarehouse x={x} y={y} sx={sx} sy={sy} seed={seed} rnd={rnd} />;
  }
  return <ResidentialHouse x={x} y={y} sx={sx} sy={sy} seed={seed} rnd={rnd} />;
}

// --- Downtown: tall office towers with grid windows + AC units / antenna ---
function DowntownTower({ x, y, sx, sy, seed, rnd }) {
  const palettes = [
    { main: "#2c3147", roof: "#3a4564", glass: "#4d6394" },
    { main: "#262a3d", roof: "#36405c", glass: "#5a7ab0" },
    { main: "#323852", roof: "#404a6b", glass: "#406090" },
    { main: "#1f2436", roof: "#2c3450", glass: "#3a5a90" },
  ];
  const pal = palettes[seed % palettes.length];
  const height = 28 + (seed % 18);
  const box = isoBox(sx, sy, height, pal.main);

  // Window grid — rows × cols on each visible face
  const cols = 3 + (seed % 2);
  const rows = Math.max(2, Math.floor(height / 8));

  // Lit windows pattern
  const lit = (i, j, face) => ((i * 17 + j * 23 + seed * 7 + (face === "L" ? 0 : 11)) % 7) < 2;

  const windows = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const fx = (c + 0.5) / cols;
      const fy = (r + 0.5) / rows;
      // Right face windows
      const rxTop = sx + TILE_W * fx;
      const ryTop = sy - height + TILE_H * fx;
      const rxBot = rxTop;
      const ryBot = ryTop + height * 0.86;
      const wx = rxTop - 1.4;
      const wy = ryTop + (height * 0.86) * (fy - 0.5/rows) + 2;
      windows.push(
        <rect key={`r-${r}-${c}`} x={wx} y={wy} width="2.6" height="2.4" fill={lit(r,c,"R") ? "#ffe08a" : pal.glass} opacity={lit(r,c,"R") ? 0.92 : 0.55} />
      );
      // Left face windows
      const lx = sx - TILE_W * fx + 0.6;
      const ly = sy - height + TILE_H * fx + (height * 0.86) * (fy - 0.5/rows) + 2;
      windows.push(
        <rect key={`l-${r}-${c}`} x={lx} y={ly} width="2.6" height="2.4" fill={lit(r,c,"L") ? "#ffe08a" : pal.glass} opacity={lit(r,c,"L") ? 0.92 : 0.4} />
      );
    }
  }

  // Roof details: AC unit, antenna, water tank
  const detail = seed % 4;
  const roofY = sy - height;

  return (
    <g filter="url(#ds)">
      <polygon points={box.left} fill={box.leftShade} />
      <polygon points={box.right} fill={box.rightShade} />
      {windows}
      <polygon points={box.top} fill={pal.roof} stroke={shade(pal.roof, -0.3)} strokeWidth="0.4" />
      {/* Roof parapet */}
      <polygon points={`${sx-TILE_W*0.85},${roofY-TILE_H*0.85+1} ${sx},${roofY-TILE_H*0.95+1} ${sx+TILE_W*0.85},${roofY-TILE_H*0.85+1} ${sx+TILE_W*0.85},${roofY-TILE_H*0.85+2} ${sx},${roofY-TILE_H*0.95+2} ${sx-TILE_W*0.85},${roofY-TILE_H*0.85+2}`} fill={shade(pal.roof, 0.15)} opacity="0.5" />
      {detail === 0 && (
        <g>
          {/* AC unit */}
          <rect x={sx - 5} y={roofY - 3} width="10" height="3" fill={shade(pal.main, 0.2)} />
          <line x1={sx - 4} y1={roofY - 2} x2={sx + 4} y2={roofY - 2} stroke={shade(pal.main, -0.2)} strokeWidth="0.5" />
        </g>
      )}
      {detail === 1 && (
        <g>
          {/* Antenna */}
          <line x1={sx} y1={roofY} x2={sx} y2={roofY - 10} stroke="#888" strokeWidth="0.6" />
          <line x1={sx - 2} y1={roofY - 8} x2={sx + 2} y2={roofY - 8} stroke="#888" strokeWidth="0.5" />
          <circle cx={sx} cy={roofY - 11} r="0.8" fill="#ff4040">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
      {detail === 2 && (
        <g>
          {/* Water tank */}
          <ellipse cx={sx} cy={roofY - 4} rx="4" ry="1.5" fill={shade(pal.main, 0.3)} />
          <rect x={sx - 4} y={roofY - 6} width="8" height="3" fill="#4a3a2a" />
          <ellipse cx={sx} cy={roofY - 6} rx="4" ry="1.5" fill="#5a4a3a" />
        </g>
      )}
      {detail === 3 && (
        <g>
          {/* Stairwell box */}
          <rect x={sx - 4} y={roofY - 5} width="8" height="5" fill={shade(pal.main, 0.15)} />
          <rect x={sx - 3} y={roofY - 4} width="2" height="2" fill={shade(pal.glass, 0.2)} />
        </g>
      )}
      {/* Fire escape on left face if seed bit */}
      {(seed % 5) === 0 && (
        <g>
          <line x1={sx - TILE_W * 0.55} y1={sy - 2} x2={sx - TILE_W * 0.55} y2={sy - height + 4} stroke="#1a1410" strokeWidth="0.5" />
          {[0.3, 0.55, 0.8].map(t => (
            <line key={t} x1={sx - TILE_W * 0.7} y1={sy - height * t} x2={sx - TILE_W * 0.4} y2={sy - height * t + 2} stroke="#1a1410" strokeWidth="0.4" />
          ))}
        </g>
      )}
    </g>
  );
}

// --- Docks: stout warehouses with corrugated roofs + roller doors ---
function DocksWarehouse({ x, y, sx, sy, seed, rnd }) {
  const palettes = [
    { main: "#3a352d", roof: "#4d4538", door: "#1c1812" },
    { main: "#36322a", roof: "#5a5040", door: "#1c1812" },
    { main: "#2f2b25", roof: "#42392f", door: "#1c1812" },
  ];
  const pal = palettes[seed % palettes.length];
  const height = 16 + (seed % 8);
  const box = isoBox(sx, sy, height, pal.main);

  // Corrugated roof — alternating stripes
  const stripes = [];
  for (let i = 0; i < 6; i++) {
    const t = i / 6;
    const x1 = sx - TILE_W + (TILE_W) * t;
    const y1 = sy - height + TILE_H * t;
    const x2 = sx + (TILE_W) * t;
    const y2 = sy - height - TILE_H + TILE_H * t;
    stripes.push(<line key={`s-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={shade(pal.roof, -0.2)} strokeWidth="0.4" />);
  }

  return (
    <g filter="url(#ds)">
      <polygon points={box.left} fill={box.leftShade} />
      <polygon points={box.right} fill={box.rightShade} />
      {/* Roller door on right face */}
      <rect x={sx + 2} y={sy - height * 0.55} width={TILE_W * 0.55} height={height * 0.55} fill={pal.door} />
      {[0.2, 0.4, 0.6, 0.8].map(t => (
        <line key={t} x1={sx + 2} y1={sy - height * 0.55 + height * 0.55 * t} x2={sx + 2 + TILE_W * 0.55} y2={sy - height * 0.55 + height * 0.55 * t} stroke={shade(pal.door, 0.4)} strokeWidth="0.3" />
      ))}
      {/* Small window high on left face */}
      <rect x={sx - TILE_W * 0.65} y={sy - height + 3} width="6" height="2.5" fill="#ffd96a" opacity={(seed % 3) === 0 ? 0.8 : 0.2} />
      <polygon points={box.top} fill={pal.roof} stroke={shade(pal.roof, -0.3)} strokeWidth="0.4" />
      {stripes}
      {/* Stacked crates on roof sometimes */}
      {(seed % 3) === 0 && (
        <g>
          <rect x={sx - 4} y={sy - height - 4} width="4" height="3" fill="#7a5d2a" />
          <rect x={sx - 4} y={sy - height - 4} width="4" height="3" fill="none" stroke="#5a3d18" strokeWidth="0.4" />
          <rect x={sx + 1} y={sy - height - 3} width="3" height="2" fill="#7a5d2a" stroke="#5a3d18" strokeWidth="0.3" />
        </g>
      )}
      {/* Crane on some warehouses */}
      {(seed % 7) === 0 && (
        <g>
          <line x1={sx + TILE_W * 0.6} y1={sy - height} x2={sx + TILE_W * 0.6} y2={sy - height - 14} stroke="#dc8" strokeWidth="0.7" />
          <line x1={sx + TILE_W * 0.6} y1={sy - height - 14} x2={sx + TILE_W * 0.2} y2={sy - height - 12} stroke="#dc8" strokeWidth="0.6" />
          <line x1={sx + TILE_W * 0.3} y1={sy - height - 12.5} x2={sx + TILE_W * 0.3} y2={sy - height - 8} stroke="#888" strokeWidth="0.3" />
        </g>
      )}
    </g>
  );
}

// --- Residential: pitched roofs, chimneys, balconies ---
function ResidentialHouse({ x, y, sx, sy, seed, rnd }) {
  const palettes = [
    { main: "#3d3328", roof: "#5a2820" },
    { main: "#2f3a3d", roof: "#4a3018" },
    { main: "#3a2f3a", roof: "#4a201c" },
    { main: "#2c3530", roof: "#3a2820" },
  ];
  const pal = palettes[seed % palettes.length];
  const height = 14 + (seed % 8);
  const box = isoBox(sx, sy, height, pal.main);

  // Pitched roof apex above the regular top
  const apexH = 6 + (seed % 4);
  const apexY = sy - height - apexH;

  // Roof: two triangular gables forming a peaked roof
  const roofLeft = `${sx - TILE_W},${sy - height} ${sx},${apexY} ${sx},${sy + TILE_H - height}`;
  const roofRight = `${sx + TILE_W},${sy - height} ${sx},${apexY} ${sx},${sy + TILE_H - height}`;
  const roofTopBack = `${sx - TILE_W},${sy - height} ${sx},${sy - height - TILE_H} ${sx + TILE_W},${sy - height} ${sx},${apexY}`;

  return (
    <g filter="url(#ds)">
      <polygon points={box.left} fill={box.leftShade} />
      <polygon points={box.right} fill={box.rightShade} />
      {/* Door on right face */}
      <rect x={sx + 1} y={sy - height * 0.45} width="3" height={height * 0.45} fill={shade(pal.main, -0.5)} />
      <circle cx={sx + 3.5} cy={sy - height * 0.2} r="0.4" fill="#dca066" />
      {/* Windows */}
      <rect x={sx + TILE_W * 0.55} y={sy - height + 4} width="3.5" height="2.5" fill="#ffd96a" opacity={(seed % 4) === 0 ? 0.85 : 0.3} />
      <rect x={sx - TILE_W * 0.6} y={sy - height + 4} width="3.5" height="2.5" fill="#ffd96a" opacity={(seed % 5) === 0 ? 0.8 : 0.25} />
      <rect x={sx - TILE_W * 0.4} y={sy - height * 0.5} width="3" height="2.5" fill="#ffd96a" opacity={(seed % 3) === 1 ? 0.7 : 0.2} />
      {/* Pitched roof */}
      <polygon points={roofLeft} fill={shade(pal.roof, -0.15)} />
      <polygon points={roofRight} fill={pal.roof} />
      <polygon points={roofTopBack} fill={shade(pal.roof, 0.1)} opacity="0.95" />
      <line x1={sx} y1={apexY} x2={sx} y2={sy + TILE_H - height} stroke={shade(pal.roof, -0.4)} strokeWidth="0.4" />
      <line x1={sx} y1={apexY} x2={sx - TILE_W} y2={sy - height} stroke={shade(pal.roof, -0.4)} strokeWidth="0.4" />
      <line x1={sx} y1={apexY} x2={sx + TILE_W} y2={sy - height} stroke={shade(pal.roof, -0.4)} strokeWidth="0.4" />
      {/* Chimney */}
      {(seed % 3) === 0 && (
        <g>
          <rect x={sx - 8} y={apexY + 2} width="3" height="6" fill="#3a2820" />
          <rect x={sx - 8.3} y={apexY + 1} width="3.6" height="1.4" fill="#26181a" />
          {(seed % 6) < 3 && (
            <ellipse cx={sx - 6.5} cy={apexY - 2} rx="2" ry="3" fill="#aaa" opacity="0.3">
              <animate attributeName="opacity" values="0.1;0.4;0.1" dur="3s" repeatCount="indefinite" />
            </ellipse>
          )}
        </g>
      )}
      {/* Balcony on right face */}
      {(seed % 4) === 1 && (
        <g>
          <rect x={sx + 1} y={sy - height * 0.55 + 1} width={TILE_W * 0.6} height="0.8" fill={shade(pal.main, -0.5)} />
          <line x1={sx + 1} y1={sy - height * 0.55} x2={sx + TILE_W * 0.6} y2={sy - height * 0.55 + TILE_H * 0.3} stroke="#1a1410" strokeWidth="0.4" />
          <line x1={sx + 2} y1={sy - height * 0.55} x2={sx + 2} y2={sy - height * 0.55 + 2} stroke="#1a1410" strokeWidth="0.3" />
          <line x1={sx + 5} y1={sy - height * 0.55 + 0.5} x2={sx + 5} y2={sy - height * 0.55 + 2.5} stroke="#1a1410" strokeWidth="0.3" />
        </g>
      )}
    </g>
  );
}

// --- Special buildings (shop, hideout, police, warehouse, safe house) ---
function SpecialBuilding({ x, y, spec, terrain, intelGathered }) {
  const { sx, sy } = iso(x, y);
  const height = spec.height;
  const box = isoBox(sx, sy, height, spec.color);
  const roofY = sy - height;

  return (
    <g filter="url(#ds)">
      <polygon points={box.left} fill={box.leftShade} />
      <polygon points={box.right} fill={box.rightShade} />

      {/* Per-terrain front details on right face */}
      {terrain === 3 && (
        // SHOP — awning + door + signage
        <g>
          {/* Storefront */}
          <rect x={sx + 1} y={sy - height * 0.5} width={TILE_W * 0.7} height={height * 0.5} fill="#1a1410" />
          <rect x={sx + 1} y={sy - height * 0.5} width={TILE_W * 0.7} height="2.2" fill="#ffe08a" opacity="0.5" />
          {/* Door */}
          <rect x={sx + TILE_W * 0.4} y={sy - height * 0.4} width="3" height={height * 0.4} fill="#3a2c14" />
          {/* Awning — striped */}
          {[0, 0.2, 0.4, 0.6, 0.8].map(t => (
            <line key={t} x1={sx + 1 + TILE_W * 0.7 * t} y1={sy - height * 0.55} x2={sx + 1 + TILE_W * 0.7 * (t + 0.1)} y2={sy - height * 0.55 + 2} stroke={t * 10 % 2 < 1 ? "#c44" : "#fff" } strokeWidth="0.6" />
          ))}
          <polygon points={`${sx + 1},${sy - height * 0.55} ${sx + 1 + TILE_W * 0.7},${sy - height * 0.55} ${sx + 1 + TILE_W * 0.7 - 1},${sy - height * 0.55 + 2.5} ${sx + 2},${sy - height * 0.55 + 2.5}`} fill="#c44" opacity="0.6" />
        </g>
      )}
      {terrain === 5 && (
        // HIDEOUT — boarded windows, neon
        <g>
          <rect x={sx + 2} y={sy - height * 0.55} width={TILE_W * 0.55} height={height * 0.55} fill="#1a0a0a" />
          {/* Boarded planks */}
          <line x1={sx + 2} y1={sy - height * 0.45} x2={sx + 2 + TILE_W * 0.55} y2={sy - height * 0.45 + TILE_H * 0.3} stroke="#5a3a18" strokeWidth="0.7" />
          <line x1={sx + 2} y1={sy - height * 0.3} x2={sx + 2 + TILE_W * 0.55} y2={sy - height * 0.3 + TILE_H * 0.3} stroke="#5a3a18" strokeWidth="0.7" />
          {/* Neon strip */}
          <rect x={sx - TILE_W * 0.7} y={sy - height + 2} width={TILE_W * 1.4} height="1.5" fill="#ff3050">
            <animate attributeName="opacity" values="0.6;1;0.6" dur="1.4s" repeatCount="indefinite" />
          </rect>
        </g>
      )}
      {terrain === 6 && (
        // POLICE — entrance, columns, light bar
        <g>
          {/* Steps */}
          <rect x={sx + 1} y={sy - 2} width={TILE_W * 0.7} height="2" fill={shade(spec.color, -0.4)} />
          {/* Door */}
          <rect x={sx + TILE_W * 0.3} y={sy - height * 0.45} width="4" height={height * 0.45} fill="#0a1230" />
          {/* Columns */}
          {[0.15, 0.55].map(t => (
            <rect key={t} x={sx + 2 + TILE_W * 0.7 * t} y={sy - height * 0.45} width="1.2" height={height * 0.45} fill={shade(spec.color, 0.2)} />
          ))}
          {/* Roof flag */}
          <line x1={sx} y1={roofY} x2={sx} y2={roofY - 12} stroke="#888" strokeWidth="0.5" />
          <polygon points={`${sx},${roofY - 12} ${sx + 5},${roofY - 10.5} ${sx},${roofY - 9}`} fill="#5b8cff" />
          {/* Blue/red flashers */}
          <circle cx={sx - 4} cy={roofY - 2} r="1" fill="#5b8cff">
            <animate attributeName="opacity" values="1;0.1;1" dur="0.8s" repeatCount="indefinite" />
          </circle>
          <circle cx={sx + 4} cy={roofY - 2} r="1" fill="#ff3050">
            <animate attributeName="opacity" values="0.1;1;0.1" dur="0.8s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
      {terrain === 7 && (
        // WAREHOUSE — large roller door, intel marker
        <g>
          <rect x={sx + 1} y={sy - height * 0.7} width={TILE_W * 0.75} height={height * 0.7} fill="#0e0c08" />
          {[0.15, 0.3, 0.45, 0.6, 0.75, 0.9].map(t => (
            <line key={t} x1={sx + 1} y1={sy - height * 0.7 + height * 0.7 * t} x2={sx + 1 + TILE_W * 0.75} y2={sy - height * 0.7 + height * 0.7 * t + TILE_H * 0.05} stroke="#3a3733" strokeWidth="0.4" />
          ))}
          {/* Caution stripes at base */}
          {[0, 0.2, 0.4, 0.6, 0.8].map(t => (
            <rect key={t} x={sx + 1 + TILE_W * 0.75 * t} y={sy - 1.5} width={TILE_W * 0.075} height="1.5" fill={t * 10 % 2 < 1 ? "#ffc14a" : "#1a1410"} />
          ))}
          {/* Intel pulse */}
          {!intelGathered && (
            <circle cx={sx} cy={roofY - 6} r="2" fill="#ffc14a">
              <animate attributeName="r" values="1.5;3.5;1.5" dur="1.8s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="1;0.2;1" dur="1.8s" repeatCount="indefinite" />
            </circle>
          )}
        </g>
      )}
      {terrain === 8 && (
        // SAFE HOUSE — modest door, hidden vibes
        <g>
          <rect x={sx + TILE_W * 0.3} y={sy - height * 0.4} width="3" height={height * 0.4} fill="#0a1812" />
          {/* Window */}
          <rect x={sx + TILE_W * 0.55} y={sy - height * 0.7} width="3" height="2.5" fill="#1c5a36" opacity="0.5" />
          {/* Slats over window */}
          <line x1={sx + TILE_W * 0.55} y1={sy - height * 0.66} x2={sx + TILE_W * 0.55 + 3} y2={sy - height * 0.66} stroke="#0a1812" strokeWidth="0.3" />
          <line x1={sx + TILE_W * 0.55} y1={sy - height * 0.6} x2={sx + TILE_W * 0.55 + 3} y2={sy - height * 0.6} stroke="#0a1812" strokeWidth="0.3" />
          {/* Roof antenna */}
          <line x1={sx} y1={roofY} x2={sx} y2={roofY - 8} stroke="#888" strokeWidth="0.5" />
          <line x1={sx - 2} y1={roofY - 6} x2={sx + 2} y2={roofY - 6} stroke="#888" strokeWidth="0.4" />
        </g>
      )}

      <polygon points={box.top} fill={spec.roof} stroke={shade(spec.roof, -0.3)} strokeWidth="0.5" />

      {/* Sign label hovering above */}
      {spec.label && (
        <g>
          <rect x={sx - 18} y={roofY - TILE_H - 13} width="36" height="10" fill="#0a0e18" stroke={spec.roof} strokeWidth="0.6" rx="1" />
          <text x={sx} y={roofY - TILE_H - 5.5} fontSize="6.5" fill={spec.roof} textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontWeight="700">{spec.label}</text>
          {terrain === 7 && !intelGathered && (
            <text x={sx} y={roofY - TILE_H - 15} fontSize="5" fill="#ffc14a" textAnchor="middle" fontFamily="JetBrains Mono, monospace">◆ INTEL</text>
          )}
          {terrain === 7 && intelGathered && (
            <text x={sx} y={roofY - TILE_H - 15} fontSize="5" fill="#3acc78" textAnchor="middle" fontFamily="JetBrains Mono, monospace">✓ TAKEN</text>
          )}
        </g>
      )}
    </g>
  );
}

function shade(hex, p) {
  // p in [-1, 1]
  const c = hex.replace("#", "");
  const r = parseInt(c.slice(0,2), 16);
  const g = parseInt(c.slice(2,4), 16);
  const b = parseInt(c.slice(4,6), 16);
  const f = (v) => Math.max(0, Math.min(255, Math.round(v + (p < 0 ? v * p : (255 - v) * p))));
  return `rgb(${f(r)},${f(g)},${f(b)})`;
}

// --- Tree --- a small cluster of 1-2 trees, deterministic per tile
function Tree({ x, y }) {
  const { sx, sy } = iso(x, y);
  const seed = (x * 17 + y * 23) % 7;
  // 1 or 2 trees per tile
  const count = 1 + (seed % 2);
  const positions = [];
  for (let i = 0; i < count; i++) {
    const s = (seed + i * 11) % 13;
    const ox = ((s * 7) % (TILE_W * 1.0)) - TILE_W * 0.5;
    const oy = ((s * 13) % (TILE_H * 0.9)) - TILE_H * 0.45;
    const sz = 0.6 + ((s * 3) % 7) * 0.05;        // 0.6 .. 0.9 — smaller
    const tone = (s % 3); // 0/1/2 → different greens
    positions.push({ ox, oy, sz, tone });
  }
  // Sort so trees further back render first
  positions.sort((a, b) => a.oy - b.oy);
  const greens = [
    { dark: "#143a1c", mid: "#1c5a30", light: "#2a7a40" },
    { dark: "#1a3a14", mid: "#27602a", light: "#3a8a3a" },
    { dark: "#103018", mid: "#185028", light: "#206a32" },
  ];
  return (
    <g transform={`translate(${sx}, ${sy})`}>
      {positions.map((p, i) => {
        const g = greens[p.tone];
        return (
          <g key={i} transform={`translate(${p.ox}, ${p.oy}) scale(${p.sz})`}>
            <ellipse cx="0" cy="2" rx="6" ry="1.5" fill="#000" opacity="0.45" />
            <rect x="-1.2" y="-10" width="2.4" height="11" fill="#3a2a18" />
            <circle cx="0" cy="-13" r="7" fill={g.mid} />
            <circle cx="-3" cy="-15" r="4" fill={g.light} />
            <circle cx="3" cy="-12" r="4" fill={g.dark} />
          </g>
        );
      })}
    </g>
  );
}

// --- Agent sprite (top-down character with head/body/shadow) ---
function AgentSprite({ x, y, coverBlown }) {
  const { sx, sy } = iso(x, y);
  const color = coverBlown ? "#ff3344" : "#ffc14a";
  return (
    <g style={{ transition: "transform 0.6s cubic-bezier(0.22,0.61,0.36,1)" }} transform={`translate(${sx}, ${sy})`}>
      {/* glow */}
      <circle cx="0" cy="0" r="22" fill="url(#agent-glow)" />
      {/* shadow */}
      <ellipse cx="0" cy="2" rx="9" ry="3.5" fill="#000" opacity="0.5" />
      {/* legs */}
      <rect x="-4" y="-6" width="3" height="9" fill="#1c1610" rx="0.5" />
      <rect x="1" y="-6" width="3" height="9" fill="#1c1610" rx="0.5" />
      {/* torso (long coat) */}
      <path d="M -7 -16 L 7 -16 L 9 -2 L -9 -2 Z" fill={shade(color, -0.5)} />
      <path d="M -6 -16 L 6 -16 L 7 -4 L -7 -4 Z" fill={color} />
      {/* shoulders */}
      <ellipse cx="-7" cy="-15" rx="3" ry="2.5" fill={shade(color, -0.3)} />
      <ellipse cx="7" cy="-15" rx="3" ry="2.5" fill={shade(color, -0.3)} />
      {/* head */}
      <circle cx="0" cy="-19" r="4.5" fill="#d8a878" />
      {/* hat / hood */}
      <path d="M -5 -22 Q 0 -26 5 -22 L 5 -19 Q 0 -22 -5 -19 Z" fill="#1c1610" />
      <ellipse cx="0" cy="-19.5" rx="6" ry="1.5" fill="#0a0608" />
      {/* idle bob via animation */}
      <animateTransform attributeName="transform" type="translate" values="0,0; 0,-0.6; 0,0" dur="2s" repeatCount="indefinite" additive="sum" />
      {/* AGENT label */}
      <text x="0" y="10" fontSize="6" fill={color} textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontWeight="700">AGENT</text>
    </g>
  );
}

// --- NPC sprite (varied by faction) ---
function NpcSprite({ npc, isFocus, onClick }) {
  const { sx, sy } = iso(npc.x, npc.y);
  const factionColor = { gang: "#ff5959", police: "#5b8cff", civilian: "#cdd2dd" }[npc.faction];
  const danger = npc.suspicion >= 60;

  // Bodies differ slightly per faction
  const body = (() => {
    if (npc.faction === "gang") {
      // Leather jacket, no hat, scar
      return (
        <>
          <path d="M -6 -15 L 6 -15 L 8 -2 L -8 -2 Z" fill="#1a0a0a" />
          <path d="M -5 -15 L 5 -15 L 6 -3 L -6 -3 Z" fill={factionColor} opacity="0.7" />
          <line x1="-6" y1="-15" x2="6" y2="-15" stroke="#3a0a0a" strokeWidth="1" />
          <circle cx="0" cy="-19" r="4.2" fill="#c89868" />
          <line x1="-2" y1="-20" x2="2" y2="-19" stroke="#7a3838" strokeWidth="0.6" /> {/* scar */}
          <path d="M -4 -23 L 4 -23 L 4 -20 L -4 -20 Z" fill="#0a0608" />
        </>
      );
    }
    if (npc.faction === "police") {
      // Uniform, cap
      return (
        <>
          <path d="M -6 -15 L 6 -15 L 8 -2 L -8 -2 Z" fill={shade(factionColor, -0.5)} />
          <path d="M -5 -15 L 5 -15 L 6 -3 L -6 -3 Z" fill={factionColor} />
          <rect x="-1" y="-12" width="2" height="6" fill="#ffc14a" /> {/* badge */}
          <circle cx="0" cy="-19" r="4.2" fill="#d8a878" />
          <ellipse cx="0" cy="-22" rx="5.5" ry="1.5" fill="#0a1230" />
          <rect x="-5" y="-23" width="10" height="3" fill="#1a2c5a" />
        </>
      );
    }
    // civilian
    return (
      <>
        <path d="M -6 -15 L 6 -15 L 8 -2 L -8 -2 Z" fill={shade(factionColor, -0.4)} />
        <path d="M -5 -15 L 5 -15 L 6 -3 L -6 -3 Z" fill={factionColor} />
        <circle cx="0" cy="-19" r="4.2" fill="#d8a878" />
        <path d="M -4 -22 Q 0 -24 4 -22 L 3 -20 L -3 -20 Z" fill="#3a2a18" />
      </>
    );
  })();

  return (
    <g
      style={{ transition: "transform 0.6s cubic-bezier(0.22,0.61,0.36,1)", cursor: "pointer" }}
      transform={`translate(${sx}, ${sy})`}
      onClick={onClick}
    >
      {/* shadow */}
      <ellipse cx="0" cy="2" rx="8" ry="3" fill="#000" opacity="0.5" />
      {/* legs */}
      <rect x="-3.5" y="-6" width="2.6" height="8" fill="#1a1410" rx="0.5" />
      <rect x="0.9" y="-6" width="2.6" height="8" fill="#1a1410" rx="0.5" />
      {/* body */}
      {body}
      {/* trust ring */}
      {npc.trust > 0 && (
        <circle cx="0" cy="-7" r="14" fill="none" stroke="#3acc78" strokeWidth="1.2"
          strokeDasharray={`${(npc.trust/100) * 2 * Math.PI * 14} ${2*Math.PI*14}`} opacity="0.85" transform="rotate(-90)" />
      )}
      {/* suspicion ring */}
      {npc.suspicion > 0 && (
        <circle cx="0" cy="-7" r="11" fill="none" stroke="#ff4040" strokeWidth="1.2"
          strokeDasharray={`${(npc.suspicion/100) * 2 * Math.PI * 11} ${2*Math.PI*11}`} opacity="0.85" transform="rotate(-90)" />
      )}
      {/* focus halo */}
      {isFocus && <circle cx="0" cy="-7" r="18" fill="none" stroke="#ffc14a" strokeWidth="1" opacity="0.8" strokeDasharray="2,2" />}
      {/* danger pulse */}
      {danger && (
        <circle cx="0" cy="-7" r="13" fill="none" stroke="#ff4040" strokeWidth="1">
          <animate attributeName="r" values="13;22" dur="1.2s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.7;0" dur="1.2s" repeatCount="indefinite" />
        </circle>
      )}
      {/* idle bob */}
      <animateTransform attributeName="transform" type="translate" values="0,0; 0,-0.5; 0,0" dur="2.4s" begin={`${(npc.x*0.1 + npc.y*0.13)}s`} repeatCount="indefinite" additive="sum" />
      {/* name */}
      <text x="0" y="10" fontSize="6" fill={factionColor} textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontWeight="700">{npc.name.toUpperCase()}</text>
    </g>
  );
}

// --- Speech bubble (positioned via pre-computed placed.bx/by from CityScene) ---
function SpeechBubble({ placed, padX, padY, lineH }) {
  const { lines, boxW, boxH, bx, by, anchorSx, anchorSy, side } = placed;
  const isAgent = side === "agent";
  const fill = isAgent ? "#ffc14a" : "#16213e";
  const textColor = isAgent ? "#1a1208" : "#e6ebf5";
  const stroke = isAgent ? "#1a1208" : "#3a4564";
  // Tail anchored from bubble bottom toward the speaker's head
  const tailFromX = (bx + boxW / 2);     // bottom-center of bubble
  const tailFromY = (by + boxH);
  const tailToX = anchorSx;
  const tailToY = anchorSy - 18;          // head height
  return (
    <g className="speech-fade">
      {/* connector line from bubble tail toward speaker */}
      <line x1={tailFromX} y1={tailFromY} x2={tailToX} y2={tailToY}
            stroke={stroke} strokeWidth="0.8" opacity="0.6" strokeDasharray="2 2" />
      <g transform={`translate(${bx}, ${by})`}>
        <rect width={boxW} height={boxH} rx="4" fill={fill} stroke={stroke} strokeWidth="0.8" filter="url(#ds)" />
        <text x={padX} y={padY + 6} fontSize="6" fill={isAgent ? "#5c4308" : "#7c8aa8"}
              fontFamily="JetBrains Mono, monospace" fontWeight="700" letterSpacing="0.5">
          {isAgent ? "AGENT →" : "← NPC"}
        </text>
        {lines.map((l, i) => (
          <text key={i} x={padX} y={padY + 14 + (i + 1) * lineH - 3} fontSize="9" fill={textColor}
                fontFamily={isAgent ? "JetBrains Mono, monospace" : "IBM Plex Sans, sans-serif"}>
            {l}
          </text>
        ))}
      </g>
    </g>
  );
}

window.CityGrid = CityScene;
