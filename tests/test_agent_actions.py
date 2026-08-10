import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.actions import AgentAction, parse_agent_action, validate_agent_action
from nonlinear_agent.mcp_server import tool_spec_to_mcp_tool
from nonlinear_agent.tools import ToolRegistry, ToolSpec


class AgentActionTest(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.spec = ToolSpec(
            name="run_training",
            description="Run one training config.",
            input_schema={
                "type": "object",
                "properties": {
                    "config_path": {"type": "string"},
                    "timeout_seconds": {"type": "number"},
                },
                "required": ["config_path"],
                "additionalProperties": False,
            },
        )
        self.registry.register("run_training", lambda **kwargs: kwargs, spec=self.spec)

    def test_parse_tool_call_action_and_convert_to_tool_call(self):
        action = parse_agent_action(
            '{"type":"tool_call","action_id":"action-001",'
            '"reason":"train candidate","tool":"run_training",'
            '"arguments":{"config_path":"runs/e1.yaml"},'
            '"caused_by_event_ids":["event-001"]}'
        )

        call = validate_agent_action(action, self.registry)

        self.assertEqual(action.action_type, "tool_call")
        self.assertEqual(call.name, "run_training")
        self.assertEqual(call.args, {"config_path": "runs/e1.yaml"})
        self.assertEqual(action.caused_by_event_ids, ("event-001",))

    def test_parse_stop_action(self):
        action = parse_agent_action(
            '{"type":"stop","action_id":"action-stop",'
            '"reason":"target reached","caused_by_event_ids":[]}'
        )

        call = validate_agent_action(action, self.registry)

        self.assertIsNone(call)
        self.assertTrue(action.is_stop)

    def test_unknown_tool_is_rejected_before_runtime(self):
        action = AgentAction(
            action_type="tool_call",
            action_id="action-unknown",
            reason="bad tool",
            tool_name="shell",
            arguments={},
        )

        with self.assertRaisesRegex(ValueError, "Unknown tool"):
            validate_agent_action(action, self.registry)

    def test_missing_required_argument_is_rejected(self):
        action = AgentAction(
            action_type="tool_call",
            action_id="action-missing",
            reason="missing path",
            tool_name="run_training",
            arguments={},
        )

        with self.assertRaisesRegex(ValueError, "Missing required arguments: config_path"):
            validate_agent_action(action, self.registry)

    def test_extra_argument_is_rejected_by_tool_spec(self):
        action = AgentAction(
            action_type="tool_call",
            action_id="action-extra",
            reason="extra arg",
            tool_name="run_training",
            arguments={"config_path": "run.yaml", "command": "del *"},
        )

        with self.assertRaisesRegex(ValueError, "Unexpected arguments: command"):
            validate_agent_action(action, self.registry)

    def test_wrong_argument_type_is_rejected_by_tool_spec(self):
        action = AgentAction(
            action_type="tool_call",
            action_id="action-type",
            reason="wrong type",
            tool_name="run_training",
            arguments={"config_path": {"nested": "run.yaml"}},
        )

        with self.assertRaisesRegex(ValueError, "config_path must be string"):
            validate_agent_action(action, self.registry)

    def test_action_guard_and_mcp_use_the_same_tool_spec_schema(self):
        mcp_tool = tool_spec_to_mcp_tool(self.registry.get_tool_spec("run_training"))

        self.assertEqual(mcp_tool["inputSchema"], self.spec.input_schema)
        self.assertEqual(
            mcp_tool["inputSchema"]["required"],
            self.registry.get_tool_spec("run_training").input_schema["required"],
        )


if __name__ == "__main__":
    unittest.main()
