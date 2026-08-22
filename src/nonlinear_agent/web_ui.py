from __future__ import annotations

from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent / "web"
WEB_ASSETS = {
    "index.html": "text/html; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "event_view_model.js": "text/javascript; charset=utf-8",
    "logo.svg": "image/svg+xml",
}


def read_web_asset(name: str) -> str:
    """Read a packaged Web UI asset from an explicit allowlist."""
    if name not in WEB_ASSETS:
        raise FileNotFoundError(name)
    return (WEB_ROOT / name).read_text(encoding="utf-8")


def render_home_page() -> str:
    return read_web_asset("index.html")
