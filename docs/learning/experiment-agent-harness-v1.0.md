# Experiment Agent Harness v1.0 学习文档

更新时间：2026-07-22

这是 v1.0 历史学习文档。当前最新主学习入口是 `experiment-agent-harness-v1.1.md`。

## 本版主题

v1.0 补上 Agent 面试高频问题：工具系统怎么定义、注册、发现、调用和失败恢复。

新增能力：

- `ToolSpec`
- tool input schema
- tool category
- tool error policy
- `ToolRegistry.describe_tools()`
- unknown tool structured failure policy
- planner prompt 的 tool spec 渐进式披露

## 核心设计

`ToolSpec` 描述工具，而不是执行工具：

```text
name
description
input_schema
category
error_policy
```

`ToolRegistry` 负责执行工具，并保存工具 schema。Planner 可以只看到本轮允许披露的工具描述，而不是整个工具实现。

## 面试回答

工具从定义到调用：

1. 用 `ToolSpec` 描述工具名、用途、输入 schema、类别和错误策略。
2. 把真实函数注册到 `ToolRegistry`。
3. Planner 只看到允许披露的 tool spec，并输出结构化计划。
4. Runtime 根据计划构造 `ToolCall`，调用 registry 执行工具。
5. 结果、错误、耗时和指标进入 trace/session/history。

Skill 和 MCP 的关系：

- Skill 偏能力组织、触发策略和工作流说明。
- MCP 偏标准协议接口。
- `ToolSpec` 是两者的前置抽象，后续可映射到 MCP tool schema。

## 验证

```powershell
python -m unittest tests.test_harness_runtime tests.test_experiment_tools tests.test_llm_planner
python -m unittest discover tests
```

