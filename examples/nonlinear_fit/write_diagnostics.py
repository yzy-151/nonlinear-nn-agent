from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.diagnostics import write_diagnostics_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the Agent Runtime diagnostics dashboard.")
    parser.add_argument("--workspace", default=str(PROJECT_ROOT))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    output = write_diagnostics_report(args.workspace, args.output)
    print(output)


if __name__ == "__main__":
    main()
