import asyncio
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.benchmark import (
    BenchmarkCase,
    BenchmarkCaseResult,
    build_benchmark_summary,
    run_benchmark_cases,
    summarize_loop_result,
    write_benchmark_artifacts,
)
from nonlinear_agent.loop import PlannerLoopResult


class BenchmarkTest(unittest.TestCase):
    def test_build_extended_cases_generates_50_with_threshold_variants(self):
        from nonlinear_agent.benchmark_cases import build_extended_cases

        cases = build_extended_cases(50)
        self.assertEqual(len(cases), 50)
        target_variants = [
            c for c in cases if c.case_id.startswith("target-hit")
        ]
        thresholds = {c.target_nmse_db for c in target_variants}
        self.assertGreaterEqual(len(thresholds), 4)

    def test_summarize_loop_result_counts_statuses_and_target_hit(self):
        case = BenchmarkCase(
            case_id="target-hit",
            goal="reach -35 dB",
            target_nmse_db=-35.0,
            max_rounds=2,
            max_experiments=3,
        )
        loop_result = PlannerLoopResult(
            status="stopped",
            rounds=2,
            history=[
                {"id": "bad-plan", "run_status": "rejected", "error": "rank"},
                {"id": "weak", "run_status": "failed", "nmse_db": -20.0},
                {"id": "best", "run_status": "succeeded", "nmse_db": -36.0, "parameter_count": 128},
            ],
            summaries=["try", "stop"],
        )

        result = summarize_loop_result(case, loop_result)

        self.assertEqual(result.case_id, "target-hit")
        self.assertTrue(result.target_hit)
        self.assertEqual(result.best_experiment_id, "best")
        self.assertEqual(result.best_nmse_db, -36.0)
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.succeeded_count, 1)
        self.assertEqual(result.experiments_used, 2)

    def test_summarize_loop_result_ignores_reflection_records(self):
        case = BenchmarkCase(case_id="reflection", goal="reach -35 dB", target_nmse_db=-35.0)
        loop_result = PlannerLoopResult(
            status="stopped",
            rounds=2,
            history=[
                {"id": "best", "run_status": "succeeded", "nmse_db": -36.0},
                {"id": "reflection-round-001", "run_status": "reflection", "recovery_actions": ["try safer config"]},
            ],
        )

        result = summarize_loop_result(case, loop_result)

        self.assertEqual(result.history_count, 1)
        self.assertEqual(result.succeeded_count, 1)
        self.assertEqual(result.experiments_used, 1)

    def test_build_benchmark_summary_computes_rates(self):
        results = [
            BenchmarkCaseResult(case_id="a", target_hit=True, rejected_count=0, failed_count=1, succeeded_count=1, experiments_used=2),
            BenchmarkCaseResult(case_id="b", target_hit=False, rejected_count=2, failed_count=0, succeeded_count=0, experiments_used=0),
        ]

        summary = build_benchmark_summary(results)

        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["target_hit_rate"], 0.5)
        self.assertEqual(summary["rejected_rate"], 0.5)
        self.assertEqual(summary["runtime_failure_rate"], 0.25)
        self.assertEqual(summary["average_experiments_used"], 1.0)

    def test_summarize_loop_result_computes_self_correction_and_quality_metrics(self):
        case = BenchmarkCase(case_id="multi-round", goal="recover", target_nmse_db=-35.0)
        loop_result = PlannerLoopResult(
            status="stopped",
            rounds=3,
            history=[
                {"id": "r1", "run_status": "rejected", "error": "rank"},
                {"id": "r2", "run_status": "succeeded", "nmse_db": -36.0},
                {"id": "r3", "run_status": "failed", "nmse_db": -20.0},
                {"id": "r4", "run_status": "succeeded", "nmse_db": -37.0},
            ],
            summaries=["a", "b", "c"],
            total_prompt_tokens=100,
            total_completion_tokens=50,
        )

        result = summarize_loop_result(case, loop_result)

        self.assertEqual(result.self_correction_count, 2)
        self.assertEqual(result.planner_success_rate, 0.75)  # 3/4 records passed guard
        self.assertEqual(result.tool_call_correct_rate, 2 / 3)
        self.assertEqual(result.total_prompt_tokens, 100)
        self.assertEqual(result.total_completion_tokens, 50)

    def test_same_planner_batch_failure_then_success_is_not_causal_correction(self):
        case = BenchmarkCase(case_id="same-batch", goal="recover", target_nmse_db=-35.0)
        loop_result = PlannerLoopResult(
            status="stopped",
            rounds=1,
            history=[
                {
                    "id": "bad",
                    "run_status": "failed",
                    "event_id": "event-bad",
                    "planner_call_id": "planner-001",
                    "overrides": {"model_type": "tiny_mlp"},
                },
                {
                    "id": "good",
                    "run_status": "succeeded",
                    "planner_call_id": "planner-001",
                    "caused_by_event_ids": ["event-bad"],
                    "overrides": {"model_type": "complex_lstsq"},
                    "nmse_db": -36.0,
                },
            ],
        )

        result = summarize_loop_result(case, loop_result)

        self.assertEqual(result.self_correction_count, 1)
        self.assertEqual(result.causal_correction_count, 0)
        self.assertEqual(result.causal_correction_success_rate, 0.0)

    def test_later_planner_call_that_consumes_failure_and_changes_candidate_is_causal_correction(self):
        case = BenchmarkCase(case_id="cross-plan", goal="recover", target_nmse_db=-35.0)
        loop_result = PlannerLoopResult(
            status="stopped",
            rounds=2,
            history=[
                {
                    "id": "bad",
                    "run_status": "failed",
                    "event_id": "event-bad",
                    "planner_call_id": "planner-001",
                    "overrides": {"model_type": "tiny_mlp", "learning_rate": 0.1},
                },
                {
                    "id": "good",
                    "run_status": "succeeded",
                    "planner_call_id": "planner-002",
                    "caused_by_event_ids": ["event-bad"],
                    "overrides": {"model_type": "tiny_mlp", "learning_rate": 0.001},
                    "nmse_db": -36.0,
                },
            ],
        )

        result = summarize_loop_result(case, loop_result)

        self.assertEqual(result.causal_correction_count, 1)
        self.assertEqual(result.causal_correction_success_rate, 1.0)

    def test_build_benchmark_summary_includes_extended_metrics(self):
        results = [
            BenchmarkCaseResult(
                case_id="a", target_hit=True, succeeded_count=2,
                failed_count=1, rejected_count=1, experiments_used=3,
                rounds=2, self_correction_count=1,
                planner_success_rate=0.75, tool_call_correct_rate=2 / 3,
                total_prompt_tokens=100, total_completion_tokens=50,
                estimated_cost_usd=0.01,
            ),
        ]
        summary = build_benchmark_summary(results)
        self.assertIn("planner_success_rate", summary)
        self.assertIn("average_rounds", summary)
        self.assertEqual(summary["self_correction_count"], 1)
        self.assertEqual(summary["total_prompt_tokens"], 100)
        self.assertEqual(summary["total_completion_tokens"], 50)
        self.assertAlmostEqual(summary["estimated_cost_usd"], 0.01)

    def test_build_benchmark_summary_reports_causal_correction_metrics(self):
        results = [
            BenchmarkCaseResult(
                case_id="a",
                causal_correction_count=2,
                causal_correction_attempt_count=3,
                causal_correction_success_rate=2 / 3,
            ),
            BenchmarkCaseResult(
                case_id="b",
                causal_correction_count=1,
                causal_correction_attempt_count=1,
                causal_correction_success_rate=1.0,
            ),
        ]

        summary = build_benchmark_summary(results)

        self.assertEqual(summary["causal_correction_count"], 3)
        self.assertEqual(summary["causal_correction_attempt_count"], 4)
        self.assertEqual(summary["causal_correction_success_rate"], 0.75)

    def test_run_benchmark_cases_uses_executor(self):
        cases = [
            BenchmarkCase(case_id="case-001", goal="run", target_nmse_db=-35.0),
        ]

        async def execute_case(case):
            return PlannerLoopResult(
                status="stopped",
                rounds=1,
                history=[{"id": "exp", "run_status": "succeeded", "nmse_db": -36.0}],
                summaries=[],
            )

        results, summary = asyncio.run(run_benchmark_cases(cases, execute_case))

        self.assertEqual(results[0].case_id, "case-001")
        self.assertTrue(results[0].target_hit)
        self.assertEqual(summary["target_hit_rate"], 1.0)

    def test_write_benchmark_artifacts(self):
        results = [
            BenchmarkCaseResult(case_id="case-001", target_hit=True, best_nmse_db=-36.0, best_experiment_id="exp-a"),
            BenchmarkCaseResult(case_id="case-002", target_hit=False, best_nmse_db=-20.0, best_experiment_id="exp-b"),
        ]
        summary = build_benchmark_summary(results)

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "benchmark"
            write_benchmark_artifacts(output_dir, results, summary)

            payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
            leaderboard = (output_dir / "leaderboard.csv").read_text(encoding="utf-8")
            markdown = (output_dir / "summary.md").read_text(encoding="utf-8")

        self.assertEqual(payload["summary"]["case_count"], 2)
        self.assertIn("case-001", leaderboard)
        self.assertIn("target_hit_rate", markdown)
        self.assertIn("causal_correction_success_rate", markdown)


if __name__ == "__main__":
    unittest.main()
