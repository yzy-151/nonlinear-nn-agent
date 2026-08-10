"""TDD tests for v3.8.x: ExecutionQueue (concurrency + resume) and budgets."""

from __future__ import annotations

import asyncio
import time
import unittest

from nonlinear_agent.tools import ToolRegistry, ToolSpec


def _registry() -> ToolRegistry:
    registry = ToolRegistry()

    def slow_tool(value: int = 1):
        time.sleep(0.05)
        return {"metrics": {"nmse_db": -36.0}, "artifacts": [f"runs/e{value}"]}

    registry.register("run_slow", slow_tool, ToolSpec(name="run_slow"))
    return registry


class TestExecutionQueue(unittest.TestCase):
    def test_queue_runs_all_tasks_under_concurrency_limit(self):
        from nonlinear_agent.execution_agent import ExecutionAgent
        from nonlinear_agent.execution_queue import ExecutionQueue, QueueTask

        agent = ExecutionAgent(_registry())
        queue = ExecutionQueue(agent=agent, max_concurrency=2)
        tasks = [
            QueueTask(task_id=f"t{i}", tool_name="run_slow", arguments={"value": i})
            for i in range(5)
        ]
        results = asyncio.run(queue.run(tasks))
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r.result.status == "completed" for r in results))
        self.assertTrue(all(not r.resumed for r in results))

    def test_resume_skips_already_completed_tasks(self):
        from nonlinear_agent.execution_agent import ExecutionAgent
        from nonlinear_agent.execution_queue import ExecutionQueue, QueueTask

        agent = ExecutionAgent(_registry())
        first = [
            QueueTask(task_id="t1", tool_name="run_slow", arguments={"value": 1}),
            QueueTask(task_id="t2", tool_name="run_slow", arguments={"value": 2}),
        ]
        queue = ExecutionQueue(agent=agent)
        asyncio.run(queue.run(first))

        second = [
            QueueTask(task_id="t1", tool_name="run_slow", arguments={"value": 1}),
            QueueTask(task_id="t3", tool_name="run_slow", arguments={"value": 3}),
        ]
        results = asyncio.run(queue.run(second))
        by_id = {r.task_id: r for r in results}
        self.assertTrue(by_id["t1"].resumed)
        self.assertFalse(by_id["t3"].resumed)

    def test_execution_agent_max_executions_budget(self):
        from nonlinear_agent.execution_agent import ExecutionAgent

        agent = ExecutionAgent(_registry(), max_executions=1)
        first = asyncio.run(agent.execute("run_slow", {}))
        self.assertEqual(first.status, "completed")
        second = asyncio.run(agent.execute("run_slow", {}))
        self.assertEqual(second.status, "failed")
        self.assertEqual(second.classification, "budget_exceeded")


if __name__ == "__main__":
    unittest.main()
