"""
MCP Tool Bridge — JSON-RPC 2.0 工具协议桥 ==============================

把项目内部的 ToolSpec / ToolRegistry 暴露为 MCP-compatible 的工具协议，
使外部 MCP Client（如 Claude Desktop、Codex、其他 Agent）能通过标准协议
发现和调用本项目的实验工具。

协议：JSON-RPC 2.0（不是"NRC"——是 Remote Procedure Call）
  → 请求和响应都是 JSON，通过 stdio 或 HTTP 传输
  → 每个请求有 method 字段（"做什么"）和 id 字段（"哪个请求"）
  → 响应有 result（成功）或 error（失败）

支持的两种方法：
  tools/list  — 列出所有可用工具（类似 REST 的 GET /tools）
  tools/call  — 调用一个工具（类似 REST 的 POST /tools/{name}/invoke）

面试要点：
  - ToolSpec → MCP tool schema 的映射展示了"内部抽象 → 标准协议"的转换能力
  - MCPBridge 底层复用 ToolRegistry，LLM Planner 和 MCP Client 共享同一套工具
  - JSON-RPC error codes 遵循规范（-32601 = 方法未找到, -32602 = 参数无效）
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.tools import ToolCall, ToolRegistry, ToolSpec


# ============================================================
# JSON-RPC 2.0 常量
# ============================================================
JSONRPC_VERSION = "2.0"         # 协议版本
METHOD_NOT_FOUND = -32601       # 标准错误码：调了不存在的方法
INVALID_PARAMS = -32602         # 标准错误码：参数格式不对
INTERNAL_ERROR = -32603         # 标准错误码：工具内部崩溃


# ============================================================
# tool_spec_to_mcp_tool — ToolSpec → MCP schema
# ============================================================
def tool_spec_to_mcp_tool(spec: ToolSpec | dict[str, Any]) -> dict[str, Any]:
    """把内部的 ToolSpec 转成 MCP 协议的工具描述格式。

    映射关系：
      ToolSpec.name          → MCP tool.name
      ToolSpec.description   → MCP tool.description
      ToolSpec.input_schema  → MCP tool.inputSchema（驼峰命名）
      ToolSpec.category      → MCP tool.annotations.category（非标字段，保存在 annotations 里）
      ToolSpec.error_policy  → MCP tool.annotations.error_policy

    为什么支持 dict 输入？
      ToolRegistry.describe_tools() 返回的是 dict 列表，
      不需要先转成 ToolSpec 再转 MCP。两种格式通吃。
    """
    if isinstance(spec, ToolSpec):
        name = spec.name
        description = spec.description
        input_schema = spec.input_schema
        category = spec.category
        error_policy = spec.error_policy
    else:
        # dict 格式（来自 describe_tools()）
        name = str(spec.get("name", ""))
        description = str(spec.get("description", ""))
        input_schema = dict(spec.get("input_schema", {}))
        category = str(spec.get("category", "general"))
        error_policy = str(spec.get("error_policy", "return_error"))

    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema or {"type": "object"},
        # annotations 是 MCP 协议允许的扩展字段，放非标信息
        "annotations": {
            "category": category,
            "error_policy": error_policy,
        },
    }


# ============================================================
# MCPToolBridge — 工具桥（核心）
# ============================================================
class MCPToolBridge:
    """在 ToolRegistry 外面包一层 JSON-RPC 协议。

    三个方法：
      list_tools()     — 对应 tools/list 请求，返回工具列表
      call_tool()      — 对应 tools/call 请求，执行工具
      handle_json_rpc() — 总入口：解析请求 → 路由 → 返回响应

    设计要点：
      Bridge 不创建新的工具，而是把已有的 ToolRegistry 翻译成 MCP 协议。
      LLM Planner 和 MCP Client 共用同一个 Registry 实例——工具能力是一致的。
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    # ── tools/list ──────────────────────────────────────
    def list_tools(self) -> dict[str, Any]:
        """列出所有可用工具的 MCP schema。

        返回格式：
          {"tools": [{"name": "generate_config", "description": "...", "inputSchema": {...}}, ...]}

        MCP Client 拿到这个列表后，就能知道它能调哪些工具、每个需要什么参数。
        """
        return {
            "tools": [
                tool_spec_to_mcp_tool(spec)
                for spec in self.registry.describe_tools()
            ]
        }

    # ── tools/call ──────────────────────────────────────
    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """执行一个工具调用并返回 MCP 格式的结果。

        内部流程：
          ToolCall(name, args) → ToolRegistry.run() → ToolResult
          → 成功：{"content": [{"type": "json", "json": output}], "isError": False}
          → 失败：{"content": [{"type": "text", "text": error}], "isError": True}

        MCP 协议规定工具返回值必须包在 content 数组里，每条有 type 字段。
        """
        result = await self.registry.run(
            ToolCall(name=name, args=arguments or {})
        )
        if result.status == "failed":
            return {
                "content": [
                    {"type": "text", "text": result.error or f"Tool failed: {name}"}
                ],
                "isError": True,
            }
        return {
            "content": [{"type": "json", "json": result.output}],
            "isError": False,
        }

    # ── JSON-RPC 路由 ──────────────────────────────────
    async def handle_json_rpc(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        """解析 JSON-RPC 请求，路由到对应方法，返回 JSON-RPC 响应。

        请求格式（JSON-RPC 2.0）：
          {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
          {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
           "params": {"name": "run_training", "arguments": {...}}}

        响应格式：
          成功 → {"jsonrpc": "2.0", "id": 1, "result": {...}}
          失败 → {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "..."}}

        路由表：
          tools/list  → self.list_tools()
          tools/call  → self.call_tool(name, arguments)
          其他         → METHOD_NOT_FOUND 错误
        """
        request_id = request.get("id")
        method = request.get("method")

        try:
            if method == "tools/list":
                return mcp_success_response(request_id, self.list_tools())

            if method == "tools/call":
                params = request.get("params", {})
                if not isinstance(params, dict):
                    return mcp_error_response(
                        request_id, INVALID_PARAMS, "params must be an object."
                    )
                name = params.get("name")
                arguments = params.get("arguments", {})
                if not isinstance(name, str) or not name:
                    return mcp_error_response(
                        request_id, INVALID_PARAMS,
                        "params.name must be a non-empty string."
                    )
                if not isinstance(arguments, dict):
                    return mcp_error_response(
                        request_id, INVALID_PARAMS,
                        "params.arguments must be an object."
                    )
                return mcp_success_response(
                    request_id, await self.call_tool(name, arguments)
                )

            # 不支持的方法
            return mcp_error_response(
                request_id, METHOD_NOT_FOUND, f"Unsupported method: {method}"
            )

        except Exception as exc:
            # 工具内部崩溃 → 返回结构化错误，不抛异常
            return mcp_error_response(request_id, INTERNAL_ERROR, str(exc))


# ============================================================
# 工厂函数 + JSON-RPC 响应构造
# ============================================================

def build_mcp_tool_bridge(
    workspace: Path | str, default_timeout_seconds: float = 300.0
) -> MCPToolBridge:
    """创建 MCPToolBridge 实例，绑定实验工具注册中心。

    等价于：
      registry = build_experiment_tool_registry(workspace)
      bridge = MCPToolBridge(registry)
    """
    registry = build_experiment_tool_registry(
        workspace=workspace, default_timeout_seconds=default_timeout_seconds,
    )
    return MCPToolBridge(registry)


def mcp_success_response(
    request_id: Any, result: dict[str, Any]
) -> dict[str, Any]:
    """构造 JSON-RPC 2.0 成功响应。"""
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def mcp_error_response(
    request_id: Any, code: int, message: str
) -> dict[str, Any]:
    """构造 JSON-RPC 2.0 错误响应。

    error.code 使用标准 JSON-RPC 错误码：
      -32601 = 方法不存在
      -32602 = 参数无效
      -32603 = 内部错误
    """
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


# ============================================================
# stdio JSON-Lines 服务（模拟 MCP Server）
# ============================================================
async def serve_json_lines(
    bridge: MCPToolBridge,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    """通过 stdio 的 JSON-Lines 协议提供 MCP 服务。

    读取 stdin 的每一行 → JSON 解析 → 调 bridge.handle_json_rpc()
    → 写回 stdout（一行 JSON）。

    这是 MCP 官方 SDK 接入前的一个轻量协议验证层：
      - 用 curl 或 echo 向 stdin 发请求
      - 从 stdout 读响应
      - 不需要 HTTP server，不需要网络端口

    启动方式：
      python examples/nonlinear_fit/serve_mcp_tools.py
      然后输入一行：{"jsonrpc":"2.0","id":1,"method":"tools/list"}
      回车 → 看到工具列表 JSON
    """
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout

    for line in input_stream:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                response = mcp_error_response(
                    None, INVALID_PARAMS, "request must be a JSON object."
                )
            else:
                response = await bridge.handle_json_rpc(request)
        except json.JSONDecodeError as exc:
            response = mcp_error_response(
                None, INVALID_PARAMS, f"invalid JSON: {exc}"
            )

        # 一行 JSON 输出 → 一行 JSON 响应
        output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
        output_stream.flush()


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：启动 stdio JSON-Lines MCP 服务。"""
    argv = argv or sys.argv[1:]
    workspace = Path(argv[0]) if argv else Path(".")
    bridge = build_mcp_tool_bridge(workspace)
    asyncio.run(serve_json_lines(bridge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
