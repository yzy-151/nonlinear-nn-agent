import asyncio
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.agent_benchmark_fixtures import (
    run_scripted_agent_task_benchmark,
    write_agent_task_benchmark_artifacts,
)


class AgentBenchmarkFixturesTest(unittest.TestCase):
    def test_scripted_fixture_executes_all_independent_tasks(self):
        with TemporaryDirectory() as tmpdir:
            report = asyncio.run(
                run_scripted_agent_task_benchmark(Path(tmpdir), attempts=1)
            )

        self.assertEqual(report["domain"], "nonlinear-modeling")
        self.assertEqual(report["task_count"], 18)
        self.assertEqual(report["pass_at_1"], 1.0)
        self.assertEqual(len(report["results"]), 18)
        self.assertEqual(report["evaluation_mode"], "scripted_fixture")
        first = report["results"][0]
        self.assertIn("history", first)
        self.assertIn("planner_call_id", first["history"][0])
        self.assertIn("observation", first["history"][0])

    def test_artifacts_preserve_case_level_checks_and_provenance(self):
        report = {
            "domain": "nonlinear-modeling",
            "evaluation_mode": "scripted_fixture",
            "task_count": 1,
            "attempt_count": 1,
            "pass_at_1": 1.0,
            "results": [
                {
                    "case_id": "one",
                    "attempt": 1,
                    "passed": True,
                    "passed_checks": ["terminal_status"],
                    "failed_checks": [],
                }
            ],
        }
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            paths = write_agent_task_benchmark_artifacts(output_dir, report)

            saved = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
            markdown = (output_dir / "summary.md").read_text(encoding="utf-8")

        self.assertEqual(saved["evaluation_mode"], "scripted_fixture")
        self.assertIn("one", markdown)
        self.assertIn("terminal_status", markdown)
        self.assertEqual({path.name for path in paths}, {"results.json", "summary.md"})


if __name__ == "__main__":
    unittest.main()
