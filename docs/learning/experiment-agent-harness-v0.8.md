# Experiment Agent Harness v0.8 总学习文档

更新时间：2026-07-22

这是 v0.8 历史学习文档。当前最新主学习入口是 `experiment-agent-harness-v0.9.md`。

## 1. 项目定位

项目不是“自动训练脚本”，而是：

> 面向算法实验的 Agent Harness Runtime，用真实非线性系统建模任务展示 Agentic Loop、Tool Calling、Hook、Session、Trace、SSE、LLM Planner、Schema Guard、Run Artifact 和 Benchmark Evaluation。

底层实验任务是非线性拟合，指标是 NMSE 和 PSD；求职重点是 Agent Harness 工程能力。

## 2. 版本演进

| Version | 核心能力 | 面试价值 |
|---|---|---|
| v0.1 | 自研 Harness Runtime | ToolRegistry、Hook、Session、Trace、async event loop |
| v0.2 | 接入真实实验工具 | 工具链不是空架子，能跑真实训练和验证 |
| v0.3 | FastAPI SSE | 长任务 Agent 的在线可观测 |
| v0.4 | LLM Planner Loop | 从固定 workflow 升级为 plan-run-observe |
| v0.5 | Planner Schema Guard | LLM 输出不能绕过 schema 和预算 |
| v0.6 | Run Artifacts | plan/result/leaderboard/summary 自动落盘 |
| v0.7 | Validation Guard 强化 | 将真实 traceback 转化为 preflight rejected history |
| v0.8 | Benchmark Evaluation | 用固定 case 和指标证明 Agent 改动是否有效 |

## 3. 当前架构

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
  -> Benchmark Evaluation
```

关键原则：

- LLM 只负责提出结构化计划，不直接执行 shell。
- Runtime 负责工具执行、超时、错误、trace、session 和结果收集。
- Validation 把非法计划挡在训练脚本之前。
- Artifacts 让每次 run 可复盘。
- Benchmark 回答“怎么证明 Agent 变强”。

## 4. v0.8 新增内容

新增核心文件：

- `src/nonlinear_agent/benchmark.py`
- `examples/nonlinear_fit/run_benchmark.py`
- `tests/test_benchmark.py`

Benchmark 输出：

```text
benchmarks/<run-id>/
  results.json
  leaderboard.csv
  summary.md
```

当前离线 benchmark case：

- `target-hit`：验证强候选能命中目标。
- `invalid-plan`：验证非法 planner 字段会被 rejected。
- `runtime-failure`：验证 runtime metric failure 会被统计。

示例结果：

```text
case_count: 3
target_hit_rate: 0.3333
rejected_rate: 0.3333
runtime_failure_rate: 0.3333
average_experiments_used: 0.6667
best_nmse_db: -36.0
```

这些数字不是为了证明模型效果强，而是证明 harness 能区分成功、非法计划和 runtime 失败，并能稳定产出评测指标。

## 5. 核心知识点

### Agent Harness 和直接调 LLM API 的区别

DeepSeek 只是 planner。Harness 才是执行系统：它约束模型输出、执行受控工具、记录 trace/session、验证结果和产物、汇总 leaderboard，并把 observation 回传给 planner。

### Tool Calling 怎么讲

工具不是普通函数，而是受 runtime 管理的执行单元：统一输入输出、timeout/retry、结构化错误、session 写入、trace 记录。

### Schema Guard 怎么讲

Prompt 是软约束，schema guard 是硬边界。LLM 可能输出不存在字段、结果字段、超预算参数或错误类型。v0.5-v0.7 把这些错误变成 rejected history，而不是训练脚本崩溃。

### Benchmark 怎么讲

面试官问“你怎么证明 Agent 变强”，不能只说“感觉更稳定”。应该回答：

```text
我做了 Agent 级 benchmark。固定 case 集覆盖 target hit、invalid planner output、runtime failure 等场景；每次改 planner prompt、schema guard 或 runtime 后，统计 target_hit_rate、rejected_rate、runtime_failure_rate、best_nmse_db 和 average_experiments_used，用指标判断改动是否有效。
```

## 6. 面试回答模板

### 这个项目和普通脚本有什么区别？

普通脚本只跑固定流程。这个项目把实验拆成工具链，并实现 runtime：工具调用有 timeout/retry，执行前后有 hook，session 保存状态，trace 记录完整链路，LLM planner 根据历史指标动态设计下一轮实验，非法计划会被 schema guard 拒绝，并通过 benchmark 衡量版本质量。

### 工具失败怎么办？

validation 类错误变成 rejected；runtime 工具错误变成 failed；成功结果变成 succeeded。三类状态都会写入 history、artifact 和 benchmark summary，下一轮 planner 可以据此修正。

### 怎么证明 Agent 变强？

用固定 benchmark case，不靠主观感觉。指标包括 target hit rate、rejected rate、runtime failure rate、best NMSE 和预算使用量。这样每次改 prompt、schema 或 runtime 都能比较。

## 7. 文件地图

核心 runtime：

- `src/nonlinear_agent/runtime.py`
- `src/nonlinear_agent/tools.py`
- `src/nonlinear_agent/hooks.py`
- `src/nonlinear_agent/session.py`
- `src/nonlinear_agent/trace.py`

LLM planner：

- `src/nonlinear_agent/llm.py`
- `src/nonlinear_agent/planner.py`
- `src/nonlinear_agent/loop.py`
- `src/nonlinear_agent/planner_validation.py`
- `src/nonlinear_agent/run_artifacts.py`

Benchmark：

- `src/nonlinear_agent/benchmark.py`
- `examples/nonlinear_fit/run_benchmark.py`
- `tests/test_benchmark.py`

## 8. 简历表达

推荐主 bullet：

```text
设计并实现面向算法实验的 LLM-driven Agent Harness Runtime，将非线性系统建模实验拆解为配置生成、训练执行、NMSE/PSD 验证和报告生成工具链，支持 ToolRegistry、Hook、Session、Trace、SSE 事件流、DeepSeek Planner、Schema Guard、参数预算预检、run artifact 自动落盘和 benchmark evaluation，实现可观测、可审计、可评测的 plan-run-observe 多轮实验闭环。
```

v0.8 单独 bullet：

```text
构建 Agent 级 benchmark evaluation，设计固定 case 集覆盖目标命中、非法 planner 输出和 runtime 失败等场景，统计 target_hit_rate、rejected_rate、runtime_failure_rate、best_nmse_db 与预算使用量，用指标评估 planner prompt、schema guard 和 runtime 改动效果。
```

## 9. 下一步

v0.9：Context / Memory Compression。

目标是回答面试最高频问题：上下文过长怎么办、什么时候总结、总结是否丢信息、长期记忆污染怎么处理。
