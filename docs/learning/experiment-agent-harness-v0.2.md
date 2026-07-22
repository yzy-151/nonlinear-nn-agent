# Experiment Agent Harness v0.2 学习文档

更新时间：2026-07-22

## 这一版做了什么

v0.2 把 v0.1 的抽象 runtime 接到了真实非线性拟合实验上。v0.1 证明了 harness 结构能运行，v0.2 证明它能调真实工具、跑真实训练命令、验证真实 NMSE/PSD 产物，并把 trace 重放成报告。

新增核心文件：

- `src/nonlinear_agent/experiment_tools.py`：真实实验工具封装。
- `src/nonlinear_agent/replay.py`：读取 JSONL trace 并生成 replay 报告。
- `examples/nonlinear_fit/run_harness.py`：端到端 CLI demo。
- `tests/test_experiment_tools.py`：实验工具测试。
- `tests/test_replay.py`：trace replay 测试。

同时更新：

- `src/nonlinear_agent/runtime.py`：每个工具成功后保存 session，让后续工具能读取累计状态。
- `src/nonlinear_agent/tools.py`：增加 `tool_names()`，便于调试和测试工具注册情况。

## v0.2 的真实链路

CLI demo：

```powershell
python examples\nonlinear_fit\run_harness.py `
  --experiment-id harness-demo-v02 `
  --base-config configs\model-search\lstsq-complexmp-o12-m150.yaml `
  --output-dir reports\harness-demo-v02 `
  --epochs 0 `
  --nmse-threshold-db -35 `
  --timeout-seconds 120
```

实际工具链：

```text
generate_config
  -> run_training
  -> verify_artifacts
  -> write_report
  -> write_replay_report
```

本次 demo 结果：

```text
NMSE: -37.4249 dB
parameter_count: 3626
model_type: complex_lstsq
feature_mode: complex_mp
mp_order_count: 12
```

生成的本地产物：

- `configs/harness-demo-v02.yaml`
- `sessions/harness-demo-v02.json`
- `traces/harness-demo-v02.jsonl`
- `reports/harness-demo-v02/metrics.json`
- `reports/harness-demo-v02/psd.png`
- `reports/harness-demo-v02/agent-harness-report.md`
- `reports/harness-demo-v02/replay.md`

其中 `reports/`、`sessions/`、`traces/` 属于运行产物，默认不建议提交到 GitHub。

## 你应该从中学会什么

### 1. Tool Calling 的工程封装

`experiment_tools.py` 把真实训练流程拆成工具：

- `generate_config_tool`：读取基础 YAML，写入实验配置。
- `run_training_tool`：执行训练命令，捕获 stdout/stderr/returncode/elapsed time。
- `verify_artifacts_tool`：验证 `metrics.json`、`psd.png` 和 NMSE 阈值。
- `write_report_tool`：根据 session metrics/artifacts 生成求职展示报告。

关键理解：Agent 工具不是简单函数。工具必须有稳定输入、稳定输出、失败语义、可观测字段和可复现产物。

### 2. 真实 Agent Runtime 要能跨步骤传递状态

v0.2 修改 runtime：每个工具成功后都会保存 session。这样后续工具可以读取前面步骤累计的 metrics/artifacts。

这对应生产 Agent 里的 checkpoint/resume 思路：不是等所有步骤结束才保存，而是在关键节点保存可恢复状态。

### 3. Trace Replay 是可观测性的展示

`replay.py` 读取 JSONL trace，统计：

- tool calls
- total latency
- retry count
- metrics
- errors
- tool latency table

这就是面试里“如何定位 Agent 执行链路问题”的证据。如果某个训练工具慢、失败、重试过多，可以直接从 replay 报告看出来。

### 4. 这个项目已经从脚本升级为 Harness

v0.1：抽象 runtime 能跑。

v0.2：runtime 能跑真实实验，并产出 session、trace、report、replay。

这已经覆盖 Agent Harness 岗位中的：

- Agentic Loop
- Tool Calling
- Session Persistence
- Hook 基础
- Trace / Observability
- Failure handling
- Metric event stream
- Agentic coding evidence

## 面试讲法

可以这样讲：

> 我没有把项目停留在自动训练脚本，而是把实验过程抽象成 Agent Harness。每一步训练相关动作都是 tool call，runtime 会在工具执行前后产出事件、保存 session、记录 JSONL trace，并支持 timeout/retry。训练完成后，系统会验证 NMSE 和 PSD 产物，再基于 trace 生成 replay 报告，用于定位工具耗时、失败路径和指标变化。

如果被问“为什么这能证明 Agent Harness 能力”：

> 因为它不是只调用一次 LLM 或跑一次训练，而是实现了 harness 的几个底层组件：工具注册、异步执行、Hook、session、trace、replay 和报告。这些能力可以迁移到车载助手、科研实验、自动代码执行等多工具 Agent 场景。

## v0.3 前置知识

下一阶段要补：

1. FastAPI SSE：把 runtime event 变成在线事件流。
2. Cancel/Interrupt：模拟用户中断长任务。
3. MCP Server：把 experiment tools 暴露为标准协议工具。
4. LangGraph 对照版：用成熟框架实现同样流程，展示 checkpoint/resume/human interrupt。

## 当前不足

- 还没有 WebSocket/SSE 服务。
- 还没有 MCP server。
- `write_report` 现在从 session 读累计状态，但还没有复杂模板系统。
- 还没有 cancellation / barge-in 类中断逻辑。
- 还没有 GitHub Actions。

这些不足正好是 v0.3/v0.4 的任务。
