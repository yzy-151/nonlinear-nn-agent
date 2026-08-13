import asyncio
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.agent_benchmark_fixtures import (
    build_initial_fault_history,
    run_llm_agent_task_benchmark,
    run_scripted_agent_task_benchmark,
    write_agent_task_benchmark_artifacts,
)


class AgentBenchmarkFixturesTest(unittest.TestCase):
    def test_fault_history_exposes_recovery_event_as_initial_observation(self):
        from nonlinear_agent.agent_benchmark_cases import AgentTaskCase

        case = AgentTaskCase(
            case_id="recover",
            goal="recover",
            category="recovery",
            fault="training_error",
        )
        history = build_initial_fault_history(case)

        self.assertEqual(history[0]["event_id"], "fixture-training_error:failed")
        self.assertEqual(history[0]["run_status"], "failed")

    def test_target_hit_case_starts_with_verified_metric_observation(self):
        from nonlinear_agent.agent_benchmark_cases import build_nonlinear_agent_task_cases

        case = next(
            case for case in build_nonlinear_agent_task_cases()
            if case.case_id == "stop-after-target-hit"
        )
        history = build_initial_fault_history(case)

        self.assertEqual(history[0]["run_status"], "succeeded")
        self.assertEqual(history[0]["tool_name"], "verify_artifacts")
        self.assertLessEqual(history[0]["observation"]["metrics"]["nmse_db"], -35.0)

    def test_historical_best_fact_includes_structured_metric_evidence(self):
        from nonlinear_agent.agent_benchmark_cases import build_nonlinear_agent_task_cases

        case = next(
            case for case in build_nonlinear_agent_task_cases()
            if case.case_id == "reuse-history-best"
        )
        history = build_initial_fault_history(case)

        self.assertEqual(history[0]["observation"]["metrics"]["nmse_db"], -42.26)
        self.assertIn("evidence_id", history[0]["observation"])

    def test_llm_runner_uses_real_planner_path_with_injected_client(self):
        from nonlinear_agent.agent_benchmark_cases import AgentTaskCase
        from nonlinear_agent.llm import FakeLLMClient

        case = AgentTaskCase(
            case_id="config",
            goal="Generate a config then stop.",
            category="workflow",
            required_tools=("generate_config",),
        )

        def client_factory():
            return FakeLLMClient(responses=[
                '{"type":"tool_call","action_id":"a1","reason":"do it",'
                '"tool":"generate_config","arguments":{"base_config_path":'
                '"configs/baselines/fixture.yaml","experiment_id":"config",'
                '"overrides":{"output_dir":"reports/config"}},'
                '"caused_by_event_ids":[]}',
                '{"type":"stop","action_id":"a2","reason":"done",'
                '"caused_by_event_ids":[]}',
            ])

        with TemporaryDirectory() as tmpdir:
            report = asyncio.run(run_llm_agent_task_benchmark(
                Path(tmpdir), attempts=1, cases=[case],
                client_factory=client_factory,
            ))

        self.assertEqual(report["evaluation_mode"], "real_llm_fault_fixture")
        self.assertEqual(report["pass_at_1"], 1.0)
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
