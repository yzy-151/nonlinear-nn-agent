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

## Agent Harness 面试 Q&A

### Agent Harness 和直接调 LLM API 有什么区别？

直接调 LLM API 只解决“生成文本”。Agent Harness 解决“让模型安全、可观测、可恢复地调用工具完成长链路任务”。

本项目里：

- Planner 只输出结构化 JSON plan。
- Runtime 执行工具链。
- ToolRegistry 控制可调用工具。
- SessionStore 保存状态。
- TraceLogger 记录事件。
- ReflectionPolicy 复盘失败。
- Benchmark/Diagnostics 评估整体表现。

### 工具怎么定义、注册、发现、调用？

工具定义在 `experiment_tools.py`，注册到 `ToolRegistry`：

```text
generate_config
run_training
verify_artifacts
write_report
```

每个工具有 `ToolSpec`：

- name
- description
- input_schema
- category
- error_policy

Planner 通过 `describe_tools()` 看到工具能力。Runtime 根据 `ToolCall(name, args)` 调 `ToolRegistry.run()`，得到 `ToolResult`，再转成 `TraceEvent`。

### 工具调用失败怎么办？

分层处理：

1. schema/preflight 失败：记为 `rejected`，不执行工具。
2. timeout/tool error：记为 `failed`，写入 trace、session、history。
3. 指标不达标：记录 metric 和 error，由 reflection 判断下一步。

v1.3 之后错误有结构化 `error_type`，例如：

- `validation_error`
- `timeout_error`
- `tool_error`
- `metric_threshold_error`
- `cancelled`

### 上下文压缩怎么做？

`HistoryCompressor` 保留最近 N 条原始记录，把更久远历史压成摘要。摘要保留：

- covered_records
- status_counts
- best_experiment_id
- best_nmse_db
- best_parameter_count
- notable_errors

完整 history 仍保存在 `result.json`，只是不给 planner 全量注入。当前 reflection 也会作为 history record 进入下一轮 planner prompt。

### Reflection 和普通日志有什么区别？

日志记录发生了什么。Reflection 生成下一步怎么修：

- failure_causes
- recovery_actions
- avoid_next
- best_experiment_id
- best_nmse_db
- error_type_counts

它会进入下一轮 planner prompt，也会用于 run artifact、benchmark 分析和面试复盘。

### MCP 和 ToolSpec 什么关系？

`ToolSpec` 是项目内部工具描述。MCP 是跨进程工具协议。

本项目 v1.2 做了 MCP-compatible bridge：

- `ToolSpec -> MCP tool schema`
- `tools/list`
- `tools/call`
- JSON-RPC success/error response

底层仍复用 `ToolRegistry`，所以 LLM Planner 和 MCP client 共享同一套工具能力。

### 怎么证明 Agent 变强？

不能只看一次 demo。项目里有 benchmark 和 diagnostics。

核心指标：

- `target_hit_rate`：达标 case 数 / 总 case 数。
- `rejected_rate`：rejected 记录数 / 全部实验记录。
- `runtime_failure_rate`：failed 记录数 / 全部实验记录。
- `average_experiments_used`：消耗实验数 / case 数。
- `best_nmse_db`：全局最优 NMSE，越小越好。
- `error_type_counts`：错误类型分布，用于定位 guard、runtime、timeout、metric threshold 问题。

当前 benchmark 覆盖目标命中、非法计划拒绝、runtime 失败、reflection 恢复、预算耗尽。它可以比较 prompt、guardrail、runtime 改动前后的收益。

### 这个项目如何对应面试高频点？

| 高频点 | 本项目证据 |
|---|---|
| Harness Runtime | v0.1-v0.3 |
| Tool Calling | v1.0 |
| Context Management | v0.9 |
| Self-Reflection | v1.1 + history 注入 |
| MCP | v1.2 |
| Runtime Hardening | v1.3 |
| Evaluation | v0.8 + v1.4 + v1.6.2 |
| Demo/UI | v1.5 + v1.6 + v1.6.2 |

### 项目边界是什么？

这个项目不是 RAG 项目，不负责覆盖 BM25、Rerank、Ragas、GraphRAG。RAG 相关问题用 Storm 项目覆盖。

本项目主线是：

> Agent Harness / Runtime / Tool Calling / Context / Reflection / Evaluation / Delivery Surface

不要在面试里把它说成万能 Agent 平台。

## 当前证据文件

- `src/nonlinear_agent/runtime.py`
- `src/nonlinear_agent/tools.py`
- `src/nonlinear_agent/hooks.py`
- `src/nonlinear_agent/session.py`
- `src/nonlinear_agent/trace.py`
- `tests/test_harness_runtime.py`
- `docs/learning/experiment-agent-harness-v0.1.md`
- `docs/handoff/llm-continuation-plan.md`
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

## v0.8 追加：Benchmark Evaluation 表达

- 构建 Agent 级 benchmark evaluation，设计固定 case 集覆盖目标命中、非法 planner 输出和 runtime 失败等场景，统计 target_hit_rate、rejected_rate、runtime_failure_rate、best_nmse_db 与实验预算使用量，用指标评估 planner prompt、schema guard 和 runtime 改动效果。

## v0.9 追加：Context Compression 表达

- 为 LLM Planner Loop 增加上下文压缩机制，将完整实验历史保留在 run artifacts 中用于审计，同时只向模型注入 `history-summary` 与最近窗口，摘要保留状态统计、最佳指标和代表性错误，降低 token 成本并提升多轮实验规划的可控性。

## v1.0 追加：Tool Registry / Skill 化表达

- 为 Agent Harness 工具系统增加 ToolSpec 描述层，支持工具名称、用途、输入 schema、类别和错误策略的结构化注册，并通过 `ToolRegistry.describe_tools()` 向 LLM Planner 渐进式披露可用工具能力，实现工具发现、调用边界控制和 unknown tool 结构化失败处理。

## v1.1 追加：Reflection / Recovery Policy 表达

- 为 LLM Planner Loop 增加 Reflection / Recovery Policy，在每轮实验后结构化生成失败原因、修正策略和下一轮避免项，并将 rejected/failed/succeeded 状态、最佳指标和 recovery actions 写入 run artifacts，提升 Agent 自我修正、错误复盘和面试可解释性。

## v1.2 追加：MCP Server / Tool Protocol 表达

- 为 Agent Harness 增加 MCP-compatible Tool Protocol Bridge，将内部 ToolSpec 映射为 MCP tool schema，并实现 tools/list、tools/call 的 JSON-RPC 处理；底层复用 ToolRegistry 和真实实验工具链，使 LLM Planner 与 MCP Client 共享同一套工具能力边界。

## v1.3 追加：Async Runtime Hardening 表达

- 为 Agent Harness Runtime 增加结构化错误分类、取消/中断、超时与重试策略、step-level resume 能力，使长链路工具调用具备可观测、可恢复和可控失败处理能力；错误类型贯通 ToolResult、TraceEvent、Session 和 Reflection，支持后续 benchmark 分析。

## v1.4 追加：Evaluation Dashboard / Runtime Diagnostics 表达

- 构建 Agent Runtime diagnostics dashboard，聚合 benchmark 与 planner-loop artifacts，统计 target_hit_rate、rejected_rate、runtime_failure_rate、error_type 分布、最佳 NMSE 和实验预算使用情况，用于评估 prompt、guardrail 与 runtime hardening 改动收益。

## v1.5 追加：Unified CLI / Local Dashboard Client 表达

- 为 Agent Harness 增加统一命令行交付面和本地 HTML diagnostics dashboard，将 planner loop、benchmark、diagnostics、SSE server 等分散入口收敛为一个 CLI，并支持一键生成可分享的 runtime dashboard，降低复现实验和展示系统可观测性的成本。

## v1.6 追加：Final Docs / Onboarding / Demo UI 表达

- 将 Agent Harness 项目收口为可展示交付版本，补充新人上手文档、DeepSeek self-correction case study、Agent Harness 面试 Q&A，并为 FastAPI SSE runtime 增加浏览器首页 UI，支持从页面配置实验参数并实时查看工具调用事件流。

## v1.6.2 追加：维护定版 / 工程闭环表达

- 将 Agent Harness 定版为 v1.6.2，修复实验产物路径污染问题，使裸 `exp*`/`output*`/`result*` 输出自动归入 `reports/`；将 reflection recovery actions 写回 planner history，避免反思只落盘不参与下一轮决策；扩展 5-case benchmark 并同步 Web UI/Dashboard 指标说明，完成文档收敛和深色展示界面。

面试表达：

> v1.6.2 不是继续堆功能，而是补齐工程闭环：产物路径、决策上下文、benchmark 口径、文档边界和展示界面都统一起来。这个版本可以证明我不只会让 Agent 跑起来，也会维护它长期可复现、可审计、可交接。

## v1.9.0 追加：搜索对照与统计证据表达

- 在统一 Trial Protocol 下实现 Random Search / Optuna TPE / LLM without Reflection / LLM with Reflection 四策略真实对照：4 策略 × 5 seeds × 10 有效训练 trial = 200 个有效训练 trial（rejected 单独统计、不占用有效预算），每条 trial 记录真实 config/dataset/git hash。
- 用固定 bootstrap seed（2000 次采样、95% CI）与按 seed 配对 delta 做统计：Optuna TPE best NMSE 均值 -37.07 dB（std 0.27 dB）为四策略中最稳；Reflection 消融 paired delta +2.34 dB 不显著，报告如实结论为“未观察到稳定优势”，不挑选单 seed 展示。

面试表达：

> 我把“Agent 是否更优”从口头叙事变成可复算实验：固定协议、真实训练、hash 落盘、bootstrap 置信区间和 paired 消融。结论里有不显著的结果我也照实写——这比一个挑选出来的成功案例更有说服力。

复现命令：

```powershell
python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json --output-dir benchmarks/nonlinear-search-v1
```

报告：`docs/experiments/nonlinear-search-ablation-v1.md`。

## v2.0.0 追加：Runtime 可靠性与投递表达

- 实现 SQLite 控制面（请求去重、任务 lease、原子 claim、单调事件序列，WAL + busy timeout），并通过并发压测验收：重复执行率 0、事件丢失率 0、终态一致率 1.0、注入 10% 故障后恢复率 1.0。
- 为 SSE 增加事件 ID、15s heartbeat、显式 cancel 与 Last-Event-ID 断线重放；Trace 升级为层级 span（trace/span/parent/attempt/model/config_hash/token/cost）。
- Dashboard / Web UI 增加 Strategy Comparison 页面，展示 best-so-far、5-seed 分布、hit rate、rejected、runtime failure 与 paired delta。

面试表达：

> v2.0 证明 Runtime 的可靠性是可测量的：并发下同一请求只执行一次、断线重连不丢事件、注入故障后任务能恢复，这些都有压测报告和自动化测试支撑。

复现命令：

```powershell
python agent.py stress-runtime --concurrency 8 --requests 100 --failure-rate 0.1 --output-dir benchmarks/runtime-v2
```
