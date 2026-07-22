# Experiment Agent Harness 简历包装

更新时间：2026-07-21

## 项目定位

项目名称建议写：

`Agentic Experiment Harness for Nonlinear System Modeling`

中文解释：

面向算法实验的轻量级 Agent Harness Runtime，将神经网络非线性拟合实验拆解为可注册工具，并实现异步执行、Hook、session 持久化、trace logging、失败重试、指标采集和报告生成。

## 和岗位 JD 的对应关系

| JD 能力 | 本项目证据 |
|---|---|
| Agentic Loop | `ExperimentHarnessRuntime.run()` 按步骤执行工具并流式产出事件 |
| 工具系统 / Tool Calling | `ToolRegistry`、`ToolCall`、`ToolResult` |
| Hook 机制 | `HookManager` 支持 before/after/error/metric hook |
| 会话持久化 | `SessionStore` 保存和恢复 experiment session |
| 上下文压缩基础 | session 中保留 `context_summary` 字段，v0.2 可接日志压缩 |
| 链路可观测 | `TraceLogger` 输出 JSONL trace event |
| 稳定性和容错 | 工具 timeout、retry、失败结构化记录 |
| 异步编程 | runtime 和工具执行使用 async generator / asyncio |
| Agentic coding | 使用 Codex 协作设计、测试、实现和文档沉淀 |
| 算法背景结合 | 底层任务是神经网络非线性系统拟合，指标为 NMSE 和 PSD |

## 简历 Bullet 版本

### 标准版

- 设计并实现面向算法实验的轻量级 Agent Harness Runtime，将非线性神经网络拟合实验拆解为配置生成、训练执行、NMSE 评估、PSD 验证和报告生成等工具链，支持异步 Agentic Loop、工具注册、Hook、session 持久化、trace logging 和失败重试。

### 更偏 Agent Runtime 版

- 构建 Agentic Experiment Harness，抽象 `ToolRegistry`、`HookManager`、`SessionStore`、`TraceLogger` 等 runtime 组件，实现工具调用前后 Hook、错误回调、指标事件流、JSONL 执行轨迹和 session resume，为后续接入 LangGraph、MCP 与 WebSocket streaming 奠定基础。

### 更偏算法工程版

- 将神经网络非线性 MPDPD 拟合实验重构为可配置、可测试、可审计的自动化实验系统，支持 YAML 配置、NMSE 指标解析、PSD 产物验证、实验对比报告和小参数模型搜索；在 4000 参数约束下获得 3626 参数、NMSE -37.42 dB 的轻量模型。

### 强面试版

- 从零实现实验场景 Agent Harness 原型，覆盖 Agentic Loop、Tool Calling、Hook、会话持久化、执行 trace、失败重试和指标事件流；通过单元测试验证成功链路、失败链路、retry、hooks、session resume 与 trace JSONL，体现 Agent runtime 的可观测性和工程稳定性。

## 面试讲法

面试官如果问“你这个和普通脚本有什么区别”，回答：

普通脚本只负责把训练跑完，而这个项目把实验过程抽象成 Agent runtime：每一步是工具调用，工具调用有 timeout/retry，执行前后会触发 hook，session 保存可恢复状态，trace 记录完整链路，指标作为事件流产出。这样后续可以接 LangGraph checkpoint、MCP tool server、WebSocket streaming，而不是只能本地跑一次脚本。

面试官如果问“为什么不用 LangGraph 直接做”，回答：

我先做轻量 runtime 是为了理解 Agent harness 的基本组成：工具系统、Hook、session、trace 和事件流。LangGraph 可以作为 v0.3 的编排框架接入，但我不希望只会调用框架 API，而不理解 runtime 内部为什么需要这些组件。

面试官如果问“这个项目和岗位有什么关系”，回答：

岗位核心不是车载业务本身，而是 Agent harness/runtime 的工程能力。本项目把真实算法实验作为业务场景，展示了工具调用治理、异步执行、链路追踪、失败恢复和 session 持久化。这些能力可以迁移到车载对话系统、实验自动化系统或其他复杂工具调用 Agent。

## 当前证据文件

- `src/nonlinear_agent/runtime.py`
- `src/nonlinear_agent/tools.py`
- `src/nonlinear_agent/hooks.py`
- `src/nonlinear_agent/session.py`
- `src/nonlinear_agent/trace.py`
- `tests/test_harness_runtime.py`
- `docs/learning/experiment-agent-harness-v0.1.md`
- `docs/handoff/deepseek-continuation-plan.md`
- `docs/model-search-summary.md`
- `docs/model-search-results.csv`

## 下一步增强后可新增表述

完成 v0.2 后可补一句：

- 基于 FastAPI 实现 Agent 执行事件 SSE/WebSocket streaming，支持训练过程实时观测、失败事件推送和 session replay，模拟长任务 Agent runtime 的在线调试链路。

完成 MCP 后可补一句：

- 将实验工具封装为 MCP server tools，使 Agent 可通过标准协议调用配置生成、训练、评估和报告工具，提升工具系统的可扩展性和协议兼容性。

## v0.2 新增简历证据

v0.2 后可以把项目表述升级为：

- 将轻量级 Agent Harness Runtime 接入真实非线性拟合训练链路，封装配置生成、训练执行、NMSE/PSD 验证和报告生成工具；训练工具捕获 stdout/stderr/returncode/elapsed time，runtime 自动记录 session 与 JSONL trace，并通过 replay 报告统计工具耗时、重试次数、指标事件和失败路径。

更强的面试表达：

> v0.1 我先实现了 harness 的抽象结构；v0.2 我把它接到真实实验命令上，证明 runtime 不是空架子。现在一次实验会生成 config、metrics、PSD、session、trace、agent report 和 replay report，能从结果回溯到每个工具调用的耗时、参数和状态。

## v0.3 新增简历证据

v0.3 后可以增加流式 runtime 表述：

- 为 Agent Harness 增加 SSE 流式服务层，将 start/tool_start/tool_end/metric/error/complete 等 runtime event 转为 `text/event-stream`，支持客户端实时观测工具调用状态、耗时、重试、指标和失败路径；通过 FastAPI app 工厂和 CLI 启动入口验证长任务 Agent 的在线可观测能力。

面试表达：

> 我把 Agent 内部执行事件做成标准 SSE 流，前端或 CLI 不需要等最终报告生成，就能实时看到正在执行哪个工具、耗时多少、是否失败、NMSE 等指标何时出现。这是长链路 Agent 从 demo 走向可调试系统的关键能力。

## v0.4 新增简历证据

v0.4 后可以把项目升级表述为：

- 接入 DeepSeek-compatible LLM Planner，将自然语言实验目标、参数约束和历史结果转为结构化实验计划 JSON；实现 plan-run-observe 多轮循环，由 planner 设计候选实验，Harness Runtime 执行配置生成/训练/NMSE 验证/报告工具，并将 metric events 回写为下一轮 observation，支持自动停止或继续优化。

更严谨的项目总表述：

> 先构建可观测实验 Harness 底座，再接入 LLM Planner 形成真正 Agent loop。底座负责工具治理、session、trace、SSE 和失败处理；Planner 负责根据目标与历史结果生成下一轮实验候选，执行层仍通过受控工具链完成实验。

## v0.4 追加：实验设计能力表达

- 在 LLM Planner prompt 中显式注入可执行设计空间、物理先验、参数预算和历史实验结果，引导模型设计 `complex_lstsq`、`tiny_mlp`、`spline_mlp` 等候选实验；新增 learnable 1D LUT + 16-knot first-order spline activation 的浅层非线性模型，并通过 Harness Runtime 自动执行、验证 NMSE/参数量、记录失败路径和汇总对比。

## v0.5 新增简历证据

- 为 LLM Planner 增加 schema guard 和参数预算预检查，支持 `train_samples -> max_train_samples` 字段映射，拒绝 `rank` 等非法控制字段，并在运行前估算 `complex_lstsq`、`tiny_mlp`、`spline_mlp` 参数量，避免 LLM 输出不可执行或超预算实验；被拒绝候选会写入 history 形成可审计失败记录。

## v0.5 追加：自我修正能力表达

- 通过真实 DeepSeek planner run 验证 plan-run-observe 反馈闭环：LLM 第一轮输出非法 `spline_range` 类型导致 spline_mlp 训练失败，Harness 将错误写入 history，第二轮 planner 根据错误修正为 scalar 并继续实验，第三轮基于 NMSE 结果选择 202 参数的 `complex_lstsq` 候选并主动停止。

## v0.6 追加：可观测实验记录表达

- 为 Agent Harness 增加 run artifact 自动落盘能力，结构化保存每轮 planner JSON、最终 result、按 NMSE 排序的 leaderboard.csv 与 summary.md，实现 LLM 实验循环的可复现、可审计和结果展示闭环。

## v0.7 追加：Schema Guard 表达

- 基于真实 DeepSeek planner 运行暴露的非法参数事故，补充 planner schema guard 和类型/值域预检，将 `spline_range=None/list`、神经模型 `epochs=0` 等不可执行计划在 runtime 前拒绝并写入 history，提升 Agent Harness 的稳定性、可审计性和自我修正输入质量。
