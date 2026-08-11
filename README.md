# Nonlinear NN Agent Harness

面向真实机器学习实验的 Agent Harness：让 LLM 设计实验、生成候选代码并根据验证事实迭代，同时由确定性运行时负责安全校验、真实训练、指标复核、过程观测和证据报告。

当前版本：`v4.1.0`。项目重点是 **Agent 工程闭环**，不是宣称 LLM 已经自动找到最强通信算法。

## 项目总览

[编辑领导版 Draw.io](docs/assets/architecture/nonlinear-agent-executive.drawio) · [编辑工程详细版 Draw.io](docs/assets/architecture/nonlinear-agent-system.drawio) · [打开详细版 SVG](docs/assets/architecture/nonlinear-agent-system.svg)

[![Nonlinear NN Agent 领导简化版](docs/assets/architecture/nonlinear-agent-executive.svg)](docs/assets/architecture/nonlinear-agent-executive.svg)

这套系统解决的不是“怎样多调用几次训练脚本”，而是怎样让 LLM 的实验决策进入一条可控、可恢复、可观测、可复算的工程链路：

1. **自主实验**：PlanAgent 提出假设，CodingAgent 生成完整候选包，ExecutionAgent 执行真实训练，WritingAgent 汇总证据。
2. **确定性护栏**：PlanGate、Schema/AST/path gate、ToolRegistry、隔离 worktree、预算和超时共同约束模型行为。
3. **证据闭环**：Evaluator 复核 NMSE、参数量与 PSD；Reflection 只提取事实，下一轮 LLM 再选择策略；报告只能引用已有 `evidence_id`。

## 当前能力

| 能力 | 状态 | 真实性边界 |
| --- | --- | --- |
| Multi-Agent Supervisor | 已接通 | `Idea/Plan → PlanGate → Coding → Execution → Writing → Terminal` 共用结构化 state |
| LLM Coding 闭环 | 已接通 | 输出完整 candidate package，经 JSON、路径、AST、契约与 smoke-training gate 后才可运行 |
| 真实训练与独立评测 | 已接通 | ExecutionAgent 只调用注册工具；Evaluator 复核有限指标和 artifact 路径 |
| Reflection 与重规划 | 已接通 | 程序只提取 metrics/failure facts，不用 `if` 规则替 LLM 决定下一步 |
| Trace 与控制面 | 已接通 | SSE、层级 trace、SQLite 幂等/lease/replay、取消与唯一终态 |
| WritingAgent 报告 | 已接通 | HTML/PDF 共用 `EvidenceBundle`；未知引用和不存在的数字会被拒绝 |
| Knowledge / typed Memory | 部分接通 | CLI/Action Loop 已消费检索上下文；Multi-Agent 注入仍为 `PLANNED` |
| 自主算法质量 | 尚未达标 | 真实 3×3 run 验证了工程闭环，但没有达到 `-41 dB` 目标 |

## 真实运行证据

一次连续 DeepSeek run 使用 `deepseek-chat` 承担 Idea/Plan、Coding 和 Writing，执行 3 round × 3 search experiments，并对全局最优候选独立终评。约束为固定 MPDPD 数据契约、`seed=42`、单候选不超过 4000 参数、epoch 不超过 50。

| 阶段 | 最佳候选 | 完成情况 | 最佳 NMSE | 参数量 |
| --- | --- | ---: | ---: | ---: |
| Round 1 | ComplexRational | 2/3 | -0.0474 dB | 146 |
| Round 2 | ComplexRationalV2 | 3/3 | -0.0272 dB | 34 |
| Round 3 | LUTSplineV3 | 3/3 | **-23.0778 dB** | **24** |
| Independent final | LUTSplineV3 | completed | **-23.0778 dB** | **24** |

总计 `8/9` 个搜索候选完成。该运行证明了候选代码生成、失败隔离、跨轮事实反馈、独立终评和报告收口；它**没有**命中 `-41 dB`，也没有超过项目历史先验模型。

[完整 6 页 PDF 报告](docs/reports/v4.0.0-e-deepseek-3x3-report.pdf) · [九次实验 NMSE](docs/assets/results/v4.0.0-e/nine-experiment-nmse.png) · [最终模型架构](docs/assets/results/v4.0.0-e/architecture.png)

![最终复评 PSD](docs/assets/results/v4.0.0-e/final-psd.png)

## 快速开始

环境要求：Python 3.9+，Windows / Linux / macOS。

```powershell
# 安装
pip install -r requirements.txt

# 离线跑一次 Agent Loop，不需要 API Key
python agent.py run --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\quickstart

# 启动 Web Operations Console
python agent.py serve --host 127.0.0.1 --port 8000

# 快速回归测试
python scripts/run_tests.py fast
```

真实模型调用使用环境变量，例如 `DEEPSEEK_API_KEY`；不要把密钥写进命令、配置文件、trace 或 Git。

## Operations Console

Web 首页默认进入 Multi-Agent。中栏的 Timeline、Console、Raw Events 来自同一 SSE 事件流；点击事件后，右侧 Inspector 展示 role、model、token、cost、latency、输入/输出引用和失败事实。

![v4.1.0 Hybrid Operations Console](docs/assets/ui/v4.1.0-operations-console.png)

页面还包含 Agent Planner、Fixed Workflow、Experiments、Benchmark、Memory、Reports 与 Diagnostics。Knowledge 文件入口目前明确标记为尚未接通，不会伪装成已经影响 Multi-Agent PlanAgent。

## 工程详细图

<details>
<summary>展开端到端工程架构图</summary>

[打开可缩放 SVG](docs/assets/architecture/nonlinear-agent-system.svg) · [打开 3200×1800 PNG](docs/assets/architecture/nonlinear-agent-system.png)

[![端到端 Agent Harness 工程详细图](docs/assets/architecture/nonlinear-agent-system.svg)](docs/assets/architecture/nonlinear-agent-system.svg)

</details>

主成功流为：

```text
Goal → Plan → Validate → Code → Execute → Evaluate → Reflect → Write → Evidence
```

失败流只回传裁剪后的验证事实：

```text
schema / coding / runtime failure
  → deterministic fact extraction
  → clean planner history
  → next-round LLM strategy selection
  → retry within budget or single terminal
```

## 如何编辑架构图

两张图都不是位图模板，主要节点、区域和连线均为独立 Draw.io 图形：

1. 打开 [diagrams.net](https://app.diagrams.net/) 或 Draw.io Desktop。
2. 选择 `File → Open from → Device`。
3. 打开领导版 `docs/assets/architecture/nonlinear-agent-executive.drawio`，或工程版 `docs/assets/architecture/nonlinear-agent-system.drawio`。
4. 修改节点和连线后，通过 `File → Export as → SVG / PNG` 导出展示文件；保留 `.drawio` 作为唯一可编辑源文件。

不要直接修改 PNG。README 默认展示 SVG，因为 SVG 在 GitHub 中可缩放且文字更清晰。

## 核心实现

| 模块 | 职责 |
| --- | --- |
| `supervisor_graph.py` | Multi-Agent 状态机、角色 handoff、预算、重规划与唯一终态 |
| `planner.py` / `plan_gate.py` | 结构化计划、引用和约束验证、rejected facts |
| `coding_agent.py` | 生成完整候选包，执行有限次数的事实驱动修复 |
| `model_plugins/` | `ModelPlugin`、`ModelDescriptor`、`CandidateRegistry` 与固定 runner |
| `execution_agent.py` / `runtime.py` | tool-only 执行、TraceEvent、session 与 artifact 发布 |
| `tools.py` | `ToolSpec`、`ToolCall`、`ToolResult` 和 `ToolRegistry` |
| `reflection.py` / `loop.py` | 确定性事实提取及下一轮 planner history 注入 |
| `writing_agent.py` / `reporting/` | `EvidenceBundle`、citation fidelity gate、HTML/PDF 报告 |
| `knowledge/` / `memory/` | 白名单知识摄入、混合检索、typed memory 与 provenance |
| `control_plane.py` | SQLite 幂等请求、lease、原子 claim 与事件重放 |
| `server.py` / `web/` | FastAPI、SSE 和无构建步骤的 Operations Console |
| `evaluation_statistics.py` | bootstrap 95% CI、paired delta 和策略汇总 |

## 实验领域

| Domain | 任务 | 主指标 |
| --- | --- | --- |
| Nonlinear Modeling | MPDPD 非线性建模与对消 | `nmse_db` |
| PIM Cancellation | 三阶 PIM 对消 | `res_db` |
| Register Config | 寄存器表单配置实验 | `final_mse_db` |
| Synthetic Regression | 可控合成回归评测 | `val_mse` |

通过 `DomainPlugin` 实现 `design_space`、`validate_candidate` 和 `build_tool_registry`，新领域可以复用 Planner、Guard、Runtime、Search、Trace 与 Web UI。

### NMSE 与 PSD

```text
NMSE = 10 * log10(mean(|prediction - target|²) / mean(|target|²))
```

NMSE 越低越好。PSD 图用于检查预测信号与目标信号在频域是否重合；搜索阶段的最佳值必须通过独立 final evaluation 才能进入最终报告。

## Benchmark 与验收

项目没有把单一自建分数包装成“官方 Agent benchmark”，而是分三层验证：

| 层级 | 回答的问题 | 主要指标 |
| --- | --- | --- |
| Agent behavior benchmark | Agent 是否正确计划、调用工具、消费失败事实并停止 | pass@k、planner success、causal correction、invalid action rate |
| Search comparison | 搜索策略在同一数据与预算下是否更有效 | best NMSE、target hit、rejected rate、bootstrap 95% CI、paired delta |
| Runtime stress | 控制面在并发和故障下注入是否可靠 | duplicate execution、event loss、terminal consistency、recovery rate |

Benchmark/Search 复用生产 `Guard`、`Runtime`、`ToolRegistry` 和 evaluator，不另外搭一条更容易通过的测试路径。

```powershell
python agent.py agent-benchmark --provider scripted --attempts 1 --output-dir benchmarks/agent-tasks-v1
python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json --output-dir benchmarks/nonlinear-search-v1-v20000
python agent.py stress-runtime --concurrency 8 --requests 100 --failure-rate 0.1 --output-dir benchmarks/runtime-v2
```

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `python agent.py run --provider fake` | 离线 Agent Planner Loop |
| `python agent.py run --provider deepseek` | 真实 LLM Planner Loop |
| `python agent.py multi-agent --provider deepseek --rounds 3 --experiments-per-round 3 --final-evaluation` | Multi-Agent 3×3 搜索与独立终评 |
| `python agent.py benchmark` | 传统 Harness 行为回归 |
| `python agent.py agent-benchmark` | 独立 action-level Agent 任务评测 |
| `python agent.py compare-search` | 四种搜索策略统一协议对照 |
| `python agent.py stress-runtime` | SQLite 控制面并发压测 |
| `python agent.py dashboard` | 生成离线诊断 Dashboard |

## 目录结构

```text
src/nonlinear_agent/       Agent、Harness、Guard、Memory、Knowledge、Report 与 Web 核心包
examples/nonlinear_fit/    非线性建模训练与评测入口
configs/                   baseline、example 与历史先验配置
benchmarks/                协议、逐 case 结果、统计摘要与压力测试证据
docs/                      学习文档、实验报告、交接说明和展示资源
tests/                     单元、集成、故障注入与 Web 契约测试
```

## 文档导航

- [新人上手指南](docs/onboarding/newcomer-guide.md)
- [最新学习文档 v1.6.2](docs/learning/experiment-agent-harness-v1.6.2.md)
- [唯一维护的后续计划与交接文档](docs/handoff/llm-continuation-plan.md)
- [真实 DeepSeek 3×3 PDF 报告](docs/reports/v4.0.0-e-deepseek-3x3-report.pdf)
- [独立 Agent 任务摘要](benchmarks/agent-tasks-v1/summary.md)
- [搜索策略历史实验 v3](docs/experiments/nonlinear-search-ablation-v3.md)

## 已知限制与下一步

- Multi-Agent 的 Knowledge/Memory 注入尚未接通；当前 UI 入口只是明确禁用的接口预留。
- 自由生成模型的算法效果明显弱于历史先验候选；下一步应把检索证据和可引用先验接入 Idea/Plan，并做 knowledge on/off 消融。
- Executor 仍应进一步强化从标准 prediction artifact 重算指标的能力，减少对候选自报字段的信任。
- 真实 LLM benchmark 成本较高；任何性能结论都应同时报告任务集、预算、seed、失败数、token 和成本。
