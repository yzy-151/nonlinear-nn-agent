# Experiment Agent Harness v0.7 总学习文档

更新时间：2026-07-22

这是当前主学习文档。你优先读这一份；旧版 `v0.1-v0.6` 保留为版本历史。

## 1. 项目定位

项目不是“自动训练脚本”，而是：

> 面向算法实验的 Agent Harness Runtime，用真实非线性系统建模任务展示 Agentic Loop、Tool Calling、Hook、Session、Trace、SSE、LLM Planner、Schema Guard、Run Artifact 和可评测迭代能力。

底层实验任务是非线性拟合，指标是 NMSE 和 PSD；求职重点不是通信算法本身，而是 Agent Harness 工程能力。

## 2. 总体架构

```text
User Goal
  -> LLM Planner
  -> Structured Experiment Plan
  -> Schema / Budget Guard
  -> Harness Runtime
  -> Tool Registry
  -> Training / Verify / Report Tools
  -> Trace / Session / Metrics
  -> History / Run Artifacts
  -> Planner revises or stops
```

关键原则：

- LLM 只负责提出结构化计划，不直接执行 shell。
- Runtime 负责工具执行、超时、错误、trace、session 和结果收集。
- Validation 负责把非法计划挡在训练脚本之前。
- Artifacts 负责让每次 run 可复盘、可比较、可写进简历。

## 3. 版本演进

| Version | 核心能力 | 你要会讲的点 |
|---|---|---|
| v0.1 | 自研 Harness Runtime | ToolRegistry、Hook、Session、Trace、async event loop |
| v0.2 | 接入真实实验工具 | generate_config、run_training、verify_artifacts、write_report、replay |
| v0.3 | FastAPI SSE | 长任务 Agent 的在线可观测、事件流接口 |
| v0.4 | LLM Planner Loop | 从固定 workflow 升级为 plan-run-observe Agent loop |
| v0.5 | Planner Schema Guard | LLM 输出不能绕过 schema、字段和参数预算 |
| v0.6 | Run Artifacts | plan/result/leaderboard/summary 自动落盘 |
| v0.7 | Validation Guard 强化 | 将真实 traceback 转化为 preflight rejected history |

## 4. 核心知识点

### Agent Harness 和普通 LLM API 的区别

普通 LLM API 只回答一次。Agent Harness 负责把模型输出接到真实工具链上，并保证执行过程可控：

- 工具定义、注册、调用、失败语义。
- Hook 和 Trace 记录链路。
- Session 保存可恢复状态。
- Validation 控制 LLM 的执行边界。
- Runtime 把工具结果转成下一轮 observation。

### Tool Calling 怎么讲

本项目里工具不是随便写的函数，而是受 runtime 管理的执行单元：

- 有统一输入输出。
- 有 timeout/retry。
- 错误结构化记录。
- 输出 metrics/artifacts 后写入 session。
- trace 记录工具名、状态、耗时、错误。

### 上下文和记忆现状

当前已有 `history`，用于把实验结果、错误、rejected record 回传给 planner。它还不是完整记忆系统。

下一步 v0.9 应补：

- short-term history window。
- run summary compression。
- rejected/failed/succeeded 经验沉淀。
- history 注入预算控制。

面试时要诚实讲：现在是实验 history 和 run artifacts，不是用户长期记忆系统。

### 自我修正证据

真实 DeepSeek run 中：

1. 第一轮输出非法 `spline_range` 类型导致训练失败。
2. 错误进入 history。
3. 第二轮 DeepSeek 根据错误改成 scalar。
4. 第三轮基于 NMSE 结果主动停止。

这证明当前 loop 已经具备初步反馈闭环：

```text
LLM proposes -> runtime executes -> error/metric enters history -> LLM revises -> LLM stops
```

### Schema Guard 为什么重要

LLM 可能输出：

- 不存在字段。
- 结果字段当控制字段。
- 超预算参数。
- 类型错误，例如 `spline_range=None/list`。
- 神经模型 `epochs=0`。

v0.5-v0.7 的 guard 会在 runtime 前拒绝这些计划，写入 `run_status=rejected`，避免训练脚本崩溃。

## 5. 面试高频问题回答

### 这个项目和普通脚本有什么区别？

普通脚本只跑固定流程。这个项目把实验拆成工具链，并实现 runtime：工具调用有 timeout/retry，执行前后有 hook，session 保存状态，trace 记录完整链路，LLM planner 根据历史指标动态设计下一轮实验，非法计划会被 schema guard 拒绝。

### Agent Harness 和直接调用 DeepSeek 有什么区别？

DeepSeek 只是 planner。Harness 才是执行系统：它约束模型输出、执行工具、记录 trace、保存 session、验证结果、生成 leaderboard，并把 observation 回传给下一轮 planner。

### 怎么证明 Agent 变强了？

当前证据是单次实验的 NMSE、invalid plan、rejected record 和 run artifacts。下一步 v0.8 要补 benchmark：固定 case 集，统计 target hit rate、invalid plan rate、runtime failure rate、best NMSE、预算使用量。

### 工具失败怎么办？

工具失败不会直接让系统不可解释地崩掉。runtime 捕获 error event，写入 history 和 trace；validation 类错误会变成 rejected；工具类错误会变成 failed；planner 下一轮能读取错误并修正计划。

### 为什么不用 LangGraph？

这个项目先自研轻量 runtime，是为了理解 Agent Harness 底层结构：ToolRegistry、Hook、Session、Trace、Validation、Event Stream。后续可以接 LangGraph，但不能只会调用框架 API。

## 6. 当前文件地图

核心 runtime：

- `src/nonlinear_agent/runtime.py`
- `src/nonlinear_agent/tools.py`
- `src/nonlinear_agent/hooks.py`
- `src/nonlinear_agent/session.py`
- `src/nonlinear_agent/trace.py`

真实工具：

- `src/nonlinear_agent/experiment_tools.py`
- `src/nonlinear_agent/replay.py`

服务层：

- `src/nonlinear_agent/server.py`
- `examples/nonlinear_fit/serve_harness.py`

LLM planner：

- `src/nonlinear_agent/llm.py`
- `src/nonlinear_agent/planner.py`
- `src/nonlinear_agent/loop.py`
- `src/nonlinear_agent/planner_validation.py`
- `src/nonlinear_agent/run_artifacts.py`
- `examples/nonlinear_fit/run_planner_loop.py`

测试：

- `tests/test_harness_runtime.py`
- `tests/test_experiment_tools.py`
- `tests/test_replay.py`
- `tests/test_server_streaming.py`
- `tests/test_llm_planner.py`
- `tests/test_planner_validation.py`

## 7. 简历表达

推荐主 bullet：

```text
设计并实现面向算法实验的 LLM-driven Agent Harness Runtime，将非线性系统建模实验拆解为配置生成、训练执行、NMSE/PSD 验证和报告生成工具链，支持 ToolRegistry、Hook、Session、Trace、SSE 事件流、DeepSeek Planner、Schema Guard、参数预算预检和 run artifact 自动落盘，实现 plan-run-observe 多轮实验闭环。
```

更偏 Agent Harness：

```text
构建可观测 Agent Runtime，统一治理工具 timeout/retry、结构化错误、session resume、JSONL trace 和 metric events；LLM 仅输出结构化 plan，执行层通过 schema guard 和受控工具链保证稳定性与可审计性。
```

## 8. 当前不足和下一版

当前不足：

- 没有 Agent 级 benchmark，无法系统回答“怎么证明 Agent 变强”。
- 没有完整上下文压缩/记忆模块。
- ToolRegistry 还没有显式 Skill/MCP 化。
- Self-reflection 还只是隐式通过 history 实现。
- SSE 有服务层，但没有 dashboard。

下一版 v0.8 做：

> Agent Evaluation Benchmark：固定 case 集、运行 fake/deepseek planner、统计 invalid plan rate、rejected rate、runtime failure rate、best NMSE、target hit rate 和预算使用量。

