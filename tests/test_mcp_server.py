import asyncio
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.mcp_server import (
    MCPToolBridge,
    build_mcp_tool_bridge,
    mcp_error_response,
    mcp_success_response,
    tool_spec_to_mcp_tool,
)
from nonlinear_agent.tools import ToolRegistry, ToolSpec


class MCPServerTest(unittest.TestCase):
    def test_tool_spec_to_mcp_tool_maps_schema_description_and_metadata(self):
        spec = ToolSpec(
            name="verify_artifacts",
            description="Verify metrics and PSD.",
            input_schema={"type": "object", "required": ["output_dir"]},
            category="experiment",
            error_policy="return_error",
        )

        tool = tool_spec_to_mcp_tool(spec)

        self.assertEqual(tool["name"], "verify_artifacts")
        self.assertEqual(tool["description"], "Verify metrics and PSD.")
        self.assertEqual(tool["inputSchema"], {"type": "object", "required": ["output_dir"]})
        self.assertEqual(tool["annotations"]["category"], "experiment")
        self.assertEqual(tool["annotations"]["error_policy"], "return_error")

    def test_bridge_lists_registered_tools_in_mcp_shape(self):
        registry = ToolRegistry()
        registry.register(
            "echo",
            lambda value: {"value": value},
            spec=ToolSpec(
                name="echo",
                description="Echo a value.",
                input_schema={"type": "object", "required": ["value"]},
                category="debug",
            ),
        )

        result = MCPToolBridge(registry).list_tools()

        self.assertEqual(result["tools"][0]["name"], "echo")
        self.assertEqual(result["tools"][0]["inputSchema"]["required"], ["value"])

    def test_bridge_calls_tool_and_returns_mcp_content(self):
        registry = ToolRegistry()
        registry.register("echo", lambda value: {"value": value})

        result = asyncio.run(MCPToolBridge(registry).call_tool("echo", {"value": "ok"}))

        self.assertFalse(result["isError"])
        self.assertEqual(result["content"][0]["type"], "json")
        self.assertEqual(result["content"][0]["json"]["value"], "ok")

    def test_bridge_returns_structured_error_for_failed_tool(self):
        registry = ToolRegistry(unknown_tool_policy="return_error")

        result = asyncio.run(MCPToolBridge(registry).call_tool("missing", {}))

        self.assertTrue(result["isError"])
        self.assertIn("Unknown tool", result["content"][0]["text"])

    def test_bridge_handles_json_rpc_tools_list_and_tools_call(self):
        registry = ToolRegistry()
        registry.register("echo", lambda value: {"value": value})
        bridge = MCPToolBridge(registry)

        list_response = asyncio.run(bridge.handle_json_rpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }))
        call_response = asyncio.run(bridge.handle_json_rpc({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"value": "ok"}},
        }))

        self.assertEqual(list_response["id"], 1)
        self.assertIn("tools", list_response["result"])
        self.assertEqual(call_response["id"], 2)
        self.assertEqual(call_response["result"]["content"][0]["json"]["value"], "ok")

    def test_json_rpc_helpers_preserve_id_and_error_shape(self):
        success = mcp_success_response(request_id="abc", result={"ok": True})
        error = mcp_error_response(request_id="abc", code=-32601, message="missing method")

        self.assertEqual(success, {"jsonrpc": "2.0", "id": "abc", "result": {"ok": True}})
        self.assertEqual(error["jsonrpc"], "2.0")
        self.assertEqual(error["id"], "abc")
        self.assertEqual(error["error"]["code"], -32601)

    def test_build_mcp_tool_bridge_exposes_experiment_tools(self):
        bridge = build_mcp_tool_bridge(workspace=Path("."))

        tool_names = [tool["name"] for tool in bridge.list_tools()["tools"]]

        self.assertIn("generate_config", tool_names)
        self.assertIn("run_training", tool_names)
        self.assertIn("verify_artifacts", tool_names)
        self.assertIn("write_report", tool_names)


if __name__ == "__main__":
    unittest.main()
