import asyncio
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.action_loop import ActionPlannerLoop
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend
from nonlinear_agent.memory.ports import MemoryKind
from nonlinear_agent.planner import AgentActionPlanner
from nonlinear_agent.runtime import ExperimentHarnessRuntime
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolRegistry, ToolSpec
from nonlinear_agent.trace import TraceLogger


def _action(action_id, tool=None, arguments=None, caused_by=None, stop=False):
    if stop:
        return (
            '{"type":"stop","action_id":"%s","reason":"done",'
            '"caused_by_event_ids":[]}' % action_id
        )
    return (
        '{"type":"tool_call","action_id":"%s","reason":"next",'
        '"tool":"%s","arguments":%s,"caused_by_event_ids":%s}'
        % (
            action_id,
            tool,
            __import__("json").dumps(arguments or {}),
            __import__("json").dumps(caused_by or []),
        )
    )


class ActionPlannerLoopTest(unittest.TestCase):
    def _runtime_factory(self, root, registry):
        return lambda session_id: ExperimentHarnessRuntime(
            tool_registry=registry,
            session_store=SessionStore(root / "sessions"),
            trace_logger=TraceLogger(root / "traces" / f"{session_id}.jsonl"),
        )

    def test_agent_selects_one_tool_per_observation_until_stop(self):
        calls = []
        registry = ToolRegistry()

        def register(name, output):
            def tool(**kwargs):
                calls.append((name, kwargs))
                return output

            registry.register(
                name,
                tool,
                ToolSpec(
                    name=name,
                    input_schema={
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                ),
            )

        register("generate_config", {"artifacts": ["runs/e1.yaml"], "context_summary": "config ready"})
        register("run_training", {"metrics": {"nmse_db": -36.0}, "context_summary": "training done"})
        register("verify_artifacts", {"context_summary": "artifacts valid"})
        register("write_report", {"artifacts": ["reports/e1/report.md"], "context_summary": "report ready"})

        llm = FakeLLMClient(responses=[
            _action("a1", "generate_config", {"value": "e1"}),
            _action("a2", "run_training", {"value": "runs/e1.yaml"}),
            _action("a3", "verify_artifacts", {"value": "reports/e1"}),
            _action("a4", "write_report", {"value": "e1"}),
            _action("a5", stop=True),
        ])
        planner = AgentActionPlanner(llm, registry)

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loop = ActionPlannerLoop(
                planner=planner,
                tool_registry=registry,
                runtime_factory=self._runtime_factory(root, registry),
                session_id="action-demo",
            )
            result = asyncio.run(loop.run("complete one experiment", max_actions=8))

        self.assertEqual(result.status, "stopped")
        self.assertEqual([name for name, _ in calls], [
            "generate_config", "run_training", "verify_artifacts", "write_report",
        ])
        self.assertEqual(result.planner_call_count, 5)
        self.assertEqual(result.metrics["nmse_db"], -36.0)
        self.assertIn("report ready", llm.last_prompt)

    def test_failure_requires_next_action_to_reference_failure_event(self):
        registry = ToolRegistry()

        def fail():
            raise RuntimeError("training diverged")

        registry.register("run_training", fail, ToolSpec(name="run_training"))
        registry.register("generate_config", lambda: {"context_summary": "safe"}, ToolSpec(name="generate_config"))
        llm = FakeLLMClient(responses=[
            _action("a1", "run_training"),
            _action("a2", "generate_config"),
            _action("a3", "generate_config", caused_by=["a1:failed"]),
            _action("a4", stop=True),
        ])
        planner = AgentActionPlanner(llm, registry)

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loop = ActionPlannerLoop(
                planner=planner,
                tool_registry=registry,
                runtime_factory=self._runtime_factory(root, registry),
                session_id="recovery-demo",
            )
            result = asyncio.run(loop.run("recover", max_actions=6))

        records = {record["action_id"]: record for record in result.history}
        self.assertEqual(records["a1"]["run_status"], "failed")
        self.assertEqual(records["a1"]["event_id"], "a1:failed")
        self.assertEqual(records["a2"]["run_status"], "rejected")
        self.assertIn("must reference unresolved failure", records["a2"]["error"])
        self.assertEqual(records["a3"]["run_status"], "succeeded")
        self.assertEqual(records["a3"]["caused_by_event_ids"], ["a1:failed"])

    def test_action_budget_stops_loop_before_an_extra_planner_call(self):
        registry = ToolRegistry()
        registry.register("echo", lambda: {"context_summary": "ok"}, ToolSpec(name="echo"))
        llm = FakeLLMClient(responses=[_action("a1", "echo"), _action("a2", "echo")])
        planner = AgentActionPlanner(llm, registry)

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loop = ActionPlannerLoop(
                planner=planner,
                tool_registry=registry,
                runtime_factory=self._runtime_factory(root, registry),
                session_id="budget-demo",
            )
            result = asyncio.run(loop.run("respect budget", max_actions=1))

        self.assertEqual(result.status, "max_actions_reached")
        self.assertEqual(result.planner_call_count, 1)
        self.assertEqual(len(result.history), 1)

    def test_memory_off_writes_nothing(self):
        registry = ToolRegistry()
        registry.register("echo", lambda: {"context_summary": "ok"}, ToolSpec(name="echo"))
        llm = FakeLLMClient(responses=[_action("a1", "echo"), _action("a2", stop=True)])
        planner = AgentActionPlanner(llm, registry)
        backend = LangGraphMemoryBackend()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loop = ActionPlannerLoop(
                planner=planner,
                tool_registry=registry,
                runtime_factory=self._runtime_factory(root, registry),
                session_id="mem-off-demo",
                memory_backend=None,
            )
            asyncio.run(loop.run("no memory", max_actions=3))

        self.assertEqual(backend.list_by_run("mem-off-demo"), [])
        backend.close()

    def test_memory_on_writes_episodic_with_full_provenance(self):
        registry = ToolRegistry()
        registry.register("echo", lambda: {"context_summary": "ok"}, ToolSpec(name="echo"))
        llm = FakeLLMClient(responses=[_action("a1", "echo"), _action("a2", stop=True)])
        planner = AgentActionPlanner(llm, registry)
        backend = LangGraphMemoryBackend()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loop = ActionPlannerLoop(
                planner=planner,
                tool_registry=registry,
                runtime_factory=self._runtime_factory(root, registry),
                session_id="mem-on-demo",
                constraints={
                    "domain": "nonlinear-modeling",
                    "dataset_hash": "hash-ds-1",
                    "model_family": "tiny_mlp",
                    "config_hash": "cfg-1",
                },
                memory_backend=backend,
            )
            asyncio.run(loop.run("write memory", max_actions=3))

        items = backend.list_by_run("mem-on-demo")
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.kind, MemoryKind.EPISODIC)
        self.assertEqual(item.run_id, "mem-on-demo")
        self.assertEqual(item.action_id, "a1")
        self.assertEqual(item.evidence_refs, ("a1:succeeded",))
        self.assertEqual(item.namespace, ("nonlinear-modeling", "hash-ds-1", "tiny_mlp"))
        self.assertEqual(item.config_hash, "cfg-1")
        self.assertIn("echo succeeded", item.fact)
        backend.close()


if __name__ == "__main__":
    unittest.main()
