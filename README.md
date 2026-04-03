# Nonlinear NN Experiment Agent

## 2026-07-21 更新：Experiment Agent Harness v0.1

本项目已经从“自动训练 Runner”升级为轻量级 Agent Harness 原型，新增能力集中在 Agent Harness / Runtime 岗位需要的工程证据：

- `ToolRegistry`：把配置生成、训练、评估、报告等步骤抽象成可治理工具，支持 timeout 和 retry。
- `HookManager`：支持 `before_tool`、`after_tool`、`on_error`、`on_metric`，用于观测、审批、错误处理和指标采集。
- `SessionStore`：保存实验 session，支持后续 resume/replay。
- `TraceLogger`：输出 JSONL 执行链路，记录 event、tool、status、latency、payload、error。
- `ExperimentHarnessRuntime`：异步 Agentic Loop，以事件流形式执行工具链。

核心验证命令：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

配套文档：

- `docs/learning/experiment-agent-harness-v0.1.md`
- `docs/resume/experiment-agent-harness-resume.md`
- `docs/handoff/deepseek-continuation-plan.md`
- `docs/superpowers/plans/2026-07-21-experiment-agent-harness-v0.1.md`

更新时间：2026-07-18

## 项目定位

这个项目面向 Agent 开发岗，不把重点放在“通信仿真复现”，而是放在一个更可控、更能展示工程能力的场景：

> 给定一份已有的神经网络拟合非线性仿真代码，让 Agent 自动理解实验目标、生成实验计划、运行测试、管理实验结果，并输出可审计的摘要报告。

如果后续接入 LangGraph，本项目可以作为一个独立的 Agent 工程项目，不需要和 STORM 放在同一个仓库。

## 为什么这个方向合适

你已经有一份“神经网络拟合非线性”的仿真代码，这比从零找通信论文复现更适合作为项目起点：

- 代码真实存在，Agent 可以读、改、跑、测。
- 非线性拟合有明确输入输出和评价指标，适合自动实验。
- 可以做出 Agent 的完整闭环：计划、执行、验证、总结、失败恢复。
- 面试时能讲清楚工程价值，不会陷入“论文参数不完整、源码缺失”的坑。

这个项目的目标不是证明某个算法多先进，而是证明你能构建一个能维护实验代码的 Agent 系统。

## 目标用户

第一目标用户是你自己，场景是：

- 有一段 MATLAB/Python 仿真代码。
- 想快速验证不同网络结构、超参数、数据划分、噪声设置。
- 想保留每次实验的配置、日志、指标和总结。
- 想让 Agent 给出下一步实验建议，而不是只跑一遍脚本。

面向招聘时，可以把用户描述成：

> 面向算法实验开发者的 Agentic Experiment Runner，用于自动规划、执行、验证和总结机器学习仿真实验。

## 第一版功能范围

第一版做小而完整的闭环，不做复杂平台。

必须支持：

1. 读取项目中的实验代码和配置文件。
2. 生成实验计划文件，例如 `plans/experiment-001.md`。
3. 根据计划生成或修改实验配置，例如 `configs/experiment-001.yaml`。
4. 调用测试命令或训练脚本。
5. 读取输出指标，例如 loss、MSE、MAE、R2、运行时间。
6. 生成实验摘要，例如 `reports/experiment-001-summary.md`。
7. 记录失败原因和下一步建议。

第一版不要求：

- 自动大规模调参。
- Web 前端。
- 多用户权限。
- 云端训练。
- 复杂数据库。
- 论文级算法创新。

## 推荐目录结构

```text
nonlinear-nn-agent/
  README.md
  action-plan.md
  src/
    nonlinear_agent/
      __init__.py
      graph.py
      state.py
      tools.py
      planner.py
      runner.py
      summarizer.py
  examples/
    nonlinear_fit/
      README.md
      train.py
      model.py
      data.py
      config.yaml
  configs/
    experiment-001.yaml
  plans/
    experiment-001.md
  reports/
    experiment-001-summary.md
  tests/
    test_plan_schema.py
    test_runner_parse_metrics.py
    test_summary_generation.py
```

## LangGraph 设计

建议用 LangGraph 做状态机，而不是把逻辑写成一个长脚本。

节点设计：

```text
intake_request
  -> inspect_codebase
  -> draft_experiment_plan
  -> human_approval
  -> write_experiment_config
  -> run_experiment
  -> parse_metrics
  -> verify_result
  -> summarize_report
  -> suggest_next_experiment
```

状态字段：

```python
class ExperimentState(TypedDict):
    request: str
    codebase_path: str
    plan_path: str
    config_path: str
    command: str
    run_status: str
    metrics: dict[str, float]
    artifacts: list[str]
    errors: list[str]
    summary_path: str
    next_actions: list[str]
```

关键点：

- `human_approval` 必须保留，体现 Agent 工程中的人类审批机制。
- `run_experiment` 必须有超时、退出码、stdout/stderr 捕获。
- `parse_metrics` 不要靠口头总结，要从日志或 JSON 指标文件读。
- `verify_result` 要判断指标是否存在、是否 NaN、是否比 baseline 合理。
- `summarize_report` 要输出可复现命令和配置路径。

## 实验计划文件格式

Agent 生成的计划文件建议固定格式：

```markdown
# Experiment 001 Plan

## Goal

验证神经网络是否能稳定拟合目标非线性函数。

## Baseline

- Model: MLP
- Hidden layers: [64, 64]
- Activation: ReLU
- Optimizer: Adam
- Learning rate: 0.001
- Epochs: 200

## Metrics

- Train MSE
- Validation MSE
- MAE
- R2
- Runtime seconds

## Command

```powershell
python examples/nonlinear_fit/train.py --config configs/experiment-001.yaml
```

## Success Criteria

- 训练脚本退出码为 0。
- 指标文件存在。
- Validation MSE 不是 NaN。
- 报告记录配置、命令、指标和下一步建议。
```

## 报告摘要格式

```markdown
# Experiment 001 Summary

## Result

- Status: succeeded
- Validation MSE: 0.00042
- MAE: 0.013
- R2: 0.998
- Runtime: 31.2s

## What Changed

本次实验使用两层 MLP 拟合非线性函数，并记录训练/验证指标。

## Evidence

- Config: configs/experiment-001.yaml
- Command: python examples/nonlinear_fit/train.py --config configs/experiment-001.yaml
- Metrics: reports/experiment-001-metrics.json

## Interpretation

模型能够拟合目标函数，但需要进一步测试噪声鲁棒性和外推能力。

## Next Actions

1. 增加噪声数据集。
2. 对比 Tanh、ReLU、SiLU 激活函数。
3. 加入 train/validation 曲线保存。
```

## 简历包装

第一阶段完成后，可以写：

```text
设计并实现 LangGraph Experiment Agent，面向神经网络非线性拟合实验，支持自动生成实验计划、写入 YAML 配置、调用训练脚本、解析 MSE/MAE/R2 等指标、验证运行结果并生成 Markdown 实验摘要。

通过状态机拆分 request intake、code inspection、planning、human approval、execution、metric parsing、verification、summarization 等节点，构建可审计、可恢复的 Agent 实验闭环。
```

如果后续加测试和 GitHub：

```text
为实验配置解析、指标提取、失败处理和摘要生成补充 pytest 回归测试，并通过 GitHub Actions 验证核心流程，提升实验 Agent 的可复现性和维护性。
```

## 与 STORM 项目的关系

STORM 项目用于证明你能读懂和二次开发成熟 Agent 框架。

本项目用于证明你能从零设计一个垂直场景 Agent，并把它做成工程闭环。

两者在简历中可以这样分工：

- STORM MiniMax：成熟 Agent 框架二次开发、模型/检索/中文输出/工程修复。
- Nonlinear NN Experiment Agent：LangGraph 状态机、工具调用、实验自动化、测试验证、摘要生成。

## 第一周行动计划

### Day 1

整理已有神经网络非线性拟合代码，确认入口命令、依赖、输入输出和指标格式。

### Day 2

把原始脚本改成可配置运行：支持 YAML 配置、固定随机种子、输出 metrics JSON。

### Day 3

实现最小 Runner：给定 config，运行训练脚本，捕获退出码、stdout、stderr。

### Day 4

实现 metrics parser 和 verifier：读取 JSON 指标，检查 NaN、缺失字段、阈值条件。

### Day 5

实现 plan/report 模板：自动生成实验计划和总结报告。

### Day 6

接入 LangGraph：把 planner、runner、parser、verifier、summarizer 串成状态机。

### Day 7

补测试、整理 README、准备 GitHub 仓库和简历 bullet。

## 当前已整理状态

已有仿真代码已整理为：

```text
examples/nonlinear_fit/
  config.yaml
  train.py
  data/
    Simulation_MPDPD_Data.mat
    Simulation_MPDPD_Data_00.mat
  legacy/
    5-3CNN复数神经网络MP模型.py
```

新的训练入口：

```powershell
python examples\nonlinear_fit\train.py --config examples\nonlinear_fit\config.yaml
```

默认配置是全量样本实验：

- `max_train_samples: null`
- `epochs: 240`
- `optimizer: adam`
- 主指标：`nmse_db`
- 展示图：`reports/experiment-good-adam/psd.png`

一次全量验证结果：

```json
{
  "status": "succeeded",
  "samples": 16379,
  "train_samples": 16378,
  "evaluation_samples": 16379,
  "epochs": 240,
  "final_train_loss": 1.5361374647735619e-06,
  "nmse_db": -41.80887222290039
}
```

PSD 图遵循原始 CNN 脚本的画法：

```python
plt.psd(x[M:], Nfft, Fs, label="x")
plt.psd(d[M:], Nfft, Fs, label="d")
plt.psd(e_fix, Nfft, Fs, label="with MPDPD")
```

第一步不是直接写 Agent，而是先把仿真代码改造成“可被 Agent 调用”的形式：

- 命令行入口稳定。
- 配置文件稳定。
- 指标输出稳定。
- 错误日志稳定。

Agent 项目的上限，取决于底层实验代码是否可自动运行、可解析、可验证。

## 已有测试

```powershell
python -m unittest tests.test_experiment_core -v
python -m unittest tests.test_agent_workflow -v
```

当前覆盖：

- NMSE 计算公式。
- MP 记忆多项式特征生成。
- YAML 配置与默认值合并。
- Agent 生成实验计划、配置、摘要和求职变更记录。
- Agent 解析带 warning 的训练 stdout。

## Agent 工作流

第一版 Agent 已实现为本地可测试状态机，入口：

```powershell
python examples\nonlinear_fit\run_agent.py `
  --experiment-id agent-dry-run-001 `
  --goal "Validate the Agentic Experiment Runner loop for nonlinear NN MPDPD fitting and produce resume-ready evidence." `
  --base-config examples\nonlinear_fit\config_good_adam.yaml `
  --output-dir reports\agent-dry-run-001 `
  --epochs 2 `
  --learning-rate 0.001 `
  --optimizer adam `
  --nmse-threshold-db 5
```

Agent 节点逻辑：

```text
request
  -> write plan
  -> write config
  -> run experiment
  -> parse metrics
  -> verify NMSE + PSD
  -> write agent summary
  -> write resume change log
```

一次 dry-run 结果：

```json
{
  "status": "succeeded",
  "epochs": 2,
  "nmse_db": -26.957237720489502,
  "plan_path": "plans/agent-dry-run-001.md",
  "config_path": "configs/agent-dry-run-001.yaml",
  "summary_path": "reports/agent-dry-run-001/agent-summary.md",
  "resume_log_path": "docs/resume-change-logs/agent-dry-run-001.md"
}
```

求职展示材料：

- `plans/agent-dry-run-001.md`
- `configs/agent-dry-run-001.yaml`
- `reports/agent-dry-run-001/agent-summary.md`
- `docs/resume-change-logs/agent-dry-run-001.md`

## 实验对比报告

下一阶段已加入实验对比模块：

```powershell
python examples\nonlinear_fit\compare_experiments.py `
  --experiments reports\agent-dry-run-001 reports\experiment-full-adam reports\experiment-good-adam `
  --output docs\experiment-comparison.md
```

报告输出：

- `docs/experiment-comparison.md`

当前排序结果：

| Experiment | NMSE dB | Epochs | Optimizer | LR |
|---|---:|---:|---|---:|
| experiment-good-adam | -41.8089 | 240 | adam | 0.0008 |
| experiment-full-adam | -41.2165 | 120 | adam | 0.001 |
| agent-dry-run-001 | -26.9572 | 2 | adam | 0.001 |

这个模块把单次实验结果升级为可比较、可解释、可写进简历的证据链。

## 小参数模型搜索

最新目标是在参数量不超过 4000 的约束下，寻找性能尽可能好的模型。

当前最优：

```text
Model: complex_lstsq
Feature: complex_mp
memory_depth: 150
mp_order_count: 12
parameter_count: 3626
NMSE: -37.4249 dB
```

产物：

- `configs/model-search/lstsq-complexmp-o12-m150.yaml`
- `reports/model-search/lstsq-complexmp-o12-m150/metrics.json`
- `reports/model-search/lstsq-complexmp-o12-m150/psd.png`
- `docs/model-search-summary.md`
- `docs/model-search-results.csv`

核心工程改动：

- 增加 `parameter_count` 统计。
- 增加 `tiny_mlp`、`linear`、`complex_lstsq` 模型。
- 增加 `legacy_abs` 与 `complex_mp` 两种特征模式。
- 增加 `target_mode: direct/residual`。
- 增加 `mp_order_count` 控制复数 MP 特征阶数。
- 将模型搜索过程沉淀为结果表和展示说明。

## 简历表述

当前可写：

```text
设计 Agentic Experiment Runner 用于神经网络非线性 MPDPD 拟合实验，构建计划生成、YAML 配置生成、训练命令执行、NMSE 指标解析、PSD 产物验证、Markdown 摘要和求职变更记录生成的自动化闭环。

将原始单脚本 CNN 仿真实验重构为可配置、可测试、可审计的实验工程，主指标 NMSE 达到 -41.81 dB，并沉淀可复现实验配置、PSD 结果图和 Agent 执行日志。

新增实验对比模块，自动读取多组训练结果的 metrics/config/PSD 产物，按 NMSE 排序生成 Markdown 对比报告，支持从多次实验中定位最佳配置并生成面试可解释证据。

在 4000 参数以内完成小模型搜索，将原始 CNN 思路改造成复数记忆多项式特征 + 闭式最小二乘模型，得到 3626 参数、NMSE -37.42 dB 的可解释轻量模型，并输出参数量/NMSE/PSD/配置路径对比表。
```

