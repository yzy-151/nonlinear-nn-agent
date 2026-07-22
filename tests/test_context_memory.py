import asyncio
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.context_memory import HistoryCompressor
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.trace import TraceEvent


class ContextMemoryTest(unittest.TestCase):
    def test_history_compressor_keeps_summary_and_recent_records(self):
        history = [
            {"id": "old-rejected", "run_status": "rejected", "error": "rank", "nmse_db": None},
            {"id": "old-failed", "run_status": "failed", "error": "threshold", "nmse_db": -20.0},
            {"id": "old-success", "run_status": "succeeded", "nmse_db": -36.0, "parameter_count": 128},
            {"id": "recent-1", "run_status": "failed", "nmse_db": -30.0},
            {"id": "recent-2", "run_status": "succeeded", "nmse_db": -37.0, "parameter_count": 256},
        ]

        compressed = HistoryCompressor(recent_window=2).build_prompt_history(history)

        self.assertEqual(len(compressed), 3)
        self.assertEqual(compressed[0]["id"], "history-summary")
        self.assertEqual(compressed[0]["covered_records"], 3)
        self.assertEqual(compressed[0]["status_counts"]["rejected"], 1)
        self.assertEqual(compressed[0]["status_counts"]["failed"], 1)
        self.assertEqual(compressed[0]["status_counts"]["succeeded"], 1)
        self.assertEqual(compressed[0]["best_nmse_db"], -36.0)
        self.assertIn("old-rejected", compressed[0]["notable_errors"][0])
        self.assertEqual([record["id"] for record in compressed[1:]], ["recent-1", "recent-2"])

    def test_history_compressor_preserves_short_history(self):
        history = [{"id": "a"}, {"id": "b"}]

        compressed = HistoryCompressor(recent_window=3).build_prompt_history(history)

        self.assertEqual(compressed, history)
        self.assertIsNot(compressed, history)

    def test_planner_loop_sends_compressed_history_to_planner(self):
        responses = [
            '{"summary":"round1", "stop": false, "experiments": ['
            '{"id":"exp-001", "reason":"old", "overrides":{"epochs":0}}]}',
            '{"summary":"round2", "stop": false, "experiments": ['
            '{"id":"exp-002", "reason":"old", "overrides":{"epochs":0}}]}',
            '{"summary":"round3", "stop": false, "experiments": ['
            '{"id":"exp-003", "reason":"old", "overrides":{"epochs":0}}]}',
            '{"summary":"round4", "stop": true, "experiments": []}',
        ]
        llm = FakeLLMClient(responses=responses)
        planner = ExperimentPlanner(llm_client=llm)

        class FakeRuntime:
            async def run(self, request):
                yield TraceEvent(
                    session_id=request.session_id,
                    event_type="metric",
                    payload={"name": "nmse_db", "value": -30.0},
                )

        with TemporaryDirectory() as tmpdir:
            loop = ExperimentPlannerLoop(
                planner=planner,
                workspace=Path(tmpdir),
                runtime_factory=lambda session_id: FakeRuntime(),
                history_compressor=HistoryCompressor(recent_window=1),
            )
            result = asyncio.run(loop.run(goal="compress history", max_rounds=4))

        self.assertEqual(result.status, "stopped")
        self.assertIn("history-summary", llm.last_prompt)
        self.assertIn("exp-003", llm.last_prompt)
        self.assertNotIn("exp-001\", \"reason\"", llm.last_prompt)


if __name__ == "__main__":
    unittest.main()
