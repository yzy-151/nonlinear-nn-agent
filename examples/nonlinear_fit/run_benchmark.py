"""CLI entry for the 10-case Agent Benchmark.

Case definitions and executors live in `nonlinear_agent.benchmark_cases`
so the CLI and the Web UI always evaluate the same cases.

Usage:
  python examples/nonlinear_fit/run_benchmark.py --provider fake
  python examples/nonlinear_fit/run_benchmark.py --provider deepseek
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.benchmark import (  # noqa: E402
    run_benchmark_cases,
    write_benchmark_artifacts,
)
from nonlinear_agent.benchmark_cases import (  # noqa: E402
    build_extended_cases,
    execute_case,
)


def _load_env(workspace: Path) -> None:
    """Load .env.local keys (e.g. LLM API key) without overriding existing env."""
    env_path = workspace / ".env.local"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


async def run(args) -> None:
    cases = build_extended_cases(args.case_count)
    results, summary = await run_benchmark_cases(
        cases,
        lambda case: execute_case(
            case,
            provider=args.provider,
            workspace=PROJECT_ROOT,
            timeout_seconds=args.timeout_seconds,
            planner_retries=2 if args.provider == "deepseek" else 0,
        ),
    )
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    write_benchmark_artifacts(output_dir, results, summary)
    summary["provider"] = args.provider
    print(json.dumps(
        {"summary": summary, "output_dir": str(output_dir)},
        ensure_ascii=False,
        indent=2,
    ))


def main() -> None:
    _load_env(PROJECT_ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="benchmarks/fake-v08")
    parser.add_argument("--provider", choices=["fake", "deepseek"], default="fake",
                        help="LLM provider: fake (offline) or deepseek (real LLM + real training)")
    parser.add_argument("--timeout-seconds", type=float, default=36000.0,
                        help="Per-trial training timeout (default 36000s).")
    parser.add_argument("--case-count", type=int, default=50,
                        help="Number of benchmark cases (10 canonical + parameterized variants).")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
