from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.mcp_server import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or [str(PROJECT_ROOT)]))
