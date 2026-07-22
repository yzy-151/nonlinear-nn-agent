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


if __name__ == "__main__":
    unittest.main()
