# Nonlinear NN Agent GitHub Summary

更新时间：2026-07-21

## 项目定位

这是一个面向 Agent 开发岗的实验自动化项目。项目把原始神经网络非线性拟合仿真脚本整理为可配置、可测试、可审计的实验工程，并在此基础上实现本地 Agent 工作流：

```text
实验请求 -> 实验计划 -> YAML 配置 -> 训练执行 -> NMSE 解析 -> PSD 验证 -> 摘要报告 -> 简历证据记录
```

## 当前核心成果

### 1. 原始 CNN 基线

最佳全量 CNN 实验：

```text
Experiment: experiment-good-adam
NMSE: -41.8089 dB
Epochs: 240
Optimizer: Adam
Learning rate: 0.0008
```

本地结果目录：

```text
reports/experiment-good-adam
```

注意：`reports/` 不提交到 GitHub，避免上传模型权重和实验产物。公开仓库保留配置、代码、测试和结果总结。

### 2. 4000 参数以内小模型搜索

当前最优小参数模型：

```text
Model: complex_lstsq
Feature: complex_mp
memory_depth: 150
mp_order_count: 12
parameter_count: 3626
NMSE: -37.4249 dB
```

配置文件：

```text
configs/model-search/lstsq-complexmp-o12-m150.yaml
```

结果表：

```text
docs/model-search-results.csv
docs/model-search-summary.md
```

### 3. Agent 工作流

入口：

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

## GitHub 展示建议

仓库中重点展示：

- `src/nonlinear_agent/experiment.py`
- `src/nonlinear_agent/agent_workflow.py`
- `src/nonlinear_agent/comparison.py`
- `tests/`
- `configs/model-search/`
- `docs/model-search-summary.md`
- `docs/model-search-results.csv`

简历表述：

```text
设计 Agentic Experiment Runner 用于神经网络非线性 MPDPD 拟合实验，构建计划生成、YAML 配置生成、训练执行、NMSE 指标解析、PSD 产物验证、实验对比和简历证据记录的自动化闭环。

在 4000 参数以内完成轻量模型搜索，将原 CNN 拟合思路改造为复数记忆多项式特征 + 闭式最小二乘模型，得到 3626 参数、NMSE -37.42 dB 的可解释小模型，并沉淀参数量/NMSE/配置路径对比表。
```

