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


def main():
    """Entry point for running the server directly."""
    import uvicorn

    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
