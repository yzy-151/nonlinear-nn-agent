"""TDD tests for v3.8.0 Execution Agent: tool-only execution + failure taxonomy."""

from __future__ import annotations

import asyncio
import unittest

from nonlinear_agent.tools import ToolRegistry, ToolSpec


def _registry() -> ToolRegistry:
    registry = ToolRegistry()

    def good_tool(value: int = 1):
        return {
            "metrics": {"nmse_db": -36.0},
            "artifacts": ["runs/e1/result.json"],
            "context_summary": "ok",
        }

    def nan_tool():
        return {"metrics": {"nmse_db": float("nan")}, "context_summary": "nan"}

    def timeout_tool():
        raise TimeoutError("training timeout")

    def oom_tool():
        raise MemoryError("out of memory")

    def missing_artifact_tool():
        return {"artifacts": []}

    registry.register("run_good", good_tool, ToolSpec(name="run_good"))
    registry.register("run_nan", nan_tool, ToolSpec(name="run_nan"))
    registry.register("run_timeout", timeout_tool, ToolSpec(name="run_timeout"))
    registry.register("run_oom", oom_tool, ToolSpec(name="run_oom"))
    registry.register("run_missing_artifact", missing_artifact_tool, ToolSpec(name="run_missing_artifact"))
    return registry


class TestExecutionAgent(unittest.TestCase):
    def test_only_registered_tools_can_execute(self):
        from nonlinear_agent.execution_agent import ExecutionAgent

        agent = ExecutionAgent(_registry())
        with self.assertRaises(ValueError):
            asyncio.run(agent.execute("unregistered_tool", {}))

    def test_shell_invocation_count_zero(self):
        from nonlinear_agent.execution_agent import ExecutionAgent

        agent = ExecutionAgent(_registry())
        asyncio.run(agent.execute("run_good", {"value": 1}))
        self.assertEqual(agent.audit_shell_calls(), 0)

    def test_completed_terminal_state(self):
        from nonlinear_agent.execution_agent import ExecutionAgent

        agent = ExecutionAgent(_registry())
        result = asyncio.run(agent.execute("run_good", {}))
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.classification, "ok")

    def test_failure_taxonomy_unique_terminal_states(self):
        from nonlinear_agent.execution_agent import ExecutionAgent

        agent = ExecutionAgent(_registry())
        cases = {
            "run_timeout": ("failed", "timeout"),
            "run_oom": ("failed", "oom"),
            "run_nan": ("failed", "nan"),
            "run_missing_artifact": ("failed", "missing_artifact"),
        }
        for tool, (status, classification) in cases.items():
            result = asyncio.run(agent.execute(tool, {}))
            self.assertEqual(result.status, status, tool)
            self.assertEqual(result.classification, classification, tool)

    def test_cancel_yields_cancelled_terminal_state(self):
        from nonlinear_agent.execution_agent import ExecutionAgent

        agent = ExecutionAgent(_registry())
        result = asyncio.run(agent.execute("run_good", {}, cancelled=True))
        self.assertEqual(result.status, "cancelled")


if __name__ == "__main__":
    unittest.main()
