from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.test_candidate_execution import PLUGIN_SOURCE
from tests.test_coding_agent import _init_repo


def _response(source: str, candidate_name: str = "novel_dynamic_model") -> str:
    base = f"models/candidates/{candidate_name}"
    return json.dumps(
        {
            "schema_version": 1,
            "task_id": "coding-task-001",
            "candidate_name": candidate_name,
            "rationale": "Exercise a previously unlisted architecture.",
            "manifest_path": f"{base}/manifest.json",
            "files": {
                f"{base}/plugin.py": source,
                f"{base}/manifest.json": json.dumps(
                    {
                        "schema_version": 1,
                        "name": candidate_name,
                        "entrypoint": f"{base}/plugin.py:NovelPlugin",
                    }
                ),
            },
        }
    )


class _RouterStub:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, role: str, prompt: str) -> str:
        self.calls.append((role, prompt))
        return self.responses.pop(0)


class CodingWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        _init_repo(self.repo)

    def _task(self):
        from nonlinear_agent.coding_agent import CodingTaskSpec

        return CodingTaskSpec(
            task_id="coding-task-001",
            objective="Create and train an unlisted nonlinear model plugin.",
            candidate_name="novel_dynamic_model",
            config={"width": 8},
            parameter_count_max=100,
            smoke_timeout_seconds=30.0,
        )

    def test_plan_parser_accepts_complete_unknown_model_plugin(self):
        from nonlinear_agent.coding_agent import CodeChangePlan

        plan = CodeChangePlan.from_json(_response(PLUGIN_SOURCE), self._task())
        self.assertEqual(plan.candidate_name, "novel_dynamic_model")
        self.assertEqual(len(plan.files), 2)
        self.assertTrue(plan.manifest_path.endswith("manifest.json"))

    def test_plan_parser_rejects_markdown_and_path_escape(self):
        from nonlinear_agent.coding_agent import CodeChangePlan

        with self.assertRaisesRegex(ValueError, "JSON object"):
            CodeChangePlan.from_json(
                "```json\n" + _response(PLUGIN_SOURCE) + "\n```", self._task()
            )

        payload = json.loads(_response(PLUGIN_SOURCE))
        payload["files"]["../escape.py"] = "VALUE = 1\n"
        with self.assertRaisesRegex(ValueError, "candidate directory"):
            CodeChangePlan.from_json(json.dumps(payload), self._task())

    def test_static_gate_rejects_process_access_and_import_side_effect(self):
        from nonlinear_agent.coding_agent import inspect_candidate_source

        errors = inspect_candidate_source(
            "import subprocess\nsubprocess.run(['whoami'])\n"
        )
        self.assertTrue(any("subprocess" in error for error in errors))
        self.assertTrue(any("top-level" in error for error in errors))

    def test_llm_repairs_invalid_code_then_runner_executes_complete_plugin(self):
        from nonlinear_agent.coding_agent import CodingAgent

        router = _RouterStub(
            [
                _response("class NovelPlugin:\n    def broken(\n"),
                _response(PLUGIN_SOURCE),
            ]
        )
        agent = CodingAgent(repo_root=self.repo, model_router=router)
        result = agent.generate_candidate(self._task(), max_repairs=2)
        self.addCleanup(agent.cleanup_worktree)

        self.assertTrue(result.passed, result.failure_facts)
        self.assertEqual(result.attempt_count, 2)
        self.assertEqual(result.metrics["nmse_db"], -36.5)
        self.assertEqual(result.metrics["parameter_count"], 80.0)
        self.assertTrue(any(path.endswith("psd.png") for path in result.artifacts))
        self.assertTrue(any("SyntaxError" in fact for fact in result.failure_facts))
        self.assertEqual([role for role, _ in router.calls], ["coding", "coding"])
        self.assertIn("SyntaxError", router.calls[1][1])
        self.assertNotIn("DEEPSEEK_API_KEY", router.calls[1][1])
        trace_file = Path(result.worktree) / result.trace_path
        self.assertTrue(trace_file.is_file())
        trace = json.loads(trace_file.read_text(encoding="utf-8"))
        self.assertTrue(trace["attempts"][0]["files"])
        self.assertNotIn(PLUGIN_SOURCE, trace_file.read_text(encoding="utf-8"))

    def test_failed_repairs_return_facts_without_executing_arbitrary_command(self):
        from nonlinear_agent.coding_agent import CodingAgent

        router = _RouterStub([_response("import os\n") for _ in range(3)])
        agent = CodingAgent(repo_root=self.repo, model_router=router)
        result = agent.generate_candidate(self._task(), max_repairs=2)
        self.addCleanup(agent.cleanup_worktree)

        self.assertFalse(result.passed)
        self.assertEqual(result.attempt_count, 3)
        self.assertTrue(any("forbidden import" in fact for fact in result.failure_facts))
        self.assertEqual(result.metrics, {})
        self.assertEqual(result.artifacts, ())


if __name__ == "__main__":
    unittest.main()
