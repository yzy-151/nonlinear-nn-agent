# Experiment Agent Harness v1.2 总学习文档

更新时间：2026-07-23

这是当前最新主学习文档。你优先读这一份；旧版 `v0.1-v1.1` 保留为版本历史。

## 1. 本版主题

v1.2 补上 Agent Harness 面试高频问题：MCP / Tool Protocol / 工具协议层。

本版没有直接引入外部 MCP SDK，而是先实现一个可测试、可解释的 MCP-compatible bridge：

- 将内部 `ToolSpec` 映射为 MCP tool schema。
- 支持 `tools/list`。
- 支持 `tools/call`。
- 保留 JSON-RPC 2.0 响应形状。
- 把工具成功/失败统一包装为 MCP-style content。
- 提供 stdio JSON-lines 入口，便于后续替换为真实 MCP SDK。

## 2. 新增文件

- `src/nonlinear_agent/mcp_server.py`
- `examples/nonlinear_fit/serve_mcp_tools.py`
- `tests/test_mcp_server.py`

更新：

- `src/nonlinear_agent/__init__.py`

## 3. 当前完整架构

```text
User / MCP Client
  -> JSON-RPC tools/list or tools/call
  -> MCPToolBridge
  -> ToolSpec -> MCP tool schema
  -> ToolRegistry
  -> ToolCall
  -> Experiment tool function
  -> ToolResult
  -> MCP-style content result
```

它和 planner loop 的关系：

```text
LLM Planner Loop path:
  Planner -> ExperimentPlan -> Runtime -> ToolRegistry

MCP path:
  MCP Client -> MCPToolBridge -> ToolRegistry
```

两条路径共用同一个 `ToolRegistry`，所以工具能力没有复制两套。

## 4. ToolSpec 到 MCP Tool Schema

内部 `ToolSpec`：

```text
name
description
input_schema
category
error_policy
```

MCP-compatible schema：

```json
{
  "name": "verify_artifacts",
  "description": "Verify metrics, PSD artifact, and NMSE threshold.",
  "inputSchema": {
    "type": "object",
    "required": ["output_dir", "nmse_threshold_db"]
  },
  "annotations": {
    "category": "experiment",
    "error_policy": "return_error"
  }
}
```

关键函数：

- `tool_spec_to_mcp_tool()`
- `MCPToolBridge.list_tools()`

## 5. tools/call 怎么执行

`MCPToolBridge.call_tool(name, arguments)` 做三步：

1. 构造内部 `ToolCall(name=name, args=arguments)`。
2. 调用 `ToolRegistry.run(call)`。
3. 把 `ToolResult` 转成 MCP-style response。

成功返回：

```json
{
  "content": [
    {
      "type": "json",
      "json": {"value": "ok"}
    }
  ],
  "isError": false
}
```

失败返回：

```json
{
  "content": [
    {
      "type": "text",
      "text": "Unknown tool: missing"
    }
  ],
  "isError": true
}
```

## 6. JSON-RPC 入口

`MCPToolBridge.handle_json_rpc()` 当前支持：

- `tools/list`
- `tools/call`

请求示例：

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "generate_config",
    "arguments": {
      "base_config_path": "configs/model-search/lstsq-complexmp-o12-m150.yaml",
      "experiment_id": "mcp-demo",
      "overrides": {"epochs": 0, "output_dir": "reports/mcp-demo"}
    }
  }
}
```

## 7. stdio JSON-lines 入口

运行：

```powershell
python examples\nonlinear_fit\serve_mcp_tools.py
```

输入一行 JSON-RPC request，输出一行 JSON-RPC response。

这个入口是最小 mock server，不等同于完整生产 MCP server。它的价值是把协议边界、schema 映射、tool call 返回形状先跑通，后续可以替换为官方 MCP SDK。

## 8. 面试回答模板

### MCP 是什么？

MCP 可以理解为模型/Agent 调用外部工具和资源的标准协议层。它把工具发现、参数 schema、调用结果、错误返回标准化，避免每个 Agent 框架都自定义一套工具接口。

### 你这个项目里 MCP 做了什么？

我先做了一个 MCP-compatible bridge：把内部 `ToolSpec` 映射为 MCP tool schema，并实现 `tools/list` 和 `tools/call` 的 JSON-RPC 处理。底层复用已有 `ToolRegistry`，所以 LLM planner 和 MCP client 调的是同一套实验工具。

### ToolSpec、Skill、MCP 有什么区别？

- `ToolSpec`：项目内部的工具接口描述，定义 name、description、input schema、category、error policy。
- Skill：偏工作流组织和使用策略，告诉 agent 什么时候、如何使用一类能力。
- MCP：跨进程/跨客户端的标准工具协议，负责工具发现和调用。

### 为什么没有直接接完整 MCP SDK？

v1.2 的目标是先把协议抽象和工程边界跑通：schema 映射、工具发现、工具调用、错误返回。这样测试简单、依赖少、解释清楚。下一步可以把 `MCPToolBridge` 接到官方 SDK 的 transport 层，而不需要重写工具系统。

## 9. 验证

```powershell
python -m unittest tests.test_mcp_server
python -m unittest discover tests
```

## 10. 简历表达

```text
为 Agent Harness 增加 MCP-compatible Tool Protocol Bridge，将内部 ToolSpec 映射为 MCP tool schema，并实现 tools/list、tools/call 的 JSON-RPC 处理；底层复用 ToolRegistry 和真实实验工具链，使 LLM Planner 与 MCP Client 共享同一套工具能力边界。
```

## 11. 下一步

v1.3：Async Runtime Hardening。

目标：

- cancellation / interrupt
- per-tool timeout policy
- retry policy 分类
- structured error taxonomy
- resume failed run
