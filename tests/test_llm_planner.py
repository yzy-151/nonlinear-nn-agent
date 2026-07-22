import asyncio
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.llm import FakeLLMClient, OpenAICompatibleClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.trace import TraceEvent


class LLMPlannerTest(unittest.TestCase):
    def test_deepseek_client_defaults_to_openai_compatible_endpoint(self):
        client = OpenAICompatibleClient.deepseek(api_key="test-key")

        self.assertEqual(client.base_url, "https://api.deepseek.com")
        self.assertEqual(client.model, "deepseek-v4-flash")
        self.assertEqual(client.api_key, "test-key")

    def test_planner_parses_llm_json_into_experiment_plan(self):
        llm = FakeLLMClient(
            responses=[
                '{"summary":"try longer memory", "stop": false, "experiments": ['
                '{"id":"exp-o10-m180", "reason":"test deeper memory", '
                '"overrides":{"model_type":"complex_lstsq", "memory_depth":180, "mp_order_count":10}}]}'
            ]
        )
        planner = ExperimentPlanner(llm_client=llm, allowed_tools=["generate_config", "run_training"])

        plan = planner.plan(
            goal="Find best NMSE under 4000 parameters",
            history=[{"id": "baseline", "nmse_db": -37.42}],
            constraints={"parameter_count_max": 4000},
        )

        self.assertFalse(plan.stop)
        self.assertEqual(plan.summary, "try longer memory")
        self.assertEqual(plan.experiments[0].experiment_id, "exp-o10-m180")
        self.assertEqual(plan.experiments[0].overrides["memory_depth"], 180)
        self.assertIn("Find best NMSE", llm.last_prompt)

    def test_planner_loop_runs_plan_observe_cycle_until_stop(self):
        llm = FakeLLMClient(
            responses=[
                '{"summary":"run first candidate", "stop": false, "experiments": ['
                '{"id":"candidate-001", "reason":"baseline candidate", '
                '"overrides":{"output_dir":"reports/candidate-001", "epochs":0}}]}',
                '{"summary":"target reached", "stop": true, "experiments": []}',
            ]
        )
        planner = ExperimentPlanner(llm_client=llm)
        executed_sessions = []

        class FakeRuntime:
            async def run(self, request):
                executed_sessions.append(request.session_id)
                yield TraceEvent(session_id=request.session_id, event_type="start", status="running")
                yield TraceEvent(
                    session_id=request.session_id,
                    event_type="metric",
                    status="succeeded",
                    payload={"name": "nmse_db", "value": -38.0},
                )
                yield TraceEvent(
                    session_id=request.session_id,
                    event_type="metric",
                    status="succeeded",
                    payload={"name": "parameter_count", "value": 3600},
                )
                yield TraceEvent(session_id=request.session_id, event_type="complete", status="succeeded")

        with TemporaryDirectory() as tmpdir:
            loop = ExperimentPlannerLoop(
                planner=planner,
                workspace=Path(tmpdir),
                runtime_factory=lambda session_id: FakeRuntime(),
            )
            result = asyncio.run(loop.run(goal="Improve NMSE under 4000 params", max_rounds=3))

        self.assertEqual(executed_sessions, ["candidate-001"])
        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.history[0]["nmse_db"], -38.0)
        self.assertEqual(result.rounds, 2)

    def test_planner_prompt_exposes_physics_informed_design_space(self):
        llm = FakeLLMClient(responses=['{"summary":"stop", "stop": true, "experiments": []}'])
        planner = ExperimentPlanner(llm_client=llm)

        planner.plan(
            goal="Try spline LUT activation and shallow nonlinear models",
            history=[],
            constraints={"parameter_count_max": 4000},
        )

        self.assertIn("spline_mlp", llm.last_prompt)
        self.assertIn("1D LUT", llm.last_prompt)
        self.assertIn("16", llm.last_prompt)
        self.assertIn("complex_lstsq", llm.last_prompt)
        self.assertIn("activation", llm.last_prompt)
    def test_planner_loop_marks_error_event_as_failed_run_status(self):
        llm = FakeLLMClient(
            responses=[
                '{"summary":"run weak candidate", "stop": false, "experiments": ['
                '{"id":"weak-001", "reason":"expected to fail threshold", '
                '"overrides":{"output_dir":"reports/weak-001", "epochs":0}}]}',
                '{"summary":"stop", "stop": true, "experiments": []}',
            ]
        )
        planner = ExperimentPlanner(llm_client=llm)

        class FakeRuntime:
            async def run(self, request):
                yield TraceEvent(session_id=request.session_id, event_type="metric", payload={"name": "nmse_db", "value": -3.0})
                yield TraceEvent(session_id=request.session_id, event_type="error", error="NMSE threshold failed")

        with TemporaryDirectory() as tmpdir:
            loop = ExperimentPlannerLoop(
                planner=planner,
                workspace=Path(tmpdir),
                runtime_factory=lambda session_id: FakeRuntime(),
            )
            result = asyncio.run(loop.run(goal="test failed experiment status", max_rounds=2))

        self.assertEqual(result.history[0]["run_status"], "failed")
        self.assertEqual(result.history[0]["error"], "NMSE threshold failed")

if __name__ == "__main__":
    unittest.main()


