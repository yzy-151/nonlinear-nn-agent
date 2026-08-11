"""Run deterministic offline test profiles for local development and CI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAST_MODULES = (
    "tests.test_agent_actions",
    "tests.test_action_loop",
    "tests.test_agent_benchmark_cases",
    "tests.test_agent_benchmark_fixtures",
    "tests.test_agent_benchmark_server",
    "tests.test_benchmark",
    "tests.test_memory_store",
    "tests.test_knowledge_retrieval",
    "tests.test_model_router",
    "tests.test_plan_gate",
    "tests.test_supervisor",
    "tests.test_supervisor_graph",
    "tests.test_supervisor_e2e",
    "tests.test_multi_agent_runtime",
    "tests.test_multi_agent_server",
    "tests.test_coding_agent",
    "tests.test_coding_workflow",
    "tests.test_llm_client",
    "tests.test_execution_agent",
    "tests.test_execution_queue",
    "tests.test_failure_handoff",
    "tests.test_planner_context",
    "tests.test_reporting",
    "tests.test_reporting_tool",
    "tests.test_writing_agent",
    "tests.test_model_plugin_contracts",
    "tests.test_candidate_registry",
    "tests.test_candidate_execution",
    "tests.test_candidate_execution_agent",
    "tests.test_evaluation_statistics",
    "tests.test_reflection_ablation",
    "tests.test_cli",
    "tests.test_web_ui",
    "tests.test_server_streaming",
)


def build_command(profile: str) -> list[str]:
    if profile == "fast":
        return [sys.executable, "-m", "unittest", *FAST_MODULES]
    if profile == "full":
        return [sys.executable, "-m", "unittest", "discover", "tests"]
    raise ValueError(f"Unknown test profile: {profile}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("fast", "full"))
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the unittest command without running it.",
    )
    args = parser.parse_args()
    command = build_command(args.profile)
    if args.list:
        print(" ".join(command))
        return 0

    env = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in (source_path, env.get("PYTHONPATH", "")) if item
    )
    return subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
