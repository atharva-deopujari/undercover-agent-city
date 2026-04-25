"""
Custom web interface for Undercover Agent City environment.

This module provides a city-specific web interface with a 15x15 grid display,
trust/suspicion meters, fact tracker, persona indicator, and action log,
without modifying the base web_interface.py.
"""

from typing import Optional

from openenv.core.env_server.types import EnvironmentMetadata


def get_city_web_interface_html(
    metadata: Optional[EnvironmentMetadata] = None,
) -> str:
    """Generate custom HTML for the Undercover Agent City web interface."""

    env_name = "Undercover Agent City"
    if metadata and metadata.name:
        env_name = metadata.name

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{env_name} - Web Interface</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            margin: 0;
            height: 100vh;
            overflow: hidden;
        }}

        .container {{
            display: flex;
            height: calc(100vh - 140px);
        }}

        /* LEFT PANE */
        .left-pane {{
            width: 50%;
            display: flex;
            flex-direction: column;
            border-right: 2px solid #0f3460;
        }}

        /* RIGHT PANE */
        .right-pane {{
            width: 50%;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }}

        .pane-header {{
            padding: 15px 20px;
            border-bottom: 2px solid #0f3460;
            background: #16213e;
            font-weight: 600;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .pane-content {{
            flex: 1;
            padding: 15px;
            overflow-y: auto;
        }}

        /* Connection Status */
        .status-indicator {{
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #dc3545;
        }}

        .status-connected {{
            background: #28a745;
            box-shadow: 0 0 6px #28a745;
        }}

        .status-disconnected {{
            background: #dc3545;
            box-shadow: 0 0 6px #dc3545;
        }}

        /* Legend */
        .legend {{
            background: #16213e;
            border: 1px solid #0f3460;
            border-radius: 8px;
            padding: 10px 15px;
            margin-bottom: 12px;
        }}

        .legend h3 {{
            font-size: 13px;
            margin-bottom: 8px;
            color: #a0a0c0;
        }}

        .legend-items {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 11px;
        }}

        .legend-color {{
            width: 14px;
            height: 14px;
            border: 1px solid #555;
            border-radius: 2px;
        }}

        /* Grid */
        .grid-container {{
            display: flex;
            justify-content: center;
            padding: 10px;
        }}

        .grid {{
            display: grid;
            gap: 1px;
            background: #111;
            border: 2px solid #0f3460;
            border-radius: 4px;
            padding: 2px;
        }}

        .cell {{
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            font-size: 10px;
            cursor: default;
        }}

        /* Terrain colors (D-05) - matches TERRAIN_INDEX order */
        .cell-road      {{ background: #808080; }}
        .cell-building  {{ background: #4a4a4a; }}
        .cell-alley     {{ background: #5c5c3d; }}
        .cell-shop      {{ background: #daa520; }}
        .cell-park      {{ background: #228b22; }}
        .cell-hideout   {{ background: #8b0000; }}
        .cell-police    {{ background: #4169e1; }}
        .cell-warehouse {{ background: #8b8682; }}
        .cell-safe      {{ background: #006400; }}

        /* Agent marker (D-06) */
        .agent-marker {{
            background: #2196F3;
            border-radius: 50%;
            width: 14px;
            height: 14px;
            position: absolute;
            z-index: 5;
            box-shadow: 0 0 6px #2196F3;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ box-shadow: 0 0 4px #2196F3; }}
            50% {{ box-shadow: 0 0 10px #2196F3, 0 0 20px rgba(33, 150, 243, 0.3); }}
        }}

        /* NPC markers */
        .npc-marker {{
            font-size: 12px;
            position: absolute;
            z-index: 4;
            font-weight: bold;
            text-shadow: 0 0 3px rgba(0,0,0,0.8);
        }}

        .npc-gang {{ color: #ff4444; }}
        .npc-police {{ color: #4169e1; }}
        .npc-civilian {{ color: #ffffff; }}

        /* Panels */
        .status-panel, .meters-panel, .fact-panel, .mission-panel {{
            background: #16213e;
            border: 1px solid #0f3460;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
        }}

        .status-panel h3, .meters-panel h3, .fact-panel h3, .mission-panel h3 {{
            font-size: 14px;
            margin-bottom: 10px;
            color: #a0a0c0;
            border-bottom: 1px solid #0f3460;
            padding-bottom: 6px;
        }}

        /* Agent Status */
        .status-row {{
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            font-size: 13px;
        }}

        .status-label {{
            color: #888;
        }}

        .cover-intact {{
            color: #4CAF50;
            font-weight: bold;
        }}

        .cover-blown {{
            color: #f44336;
            font-weight: bold;
            animation: blink 1s infinite;
        }}

        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.3; }}
        }}

        /* Persona badge (D-10) */
        .persona-badge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        .persona-tough {{ background: #f44336; color: white; }}
        .persona-formal {{ background: #2196F3; color: white; }}
        .persona-casual {{ background: #4CAF50; color: white; }}
        .persona-none {{ background: #666; color: white; }}

        /* Trust/Suspicion meters (D-07, D-08) */
        .meter-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }}

        .meter-label {{
            width: 90px;
            font-size: 12px;
            color: #ccc;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .meter {{
            flex: 1;
            background: #333;
            height: 16px;
            border-radius: 3px;
            overflow: hidden;
        }}

        .meter-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.5s ease;
        }}

        .trust-fill {{
            background: #4CAF50;
        }}

        .suspicion-fill {{
            background: #f44336;
        }}

        .meter-value {{
            width: 35px;
            text-align: right;
            font-size: 11px;
            color: #aaa;
        }}

        /* Fact tracker table (D-09) */
        .fact-panel table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}

        .fact-panel th {{
            text-align: left;
            padding: 6px 8px;
            background: #0f3460;
            color: #a0a0c0;
            font-weight: 600;
        }}

        .fact-panel td {{
            padding: 5px 8px;
            border-bottom: 1px solid #1a2a4a;
        }}

        .consistent {{
            color: #4CAF50;
            font-weight: bold;
        }}

        .contradiction {{
            color: #f44336;
            font-weight: bold;
            animation: blink 1.5s infinite;
        }}

        /* Mission checklist (D-11) */
        .check-item {{
            padding: 4px 0;
            font-size: 13px;
            font-family: monospace;
            color: #888;
        }}

        .check-item.done {{
            color: #4CAF50;
        }}

        /* ACTION LOG (D-02) */
        .action-log-panel {{
            height: 140px;
            overflow-y: auto;
            border-top: 2px solid #0f3460;
            padding: 10px 15px;
            background: #16213e;
        }}

        .action-log-panel h3 {{
            font-size: 13px;
            color: #a0a0c0;
            margin-bottom: 8px;
        }}

        .log-entry {{
            display: flex;
            gap: 12px;
            padding: 4px 0;
            border-bottom: 1px solid #1a2a4a;
            font-size: 12px;
            align-items: center;
        }}

        .log-step {{
            color: #4169e1;
            font-weight: bold;
            white-space: nowrap;
        }}

        .log-action {{
            flex: 1;
            color: #ccc;
            font-family: monospace;
            font-size: 11px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .log-reward {{
            color: #4CAF50;
            font-weight: 600;
            white-space: nowrap;
        }}

        .log-done {{
            color: #f44336;
            font-weight: bold;
        }}

        /* Controls */
        .controls {{
            display: flex;
            gap: 8px;
            padding: 8px 15px;
            background: #0f3460;
            justify-content: flex-end;
        }}

        .btn {{
            background: #1a5276;
            color: white;
            border: 1px solid #2196F3;
            padding: 6px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}

        .btn:hover {{
            background: #2196F3;
        }}

        /* Scrollbar */
        ::-webkit-scrollbar {{
            width: 6px;
        }}

        ::-webkit-scrollbar-track {{
            background: #1a1a2e;
        }}

        ::-webkit-scrollbar-thumb {{
            background: #0f3460;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- LEFT PANE: City Grid -->
        <div class="left-pane">
            <div class="pane-header">
                <span class="status-indicator" id="connection-status"></span>
                Undercover Agent City
            </div>
            <div class="pane-content">
                <!-- Legend -->
                <div class="legend">
                    <h3>Terrain</h3>
                    <div class="legend-items">
                        <div class="legend-item"><div class="legend-color" style="background:#808080;"></div>Road</div>
                        <div class="legend-item"><div class="legend-color" style="background:#4a4a4a;"></div>Building</div>
                        <div class="legend-item"><div class="legend-color" style="background:#5c5c3d;"></div>Alley</div>
                        <div class="legend-item"><div class="legend-color" style="background:#daa520;"></div>Shop</div>
                        <div class="legend-item"><div class="legend-color" style="background:#228b22;"></div>Park</div>
                        <div class="legend-item"><div class="legend-color" style="background:#8b0000;"></div>Hideout</div>
                        <div class="legend-item"><div class="legend-color" style="background:#4169e1;"></div>Police</div>
                        <div class="legend-item"><div class="legend-color" style="background:#8b8682;"></div>Warehouse</div>
                        <div class="legend-item"><div class="legend-color" style="background:#006400;"></div>Safe House</div>
                    </div>
                    <div class="legend-items" style="margin-top:6px;">
                        <div class="legend-item"><div style="background:#2196F3;border-radius:50%;width:14px;height:14px;"></div>Agent</div>
                        <div class="legend-item"><span style="color:#ff4444;font-size:14px;font-weight:bold;">&#9650;</span>Gang</div>
                        <div class="legend-item"><span style="color:#4169e1;font-size:14px;font-weight:bold;">&#9632;</span>Police</div>
                        <div class="legend-item"><span style="color:#ffffff;font-size:14px;font-weight:bold;">&#9679;</span>Civilian</div>
                    </div>
                </div>

                <!-- Grid -->
                <div class="grid-container">
                    <div id="city-grid" class="grid" style="grid-template-columns: repeat(15, 20px);"></div>
                </div>
            </div>

            <!-- Controls -->
            <div class="controls">
                <button class="btn" id="reset-btn">Reset</button>
                <button class="btn" id="state-btn">Refresh State</button>
            </div>
        </div>

        <!-- RIGHT PANE: Status Panels -->
        <div class="right-pane">
            <div class="pane-header">Agent Status</div>
            <div class="pane-content">
                <!-- Agent Status -->
                <div class="status-panel">
                    <h3>Status</h3>
                    <div class="status-row">
                        <span class="status-label">Cover</span>
                        <span id="cover-status" class="cover-intact">INTACT</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Persona</span>
                        <span id="persona-badge" class="persona-badge persona-none">none</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Turn</span>
                        <span id="turn-display">0/30</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Task</span>
                        <span id="task-display">first_contact</span>
                    </div>
                </div>

                <!-- Trust Meters (D-07) -->
                <div class="meters-panel">
                    <h3>Trust</h3>
                    <div id="trust-meters"></div>
                </div>

                <!-- Suspicion Meters (D-08) -->
                <div class="meters-panel">
                    <h3>Suspicion</h3>
                    <div id="suspicion-meters"></div>
                </div>

                <!-- Fact Tracker (D-09) -->
                <div class="fact-panel">
                    <h3>Fact Tracker</h3>
                    <table id="fact-table">
                        <thead>
                            <tr><th>Topic</th><th>Claim</th><th>Told To</th><th>Consistent</th></tr>
                        </thead>
                        <tbody id="fact-body">
                            <tr><td>origin</td><td>---</td><td>---</td><td>---</td></tr>
                            <tr><td>job</td><td>---</td><td>---</td><td>---</td></tr>
                            <tr><td>boss</td><td>---</td><td>---</td><td>---</td></tr>
                            <tr><td>reason</td><td>---</td><td>---</td><td>---</td></tr>
                            <tr><td>history</td><td>---</td><td>---</td><td>---</td></tr>
                        </tbody>
                    </table>
                </div>

                <!-- Mission Progress (D-11) -->
                <div class="mission-panel">
                    <h3>Mission</h3>
                    <div id="mission-checklist">
                        <div class="check-item">[ ] Gather intel</div>
                        <div class="check-item">[ ] Report to handler</div>
                        <div class="check-item">[ ] Maintain cover</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- BOTTOM: Action Log (D-02) -->
    <div class="action-log-panel">
        <h3>Action Log</h3>
        <div id="action-logs">No actions yet</div>
    </div>

    <script>
        // Terrain index-to-class mapping (matches TERRAIN_INDEX order from city_data.py)
        const TERRAIN_CLASSES = ['cell-road','cell-building','cell-alley','cell-shop','cell-park','cell-hideout','cell-police','cell-warehouse','cell-safe'];
        const TERRAIN_NAMES = ['Road','Building','Alley','Shop','Park','Hideout','Police Station','Warehouse','Safe House'];

        class CityWebInterface {{
            constructor() {{
                this.ws = null;
                this.isConnected = false;
                this.lastPersona = 'none';
                this.init();
            }}

            init() {{
                this.connectWebSocket();
                this.setupEventListeners();
            }}

            connectWebSocket() {{
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${{protocol}}//${{window.location.host}}/ws/ui`;

                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {{
                    this.isConnected = true;
                    this.updateConnectionStatus(true);
                    console.log('WebSocket connected');
                    this.fetchInitialState();
                }};

                this.ws.onmessage = (event) => {{
                    try {{
                        const data = JSON.parse(event.data);
                        console.log('WebSocket message:', data.type);
                        if (data.type === 'state_update') {{
                            this.updateUI(data.episode_state);
                        }}
                    }} catch (error) {{
                        console.error('Error parsing WebSocket message:', error);
                    }}
                }};

                this.ws.onclose = () => {{
                    this.isConnected = false;
                    this.updateConnectionStatus(false);
                    console.log('WebSocket disconnected, reconnecting in 3s...');
                    setTimeout(() => this.connectWebSocket(), 3000);
                }};

                this.ws.onerror = (error) => {{
                    console.error('WebSocket error:', error);
                }};
            }}

            async fetchInitialState() {{
                try {{
                    const resp = await fetch('/web/state');
                    const state = await resp.json();
                    if (state.grid && state.npcs) {{
                        this.renderGrid(state.grid, state.width || 15, state.height || 15, state.agent_x, state.agent_y, state.npcs);
                        this.renderTrustMeters(state.npcs);
                        this.renderSuspicionMeters(state.npcs);
                        this.renderFactTracker(state.fact_db || {{}});
                        this.updateAgentStatus(state);
                    }}
                }} catch (error) {{
                    console.error('Error fetching initial state:', error);
                }}
            }}

            setupEventListeners() {{
                document.getElementById('reset-btn').addEventListener('click', () => {{
                    this.resetEnvironment();
                }});

                document.getElementById('state-btn').addEventListener('click', () => {{
                    this.fetchAndRenderState();
                }});
            }}

            async resetEnvironment() {{
                try {{
                    const response = await fetch('/web/reset', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }}
                    }});
                    if (!response.ok) {{
                        throw new Error(`HTTP error! status: ${{response.status}}`);
                    }}
                    const result = await response.json();
                    console.log('Reset result:', result);
                    // State will update via WebSocket, but also fetch directly
                    setTimeout(() => this.fetchAndRenderState(), 500);
                }} catch (error) {{
                    console.error('Error resetting environment:', error);
                }}
            }}

            updateUI(episodeState) {{
                if (episodeState.current_observation) {{
                    // Observation has partial data (nearby_npcs, not all NPCs or grid)
                    // Fetch full state for complete rendering
                    this.fetchAndRenderState();
                }}

                // Update action logs
                if (episodeState.action_logs) {{
                    this.renderActionLogs(episodeState.action_logs);
                }}

                // Try to extract persona from recent action logs
                if (episodeState.action_logs && episodeState.action_logs.length > 0) {{
                    const lastLog = episodeState.action_logs[episodeState.action_logs.length - 1];
                    if (lastLog.action && lastLog.action.persona) {{
                        this.lastPersona = lastLog.action.persona;
                    }}
                }}
            }}

            async fetchAndRenderState() {{
                try {{
                    const resp = await fetch('/web/state');
                    const state = await resp.json();
                    if (state.grid) {{
                        this.renderGrid(state.grid, state.width || 15, state.height || 15, state.agent_x, state.agent_y, state.npcs || []);
                        this.renderTrustMeters(state.npcs || []);
                        this.renderSuspicionMeters(state.npcs || []);
                        this.renderFactTracker(state.fact_db || {{}});
                        this.updateAgentStatus(state);
                    }}
                }} catch (error) {{
                    console.error('Error fetching state:', error);
                }}
            }}

            renderGrid(grid, width, height, agentX, agentY, npcs) {{
                const container = document.getElementById('city-grid');
                container.innerHTML = '';
                container.style.gridTemplateColumns = `repeat(${{width}}, 20px)`;

                for (let y = 0; y < height; y++) {{
                    for (let x = 0; x < width; x++) {{
                        const idx = y * width + x;
                        const terrainIdx = grid[idx] || 0;
                        const cell = document.createElement('div');
                        cell.className = `cell ${{TERRAIN_CLASSES[terrainIdx] || 'cell-road'}}`;
                        cell.title = `(${{x}},${{y}}) ${{TERRAIN_NAMES[terrainIdx] || 'Unknown'}}`;

                        // Agent marker
                        if (x === agentX && y === agentY) {{
                            const marker = document.createElement('div');
                            marker.className = 'agent-marker';
                            marker.title = 'Agent';
                            cell.appendChild(marker);
                        }}

                        // NPC markers
                        for (const npc of npcs) {{
                            if (npc.x === x && npc.y === y) {{
                                const marker = document.createElement('span');
                                marker.className = `npc-marker npc-${{npc.faction}}`;
                                // gang=triangle, police=square, civilian=circle
                                marker.textContent = npc.faction === 'gang' ? '\u25B2' : npc.faction === 'police' ? '\u25A0' : '\u25CF';
                                marker.title = `${{npc.name}} (${{npc.faction}}) T:${{npc.trust}} S:${{npc.suspicion}}`;
                                cell.appendChild(marker);
                            }}
                        }}

                        container.appendChild(cell);
                    }}
                }}
            }}

            renderTrustMeters(npcs) {{
                const container = document.getElementById('trust-meters');
                container.innerHTML = npcs.map(npc =>
                    `<div class="meter-row">
                        <span class="meter-label">${{npc.name}}</span>
                        <div class="meter"><div class="meter-fill trust-fill" style="width:${{npc.trust}}%"></div></div>
                        <span class="meter-value">${{npc.trust}}%</span>
                    </div>`
                ).join('');
            }}

            renderSuspicionMeters(npcs) {{
                const container = document.getElementById('suspicion-meters');
                container.innerHTML = npcs.map(npc =>
                    `<div class="meter-row">
                        <span class="meter-label">${{npc.name}}</span>
                        <div class="meter"><div class="meter-fill suspicion-fill" style="width:${{npc.suspicion}}%"></div></div>
                        <span class="meter-value">${{npc.suspicion}}%</span>
                    </div>`
                ).join('');
            }}

            renderFactTracker(factDb) {{
                const tbody = document.getElementById('fact-body');
                const topics = ['origin', 'job', 'boss', 'reason', 'history'];
                tbody.innerHTML = topics.map(topic => {{
                    const claims = factDb[topic] || {{}};
                    const entries = Object.entries(claims);
                    if (entries.length === 0) {{
                        return `<tr><td>${{topic}}</td><td>---</td><td>---</td><td>---</td></tr>`;
                    }}
                    const values = [...new Set(entries.map(([,v]) => v))];
                    const consistent = values.length <= 1;
                    const toldTo = entries.map(([npc]) => npc).join(', ');
                    const claimVal = values.join(' / ');
                    return `<tr>
                        <td>${{topic}}</td>
                        <td>${{claimVal}}</td>
                        <td>${{toldTo}}</td>
                        <td>${{consistent ? '<span class="consistent">OK</span>' : '<span class="contradiction">CONTRADICTION</span>'}}</td>
                    </tr>`;
                }}).join('');
            }}

            updateAgentStatus(state) {{
                // Cover status
                const coverEl = document.getElementById('cover-status');
                coverEl.textContent = state.cover_intact ? 'INTACT' : 'BLOWN';
                coverEl.className = state.cover_intact ? 'cover-intact' : 'cover-blown';

                // Turn
                document.getElementById('turn-display').textContent = `${{state.turn || 0}}/${{state.max_turns || 30}}`;

                // Task
                document.getElementById('task-display').textContent = state.current_task || 'first_contact';

                // Persona badge
                const badge = document.getElementById('persona-badge');
                const persona = this.lastPersona || 'none';
                badge.textContent = persona;
                badge.className = `persona-badge persona-${{persona}}`;

                // Mission checklist
                const checklist = document.getElementById('mission-checklist');
                checklist.innerHTML = `
                    <div class="check-item ${{state.intel_gathered ? 'done' : ''}}">${{state.intel_gathered ? '[x]' : '[ ]'}} Gather intel</div>
                    <div class="check-item ${{state.reported_to_handler ? 'done' : ''}}">${{state.reported_to_handler ? '[x]' : '[ ]'}} Report to handler</div>
                    <div class="check-item ${{state.cover_intact ? 'done' : ''}}">${{state.cover_intact ? '[x]' : '[ ]'}} Maintain cover</div>
                `;
            }}

            renderActionLogs(logs) {{
                const container = document.getElementById('action-logs');
                if (!logs || logs.length === 0) {{
                    container.innerHTML = 'No actions yet';
                    return;
                }}
                // Show most recent first, limit to 20
                container.innerHTML = logs.slice(-20).reverse().map(log =>
                    `<div class="log-entry">
                        <span class="log-step">Turn ${{log.step_count}}</span>
                        <span class="log-action">${{JSON.stringify(log.action)}}</span>
                        <span class="log-reward">R: ${{log.reward != null ? log.reward.toFixed(2) : '-'}}</span>
                        ${{log.done ? '<span class="log-done">DONE</span>' : ''}}
                    </div>`
                ).join('');
            }}

            updateConnectionStatus(connected) {{
                const el = document.getElementById('connection-status');
                el.className = connected ? 'status-indicator status-connected' : 'status-indicator status-disconnected';
            }}
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            new CityWebInterface();
        }});
    </script>
</body>
</html>
    """
