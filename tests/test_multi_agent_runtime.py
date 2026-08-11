from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from tests.test_supervisor_e2e import _plan


class TestMultiAgentRuntime(unittest.TestCase):
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
