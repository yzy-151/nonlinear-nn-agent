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
    def test_reflection_policy_extracts_facts_without_strategy_outputs(self):
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
        self.assertNotIn("recovery_actions", reflection)
        self.assertNotIn("avoid_next", reflection)
        self.assertEqual(reflection["facts"][0]["id"], "bad-rank")
        self.assertEqual(reflection["facts"][0]["status"], "rejected")
        self.assertEqual(reflection["facts"][0]["error"], "Unsupported planner override fields: rank")
        self.assertEqual(reflection["facts"][1]["id"], "weak")
        self.assertEqual(reflection["facts"][1]["nmse_db"], -20.0)
        self.assertEqual(reflection["facts"][2]["id"], "good")
        self.assertEqual(reflection["facts"][2]["parameter_count"], 128)

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

    def test_planner_loop_feeds_reflection_record_into_next_round_history(self):
        llm = FakeLLMClient(
            responses=[
                '{"summary":"bad plan", "stop": false, "experiments": ['
                '{"id":"bad-rank", "reason":"schema test", "overrides":{"rank":100}}]}',
                '{"summary":"stop after seeing reflection", "stop": true, "experiments": []}',
            ]
        )
        planner = ExperimentPlanner(llm_client=llm)

        with TemporaryDirectory() as tmpdir:
            loop = ExperimentPlannerLoop(
                planner=planner,
                workspace=Path(tmpdir),
            )
            result = asyncio.run(loop.run(goal="use reflection", max_rounds=2))

        self.assertTrue(any(record.get("run_status") == "reflection" for record in result.history))
        self.assertIn("reflection-round-001", llm.last_prompt)
        self.assertIn("facts", llm.last_prompt)
        self.assertNotIn("recovery_actions", llm.last_prompt)
        self.assertNotIn("avoid_next", llm.last_prompt)


if __name__ == "__main__":
    unittest.main()
