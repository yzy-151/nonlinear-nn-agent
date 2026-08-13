import asyncio
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.action_loop import ActionLoopResult
from nonlinear_agent.agent_benchmark import run_agent_task_benchmark, score_agent_task
from nonlinear_agent.agent_benchmark_cases import (
    AgentTaskCase,
    build_nonlinear_agent_task_cases,
    validate_agent_task_catalog,
)


class AgentBenchmarkCasesTest(unittest.TestCase):
    def test_catalog_contains_18_unique_single_domain_tasks_without_variants(self):
        cases = build_nonlinear_agent_task_cases()

        self.assertEqual(len(cases), 18)
        self.assertEqual({case.domain for case in cases}, {"nonlinear-modeling"})
        self.assertEqual(len({case.case_id for case in cases}), 18)
        self.assertFalse(any("-v" in case.case_id for case in cases))
        validate_agent_task_catalog(cases)

    def test_control_and_history_tasks_state_an_explicit_terminal_condition(self):
        cases = {case.case_id: case for case in build_nonlinear_agent_task_cases()}

        self.assertIn("then stop", cases["stop-after-target-hit"].goal.lower())
        self.assertIn("exactly one", cases["hard-action-budget-stop"].goal.lower())
        self.assertIn("then stop", cases["reuse-history-best"].goal.lower())
        self.assertIn("generate", cases["compressed-context-constraint"].goal.lower())

    def test_catalog_rejects_duplicate_semantic_task(self):
        case = AgentTaskCase(
            case_id="one",
            goal="complete experiment",
            category="workflow",
            required_tools=("generate_config",),
        )
        duplicate = AgentTaskCase(
            case_id="two",
            goal="complete experiment",
            category="workflow",
            required_tools=("generate_config",),
        )

        with self.assertRaisesRegex(ValueError, "Duplicate task semantics"):
            validate_agent_task_catalog([case, duplicate])

    def test_score_requires_cross_planner_failure_reference_for_causal_recovery(self):
        case = AgentTaskCase(
            case_id="recover",
            goal="recover training",
            category="recovery",
            required_tools=("run_training", "generate_config"),
            require_causal_recovery=True,
        )
        result = ActionLoopResult(
            status="stopped",
            planner_call_count=3,
            history=[
                {
                    "action_id": "a1",
                    "tool_name": "run_training",
                    "planner_call_id": "p1",
                    "event_id": "a1:failed",
                    "run_status": "failed",
                    "caused_by_event_ids": [],
                },
                {
                    "action_id": "a2",
                    "tool_name": "generate_config",
                    "planner_call_id": "p2",
                    "event_id": "a2:succeeded",
                    "run_status": "succeeded",
                    "caused_by_event_ids": ["a1:failed"],
                },
            ],
        )

        score = score_agent_task(case, result)

        self.assertTrue(score.passed)
        self.assertIn("causal_recovery", score.passed_checks)

    def test_score_fails_when_required_tool_or_artifact_is_missing(self):
        case = AgentTaskCase(
            case_id="report",
            goal="write report",
            category="artifact",
            required_tools=("write_report",),
            required_artifact_suffix="agent-harness-report.md",
        )
        result = ActionLoopResult(
            status="stopped",
            planner_call_count=1,
            history=[],
            artifacts=[],
        )

        score = score_agent_task(case, result)

        self.assertFalse(score.passed)
        self.assertIn("required_tools", score.failed_checks)
        self.assertIn("required_artifact", score.failed_checks)

    def test_seeded_fault_observation_does_not_consume_action_budget(self):
        case = AgentTaskCase(
            case_id="seeded",
            goal="recover",
            category="recovery",
            max_actions=1,
            required_tools=("generate_config",),
            require_rejection=True,
        )
        result = ActionLoopResult(
            status="stopped",
            planner_call_count=1,
            history=[
                {
                    "event_id": "fixture:rejected",
                    "run_status": "rejected",
                    "source": "deterministic_fault_fixture",
                },
                {
                    "event_id": "a1:succeeded",
                    "run_status": "succeeded",
                    "tool_name": "generate_config",
                    "planner_call_id": "p1",
                    "caused_by_event_ids": ["fixture:rejected"],
                },
            ],
        )

        score = score_agent_task(case, result)

        self.assertTrue(score.passed)

    def test_runner_reports_pass_at_1_and_pass_at_3(self):
        case = AgentTaskCase(
            case_id="stable",
            goal="stop safely",
            category="control",
        )
        attempts = 0

        async def execute(_case):
            nonlocal attempts
            attempts += 1
            return ActionLoopResult(
                status="stopped" if attempts >= 2 else "planner_error",
                planner_call_count=1,
            )

        report = asyncio.run(run_agent_task_benchmark([case], execute, attempts=3))

        self.assertEqual(report["task_count"], 1)
        self.assertEqual(report["pass_at_1"], 0.0)
        self.assertEqual(report["pass_at_3"], 1.0)
        self.assertEqual(report["attempt_count"], 3)


if __name__ == "__main__":
    unittest.main()
