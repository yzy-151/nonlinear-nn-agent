from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_candidate_execution import PLUGIN_SOURCE


class CandidateExecutionAgentE2ETest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        candidate_dir = self.root / "models" / "candidates"
        candidate_dir.mkdir(parents=True)
        (candidate_dir / "novel.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
        (candidate_dir / "novel.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "novel_dynamic_model",
                    "entrypoint": "models/candidates/novel.py:NovelPlugin",
                }
            ),
            encoding="utf-8",
        )

    def test_registry_exposes_candidate_tools(self):
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        names = build_experiment_tool_registry(self.root).tool_names()
        self.assertIn("validate_candidate_model", names)
        self.assertIn("run_candidate_model", names)

    def test_execution_agent_validates_and_runs_unlisted_model(self):
        from nonlinear_agent.execution_agent import ExecutionAgent
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        agent = ExecutionAgent(build_experiment_tool_registry(self.root))
        common = {
            "manifest_path": "models/candidates/novel.json",
            "config": {"width": 8},
            "parameter_count_max": 100,
        }
        validation = asyncio.run(
            agent.execute("validate_candidate_model", common)
        )
        self.assertEqual(validation.status, "completed", validation.error)
        self.assertEqual(
            validation.output["descriptor"]["name"], "novel_dynamic_model"
        )

        result = asyncio.run(
            agent.execute(
                "run_candidate_model",
                {
                    **common,
                    "run_id": "agent-unseen-001",
                    "output_dir": "reports/agent-unseen-001",
                    "timeout_seconds": 30,
                },
            )
        )
        self.assertEqual(result.status, "completed", result.error)
        self.assertEqual(result.metrics["nmse_db"], -36.5)
        self.assertEqual(result.metrics["parameter_count"], 80.0)
        self.assertTrue(any(path.endswith("psd.png") for path in result.artifacts))
        self.assertEqual(agent.audit_shell_calls(), 0)

    def test_tool_schema_does_not_accept_arbitrary_command(self):
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        registry = build_experiment_tool_registry(self.root)
        spec = registry.get_tool_spec("run_candidate_model")
        self.assertFalse(spec.input_schema["additionalProperties"])
        self.assertNotIn("command", spec.input_schema["properties"])


if __name__ == "__main__":
    unittest.main()
