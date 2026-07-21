# Experiment Agent Harness v0.1 学习文档

更新时间：2026-07-21

## 这一版做了什么

本阶段把原来的 Nonlinear NN Experiment Agent 从“顺序自动训练流程”升级为一个轻量级 Agent Harness 原型。重点不是继续追求更低 NMSE，而是补上 Agent Harness 岗位最关心的运行时能力：工具系统、Hook、会话持久化、trace、异步事件流和失败可观测。

新增核心文件：

- `src/nonlinear_agent/tools.py`：工具注册、异步执行、timeout、retry。
- `src/nonlinear_agent/hooks.py`：`before_tool`、`after_tool`、`on_error`、`on_metric` 回调机制。
- `src/nonlinear_agent/session.py`：实验 session 的创建、保存、加载和恢复。
- `src/nonlinear_agent/trace.py`：JSONL trace event 记录。
- `src/nonlinear_agent/runtime.py`：异步 Agentic Loop，按步骤执行工具并流式产出事件。
- `tests/test_harness_runtime.py`：覆盖成功链路、失败链路、retry、hooks、session resume、trace JSONL。

## 你应该从中掌握什么

### 1. Agent Harness 不是聊天壳

岗位里的 harness/runtime 指的是 Agent 背后的执行框架。一个可解释的 harness 至少要回答：

- Agent 每一步为什么执行？
- 调用了什么工具？参数是什么？
- 工具耗时多少？失败了吗？重试了吗？
- session 中保留了哪些状态？
- 中断后能不能恢复？
- 出问题后能不能 replay 和定位？

本项目 v0.1 已经把这些问题落到了代码结构里。

### 2. Tool Calling 要被治理

`ToolRegistry` 的作用不是简单把函数放进字典，而是提供统一治理入口：

- 所有工具都有名字、参数、超时和重试次数。
- 同步函数和异步函数都能被 runtime 调用。
- 失败不会直接让进程崩掉，而是转成可观测的 `ToolResult`。

面试时可以强调：工具调用系统需要统一封装 timeout、retry、错误结构和 trace，否则 Agent 链路不可控。

### 3. Hook 是运行时扩展点

`HookManager` 提供了四类事件：

- `before_tool`：工具调用前记录参数、做权限检查、打点。
- `after_tool`：工具成功后记录输出、做摘要、更新状态。
- `on_error`：失败时报警、降级、写入错误链路。
- `on_metric`：实验指标出现时触发评估或下一步建议。

这对应 JD 里的 Hook 机制。你要理解：Hook 的价值是让 runtime 主流程保持稳定，同时允许观测、审批、日志、评估等能力插入执行链路。

### 4. Session 和 Trace 是稳定性的证据

`SessionStore` 保存的是 Agent 的业务状态，`TraceLogger` 保存的是执行证据。两者不要混在一起：

- session 面向恢复：当前步骤、metrics、artifacts、errors、context summary。
- trace 面向排查：event_type、tool、status、latency_ms、payload、error。

这就是“可恢复”和“可观测”的区别。

### 5. 异步事件流是后续接 WebSocket/语音的基础

`ExperimentHarnessRuntime.run()` 是 async generator，会不断 yield `TraceEvent`。这意味着后续可以很自然地接：

- CLI 实时打印事件。
- FastAPI SSE。
- WebSocket streaming。
- Voice Agent 的 partial response / barge-in。

现在虽然还没做语音，但底层执行形态已经不是一次性脚本输出，而是事件流。

## 你需要补的知识

优先顺序：

1. Python async：`asyncio`、`async for`、`asyncio.wait_for`、`asyncio.to_thread`、timeout、cancel。
2. Agent runtime：tool registry、session、trace、hook、retry、event stream。
3. FastAPI streaming：SSE 和 WebSocket。
4. LangGraph：state graph、checkpoint、interrupt、resume。
5. MCP：把 `ToolRegistry` 中的实验工具暴露成 MCP tools。

## 自测问题

你应能回答这些问题：

- 为什么 `ToolRegistry.run()` 返回失败结果，而不是直接把异常抛给 runtime？
- 为什么 session 和 trace 要分开？
- Hook 和硬编码日志有什么区别？
- 这个 runtime 如何接入 LangGraph？
- 这个 runtime 如何接入 WebSocket？
- 如果训练跑到一半失败，trace 里应该看什么？

## 下一阶段学习目标

v0.2 应该补：

- `run_training` 真实工具封装。
- `generate_config` 真实工具封装。
- session resume 示例命令。
- FastAPI SSE 事件接口。
- trace replay 报告生成。

做到 v0.2 后，这个项目就不再只是实验自动化，而是一个小型 Agent runtime 工程。
