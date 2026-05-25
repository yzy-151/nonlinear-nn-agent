from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.tools import ToolCall, ToolRegistry, ToolSpec


JSONRPC_VERSION = "2.0"
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def tool_spec_to_mcp_tool(spec: ToolSpec | dict[str, Any]) -> dict[str, Any]:
    if isinstance(spec, ToolSpec):
        name = spec.name
        description = spec.description
        input_schema = spec.input_schema
        category = spec.category
        error_policy = spec.error_policy
    else:
        name = str(spec.get("name", ""))
        description = str(spec.get("description", ""))
        input_schema = dict(spec.get("input_schema", {}))
        category = str(spec.get("category", "general"))
        error_policy = str(spec.get("error_policy", "return_error"))
    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema or {"type": "object"},
        "annotations": {
            "category": category,
            "error_policy": error_policy,
        },
    }


class MCPToolBridge:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def list_tools(self) -> dict[str, Any]:
        return {
            "tools": [
                tool_spec_to_mcp_tool(spec)
                for spec in self.registry.describe_tools()
            ]
        }

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self.registry.run(ToolCall(name=name, args=arguments or {}))
        if result.status == "failed":
            return {
                "content": [{"type": "text", "text": result.error or f"Tool failed: {name}"}],
                "isError": True,
            }
        return {
            "content": [{"type": "json", "json": result.output}],
            "isError": False,
        }

    async def handle_json_rpc(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        try:
            if method == "tools/list":
                return mcp_success_response(request_id, self.list_tools())
            if method == "tools/call":
                params = request.get("params", {})
                if not isinstance(params, dict):
                    return mcp_error_response(request_id, INVALID_PARAMS, "params must be an object.")
                name = params.get("name")
                arguments = params.get("arguments", {})
                if not isinstance(name, str) or not name:
                    return mcp_error_response(request_id, INVALID_PARAMS, "params.name must be a non-empty string.")
                if not isinstance(arguments, dict):
                    return mcp_error_response(request_id, INVALID_PARAMS, "params.arguments must be an object.")
                return mcp_success_response(request_id, await self.call_tool(name, arguments))
            return mcp_error_response(request_id, METHOD_NOT_FOUND, f"Unsupported method: {method}")
        except Exception as exc:  # noqa: BLE001 - JSON-RPC bridge must return structured errors
            return mcp_error_response(request_id, INTERNAL_ERROR, str(exc))


def build_mcp_tool_bridge(workspace: Path | str, default_timeout_seconds: float = 300.0) -> MCPToolBridge:
    registry = build_experiment_tool_registry(
        workspace=workspace,
        default_timeout_seconds=default_timeout_seconds,
    )
    return MCPToolBridge(registry)


def mcp_success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def mcp_error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


async def serve_json_lines(
    bridge: MCPToolBridge,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    for line in input_stream:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                response = mcp_error_response(None, INVALID_PARAMS, "request must be a JSON object.")
            else:
                response = await bridge.handle_json_rpc(request)
        except json.JSONDecodeError as exc:
            response = mcp_error_response(None, INVALID_PARAMS, f"invalid JSON: {exc}")
        output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
        output_stream.flush()


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    workspace = Path(argv[0]) if argv else Path(".")
    bridge = build_mcp_tool_bridge(workspace)
    asyncio.run(serve_json_lines(bridge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
