"""FastAPI application for Undercover Agent City environment."""

import os
from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from openenv.core.env_server.http_server import create_app
from openenv.core.env_server.web_interface import load_environment_metadata

from ..models import CityAction, CityObservation
from .city_environment import CityEnvironment
from .city_web_interface import get_city_web_interface_html

STATIC_DIR = Path(__file__).parent / "static"


def create_city_environment():
    """Factory function for creating new CityEnvironment instances."""
    return CityEnvironment()


# Check if web interface should be enabled for custom routes
enable_web = os.getenv("ENABLE_WEB_INTERFACE", "false").lower() in ("true", "1", "yes")

app = create_app(
    create_city_environment,
    CityAction,
    CityObservation,
    env_name="undercover-agent-city",
)

# Override the default /web route with our custom spectator interface
# This must be done AFTER create_app to ensure it overrides the default route
if enable_web:
    # Load metadata for custom city interface
    env_instance = create_city_environment()
    metadata = load_environment_metadata(env_instance, "undercover-agent-city")

    # Remove any existing /web GET route and add our custom one
    routes_to_remove = []
    for route in app.routes:
        if hasattr(route, "path") and route.path == "/web":
            if hasattr(route, "methods") and "GET" in route.methods:
                routes_to_remove.append(route)
            elif hasattr(route, "methods") and not route.methods:
                routes_to_remove.append(route)

    for route in routes_to_remove:
        app.routes.remove(route)

    # Add custom city interface route (overrides default /web)
    @app.get("/web", response_class=HTMLResponse)
    async def city_web_interface():
        """Custom city-specific web interface."""
        return get_city_web_interface_html(metadata)

# Spectator UI: serve the isometric spectator view at /spectator
# This is the game-style visualization with animated city, speech bubbles,
# playback controls, and live server connection support.
if STATIC_DIR.exists():
    
    @app.get("/spectator", response_class=FileResponse)
    async def spectator_index():
        """Serve the spectator UI index page."""
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Remove the default "/" redirect so we can serve our own landing page
routes_to_remove = []
for route in app.routes:
    if hasattr(route, "path") and route.path == "/":
        if hasattr(route, "methods") and "GET" in (route.methods or set()):
            routes_to_remove.append(route)
for route in routes_to_remove:
    app.routes.remove(route)


# Landing page at root — shows env info + links to spectator UI and API docs
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page():
    """Landing page with links to spectator UI, API docs, and web interface."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Undercover Agent City — OpenEnv</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a1a;
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 720px;
            padding: 40px 32px;
            text-align: center;
        }
        .badge {
            display: inline-block;
            background: #1a2a4a;
            border: 1px solid #2a4a7a;
            border-radius: 20px;
            padding: 4px 14px;
            font-size: 12px;
            color: #6a9fd8;
            margin-bottom: 20px;
            letter-spacing: 0.5px;
        }
        h1 {
            font-size: 2.4rem;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #4a9eff, #ff4a6a);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            font-size: 1.1rem;
            color: #888;
            margin-bottom: 36px;
            line-height: 1.5;
        }
        .cards {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 36px;
        }
        .card {
            background: #111828;
            border: 1px solid #1e2d4a;
            border-radius: 12px;
            padding: 24px 20px;
            text-decoration: none;
            color: inherit;
            transition: border-color 0.2s, transform 0.2s;
        }
        .card:hover {
            border-color: #4a9eff;
            transform: translateY(-2px);
        }
        .card-icon { font-size: 2rem; margin-bottom: 10px; }
        .card-title { font-size: 1rem; font-weight: 600; margin-bottom: 6px; }
        .card-desc { font-size: 0.82rem; color: #777; line-height: 1.4; }
        .card.primary { border-color: #2a5a9a; background: #0f1e3a; }
        .card.primary:hover { border-color: #4a9eff; }
        .endpoints {
            background: #111828;
            border: 1px solid #1e2d4a;
            border-radius: 12px;
            padding: 20px 24px;
            text-align: left;
            margin-bottom: 28px;
        }
        .endpoints h3 {
            font-size: 0.85rem;
            color: #6a9fd8;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .ep-row {
            display: flex;
            align-items: baseline;
            padding: 5px 0;
            font-size: 0.85rem;
            font-family: 'SF Mono', Monaco, Consolas, monospace;
        }
        .ep-method {
            width: 50px;
            color: #4CAF50;
            font-weight: 600;
        }
        .ep-path { color: #ccc; width: 120px; }
        .ep-desc { color: #666; font-family: -apple-system, sans-serif; }
        .footer {
            font-size: 0.8rem;
            color: #555;
        }
        .footer a { color: #6a9fd8; text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">OpenEnv Compatible</div>
        <h1>Undercover Agent City</h1>
        <p class="subtitle">
            Train an LLM to be a spy. Social deception RL environment with
            persona selection, cover story consistency, and mission progression.
        </p>

        <div class="cards">
            <a class="card primary" href="/spectator">
                <div class="card-icon">&#127918;</div>
                <div class="card-title">Spectator UI</div>
                <div class="card-desc">Watch agents in action with isometric city view, speech bubbles, and playback controls</div>
            </a>
            <a class="card" href="/docs">
                <div class="card-icon">&#128209;</div>
                <div class="card-title">API Docs</div>
                <div class="card-desc">Interactive Swagger docs — try reset, step, and state endpoints</div>
            </a>
            <a class="card" href="/web">
                <div class="card-icon">&#128506;</div>
                <div class="card-title">Grid View</div>
                <div class="card-desc">Live 15x15 grid with trust meters, fact tracker, and action log</div>
            </a>
            <a class="card" href="https://docs.google.com/presentation/d/1BlNIGa1F8K8l5HGxQ14G3P-tcsB2xtTc23yPU0yGSRI/edit?usp=sharing" target="_blank">
                <div class="card-icon">&#128218;</div>
                <div class="card-title">Presentation</div>
                <div class="card-desc">Slide deck with architecture, training results, and design decisions</div>
            </a>
        </div>

        <div class="endpoints">
            <h3>API Endpoints</h3>
            <div class="ep-row"><span class="ep-method">POST</span><span class="ep-path">/reset</span><span class="ep-desc">Start new episode</span></div>
            <div class="ep-row"><span class="ep-method">POST</span><span class="ep-path">/step</span><span class="ep-desc">Take an action</span></div>
            <div class="ep-row"><span class="ep-method">GET</span><span class="ep-path">/state</span><span class="ep-desc">Current game state</span></div>
            <div class="ep-row"><span class="ep-method">GET</span><span class="ep-path">/metadata</span><span class="ep-desc">Environment info</span></div>
            <div class="ep-row"><span class="ep-method">GET</span><span class="ep-path">/health</span><span class="ep-desc">Health check</span></div>
        </div>

        <div class="footer">
            Built by <a href="https://github.com/atharva-deopujari">Atharva Deopujari</a>
            &middot; Meta OpenEnv Hackathon 2026
        </div>
    </div>
</body>
</html>
"""


def main():
    """Entry point for running the server directly."""
    import uvicorn

    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
