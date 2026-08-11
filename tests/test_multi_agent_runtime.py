from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from tests.test_supervisor_e2e import _plan, _three_candidate_plan


class TestMultiAgentRuntime(unittest.TestCase):
    def test_writing_worker_refreshes_cost_after_the_writing_model_call(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime
        from tests.test_reporting_tool import _task_source

        class Router:
            cost = 0.1

            def total_cost(self):
                return self.cost

        class Writer:
            def __init__(self, router):
                self.router = router

            def write(self, bundle):
                self.router.cost = 0.25

                class Narrative:
                    def to_dict(self):
                        return {"schema_version": 1, "task_id": bundle.task_id, "sections": {}}

                return Narrative()

        captured = []
        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            router,
            object(),
            Writer(router),
            report_writer=lambda **kwargs: captured.append(kwargs["task_source"]) or {},
        )
        runtime._report_source = lambda request: _task_source()

        runtime._writing_worker({"run_id": "cost-refresh"})

        self.assertEqual(captured[0]["cost_usd"], 0.25)

    def test_idea_plan_repairs_one_non_json_response_with_failure_fact(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        valid = _three_candidate_plan(1)

        class Router:
            def __init__(self):
                self.prompts = []
                self.responses = ["I need more time to think.", json.dumps(valid)]

            def complete(self, role, prompt):
                self.prompts.append((role, prompt))
                return self.responses.pop(0)

        router = Router()
        runtime = MultiAgentRuntime(Path.cwd(), router, object(), object())

        result = runtime._idea_plan(
            {
                "run_id": "repair-plan",
                "goal": "find a compact model",
                "round_index": 1,
                "rounds_total": 3,
                "experiments_per_round": 3,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        self.assertEqual(result["plan_id"], valid["plan_id"])
        self.assertEqual(len(router.prompts), 2)
        self.assertIn("Previous response failed validation", router.prompts[1][1])
        self.assertIn("must contain one JSON object", router.prompts[1][1])

    def test_runtime_prompts_for_three_candidates_and_targets_requested_experiment(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(2, ("fact:round-1:best:r1-exp3",))
        plan["candidate_experiments"][1]["model_type"] = "CompactSinMLP"

        class Router:
            def __init__(self):
                self.prompts = []

            def complete(self, role, prompt):
                self.prompts.append((role, prompt))
                return "```json\n" + json.dumps(plan) + "\n```"

            def total_cost(self):
                return 0.0

        @dataclass(frozen=True)
        class CodingResult:
            passed: bool = True
            task_id: str = ""
            candidate_name: str = ""
            worktree: str = ""
            manifest_path: str = "models/candidates/model/manifest.json"
            applied_files: tuple[str, ...] = ()
            attempt_count: int = 1
            failure_facts: tuple[str, ...] = ()
            validation: dict = None
            metrics: dict = None
            artifacts: tuple[str, ...] = ()
            trace_path: str = ""

        class Coding:
            def __init__(self):
                self.tasks = []

            def generate_candidate(self, task):
                self.tasks.append(task)
                return CodingResult(
                    task_id=task.task_id,
                    candidate_name=task.candidate_name,
                )

        router = Router()
        coding = Coding()
        runtime = MultiAgentRuntime(
            repo_root=Path.cwd(),
            model_router=router,
            coding_agent=coding,
            writing_agent=object(),
        )

        planned = runtime._idea_plan(
            {
                "run_id": "run-3x3",
                "goal": "improve compact nonlinear model",
                "round_index": 2,
                "rounds_total": 3,
                "experiments_per_round": 3,
                "available_fact_refs": ["fact:round-1:best:r1-exp3"],
                "round_records": [],
            }
        )
        candidate = planned["candidate_experiments"][1]
        result = runtime._coding_worker(
            {
                "run_id": "run-3x3",
                "goal": "improve compact nonlinear model",
                "round_index": 2,
                "experiment_id": candidate["experiment_id"],
                "candidate": candidate,
                "plan": planned,
                "prior_facts": [
                    {
                        "experiment_id": "r1-candidate-1",
                        "status": "failed",
                        "metrics": {},
                        "failure_facts": [
                            "TypeError: ArchitectureNode got unexpected keyword id"
                        ],
                    }
                ],
            }
        )

        prompt = router.prompts[0][1]
        self.assertIn("exactly three", prompt)
        self.assertIn("available_fact_refs", prompt)
        self.assertEqual(coding.tasks[0].candidate_name, "compact_sin_mlp")
        self.assertIn("candidate-2", coding.tasks[0].task_id)
        self.assertEqual(result["candidate_name"], "compact_sin_mlp")
        self.assertIn("unexpected keyword id", coding.tasks[0].objective)
        self.assertIn("adapt architecture", coding.tasks[0].objective)
        self.assertTrue(
            any("unexpected keyword id" in item for item in coding.tasks[0].constraints)
        )

    def test_existing_components_are_adapted_into_one_evidence_chain(self):
        from nonlinear_agent.model_router import ModelRouter
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime
        from nonlinear_agent.supervisor_graph import build_multi_agent_graph, run_multi_agent_graph

        class Client:
            provider = "fake"
            model = "idea-model"
            total_prompt_tokens = 0
            total_completion_tokens = 0

            def __init__(self):
                self.prompts = []

            def complete(self, prompt: str) -> str:
                self.prompts.append(prompt)
                self.total_prompt_tokens += 20
                self.total_completion_tokens += 10
                return json.dumps(_plan())

        client = Client()
        router = ModelRouter(
            {"idea_plan": {"provider": "fake", "model": "idea-model"}},
            client_factory=lambda role, config: client,
        )

        @dataclass(frozen=True)
        class CodingResult:
            passed: bool = True
            task_id: str = "run-001"
            candidate_name: str = "adaptive_wavelet_lut"
            worktree: str = ""
            manifest_path: str = "models/candidates/adaptive_wavelet_lut/manifest.json"
            applied_files: tuple[str, ...] = ("models/candidates/adaptive_wavelet_lut/plugin.py",)
            attempt_count: int = 1
            failure_facts: tuple[str, ...] = ()
            validation: dict = None
            metrics: dict = None
            artifacts: tuple[str, ...] = ()
            trace_path: str = "runs/coding-agent/run-001/coding-trace.json"

        class Coding:
            def __init__(self, root: Path):
                self.root = root
                self.tasks = []

            def generate_candidate(self, task):
                self.tasks.append(task)
                return CodingResult(
                    worktree=str(self.root),
                    validation={"descriptor": descriptor, "parameter_count": 128},
                    metrics={},
                )

        class Execution:
            async def execute(self, tool_name, arguments, cancelled=False):
                from nonlinear_agent.execution_agent import ExecutionResult

                self.tool_name = tool_name
                self.arguments = arguments
                return ExecutionResult(
                    status="completed",
                    classification="ok",
                    tool_name=tool_name,
                    metrics={"nmse_db": -37.5, "parameter_count": 128},
                    output={"descriptor": descriptor},
                    artifacts=("reports/run-001/execution/psd.png",),
                )

        class Writer:
            def __init__(self):
                self.bundle = None

            def write(self, bundle):
                self.bundle = bundle
                class Narrative:
                    def to_dict(self):
                        return {"schema_version": 1, "task_id": bundle.task_id, "sections": {}}

                return Narrative()

        descriptor = {
            "name": "adaptive_wavelet_lut",
            "version": "1.0.0",
            "training_mode": "custom",
            "config_schema": {"type": "object", "properties": {}},
            "nodes": [{"node_id": "lut", "label": "Wavelet LUT", "operation": "lookup"}],
            "edges": [],
        }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            coding_root = root / "coding-worktree"
            psd = coding_root / "reports" / "run-001" / "execution" / "psd.png"
            psd.parent.mkdir(parents=True)
            psd.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            coding = Coding(coding_root)
            execution = Execution()
            writer = Writer()
            report_sources = []

            def report_writer(**kwargs):
                report_sources.append(kwargs["task_source"])
                self.assertEqual(Path(kwargs["workspace"]), root.resolve())
                published_psd = root / kwargs["task_source"]["executions"][0]["psd_path"]
                self.assertTrue(published_psd.is_file())
                return {
                    "html_path": "reports/run-001/report.html",
                    "pdf_path": "reports/run-001/report.pdf",
                    "artifacts": ["reports/run-001/report.pdf"],
                }

            runtime = MultiAgentRuntime(
                repo_root=root,
                model_router=router,
                coding_agent=coding,
                writing_agent=writer,
                execution_agent_factory=lambda workspace: execution,
                report_writer=report_writer,
                nmse_threshold_db=-35.0,
            )
            graph = build_multi_agent_graph(
                runtime.workers(), model_router=router
            )
            result = run_multi_agent_graph(
                graph,
                goal="design an unseen compact nonlinear model",
                run_id="run-001",
            )

        self.assertEqual(result["status"], "completed")
        self.assertIn("candidate_experiments", client.prompts[0])
        self.assertIn("required_code_changes", client.prompts[0])
        self.assertIn("failure_facts", client.prompts[0])
        self.assertEqual(coding.tasks[0].candidate_name, "adaptive_wavelet_lut")
        self.assertEqual(execution.tool_name, "run_candidate_model")
        self.assertEqual(
            report_sources[0]["goal"], "design an unseen compact nonlinear model"
        )
        self.assertEqual(report_sources[0]["executions"][0]["nmse_db"], -37.5)
        self.assertEqual(
            report_sources[0]["executions"][0]["model_descriptor"]["name"],
            "adaptive_wavelet_lut",
        )
        self.assertEqual(writer.bundle.architecture.name, "adaptive_wavelet_lut")
        self.assertEqual(result["terminal"]["pdf_path"], "reports/run-001/report.pdf")


if __name__ == "__main__":
    unittest.main()
