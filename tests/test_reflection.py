import asyncio
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.reflection import ReflectionPolicy
from nonlinear_agent.trace import TraceEvent


class ReflectionTest(unittest.TestCase):
    def test_reflection_policy_summarizes_failures_and_recovery_actions(self):
        history = [
            {"id": "bad-rank", "run_status": "rejected", "error": "Unsupported planner override fields: rank"},
            {"id": "weak", "run_status": "failed", "error": "NMSE threshold failed", "nmse_db": -20.0},
            {"id": "good", "run_status": "succeeded", "nmse_db": -36.0, "parameter_count": 128},
        ]

        reflection = ReflectionPolicy().reflect(round_index=2, round_records=history)

        self.assertEqual(reflection["round"], 2)
        self.assertEqual(reflection["status_counts"]["rejected"], 1)
        self.assertEqual(reflection["status_counts"]["failed"], 1)
        self.assertEqual(reflection["status_counts"]["succeeded"], 1)
        self.assertIn("schema", " ".join(reflection["failure_causes"]).lower())
        self.assertIn("unsupported fields", " ".join(reflection["recovery_actions"]).lower())
        self.assertIn("avoid", " ".join(reflection["avoid_next"]).lower())

    def test_planner_loop_records_reflections_and_writes_artifacts(self):
        llm = FakeLLMClient(
            responses=[
                '{"summary":"bad plan", "stop": false, "experiments": ['
                '{"id":"bad-rank", "reason":"schema test", "overrides":{"rank":100}},'
                '{"id":"weak", "reason":"runtime failure test", "overrides":{"epochs":0}}]}',
                '{"summary":"stop after reflection", "stop": true, "experiments": []}',
            ]
        )
        planner = ExperimentPlanner(llm_client=llm)

        class FakeRuntime:
            async def run(self, request):
                yield TraceEvent(
                    session_id=request.session_id,
                    event_type="metric",
                    payload={"name": "nmse_db", "value": -20.0},
                )
                yield TraceEvent(session_id=request.session_id, event_type="error", error="NMSE threshold failed")

        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "runs" / "reflection"
            loop = ExperimentPlannerLoop(
                planner=planner,
                workspace=Path(tmpdir),
                runtime_factory=lambda session_id: FakeRuntime(),
                artifact_dir=run_dir,
            )
            result = asyncio.run(loop.run(goal="reflect on failures", max_rounds=2))

            reflection_payload = json.loads((run_dir / "reflections" / "round-001.json").read_text(encoding="utf-8"))
            result_payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))

        self.assertEqual(result.reflections[0]["round"], 1)
        self.assertEqual(reflection_payload["status_counts"]["rejected"], 1)
        self.assertEqual(reflection_payload["status_counts"]["failed"], 1)
        self.assertEqual(result_payload["reflections"][0]["round"], 1)


if __name__ == "__main__":
    unittest.main()
