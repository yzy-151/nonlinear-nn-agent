# Experiment Agent Harness v1.0 总学习文档

更新时间：2026-07-22

这是当前最新主学习文档。你优先读这一份；旧版 `v0.1-v0.9` 保留为版本历史。

## 1. 本版主题

v1.0 补上 Agent 面试高频问题：工具系统怎么定义、注册、发现、调用和失败恢复。

本项目现在支持：

- `ToolSpec`
- tool input schema
- tool category
- tool error policy
- `ToolRegistry.describe_tools()`
- unknown tool structured failure policy
- planner prompt 的 tool spec 渐进式披露

## 2. 新增/更新文件

更新：

- `src/nonlinear_agent/tools.py`
- `src/nonlinear_agent/experiment_tools.py`
- `src/nonlinear_agent/planner.py`
- `tests/test_harness_runtime.py`
- `tests/test_experiment_tools.py`
- `tests/test_llm_planner.py`

## 3. 核心设计

### ToolSpec

`ToolSpec` 描述工具，而不是执行工具：

```text
name
description
input_schema
category
error_policy
```

这解决的是“Agent 怎么发现和理解工具”的问题。

### ToolRegistry

`ToolRegistry` 现在不只是函数表，还能：

- 注册工具函数。
- 保存工具 schema。
- 按 category 披露工具。
- 返回工具描述给 planner。
- 对未知工具按策略抛错或返回结构化失败。

### Progressive Disclosure

Planner 不需要每次看到所有内部实现。它只需要看到本轮允许使用的工具 schema 摘要。

面试表达：

> 我把工具系统分成执行层和描述层。执行层是 ToolRegistry 调用真实函数；描述层是 ToolSpec，用于向 planner 渐进式披露工具能力、参数 schema 和错误策略。这样可以减少 token 消耗，也能避免模型调用不该调用的工具。

## 4. 和 Skill / MCP 的关系

当前项目还不是完整 MCP server，但已经具备 Skill 化前置结构：

- `ToolSpec` 类似 Skill/Tool 的 manifest。
- `category` 支持按任务阶段披露工具。
- `input_schema` 对应 function calling / MCP tool schema。
- `error_policy` 对应工具失败恢复策略。

下一步如果做 MCP，可以把 `ToolSpec` 转成 MCP tool schema。

## 5. 面试回答模板

### 工具从定义到调用完整流程？

先用 `ToolSpec` 描述工具名、用途、输入 schema、类别和错误策略；再把真实函数注册到 `ToolRegistry`；planner 只看到允许披露的 tool spec，并输出结构化计划；runtime 根据计划构造 `ToolCall`，调用 registry 执行工具；结果、错误、耗时和指标进入 trace/session/history。

### 工具失败怎么办？

工具失败分层处理：

- unknown tool：可以抛 `KeyError`，也可以按 `return_error` 返回结构化失败。
- runtime tool exception：返回 failed `ToolResult`，写入 trace 和 error event。
- validation error：不进 runtime，写入 rejected history。

### Skill 和 MCP 有什么区别？

Skill 更偏“能力组织和触发策略”，可以包含说明、步骤、约束、示例和工具组合。MCP 更偏“标准协议接口”，定义模型/客户端如何发现和调用外部工具。本项目的 `ToolSpec` 是两者的前置抽象：既能服务 planner 渐进式披露，也能后续映射到 MCP schema。

## 6. 验证

```powershell
python -m unittest tests.test_harness_runtime tests.test_experiment_tools tests.test_llm_planner
python -m unittest discover tests
```

## 7. 简历表达

```text
为 Agent Harness 工具系统增加 ToolSpec 描述层，支持工具名称、用途、输入 schema、类别和错误策略的结构化注册，并通过 ToolRegistry.describe_tools() 向 LLM Planner 渐进式披露可用工具能力，实现工具发现、调用边界控制和 unknown tool 结构化失败处理。
```

## 8. 下一步

v1.1：Reflection + Recovery Policy。

目标是让每轮 planner 不只继续实验，还要显式解释失败原因、修正策略和下一轮避免项。

