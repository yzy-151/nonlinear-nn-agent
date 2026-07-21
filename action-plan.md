# Nonlinear NN Experiment Agent Action Plan

更新时间：2026-07-18

## 当前目标

先把已有神经网络非线性拟合仿真代码整理成 Agent 可调用的实验底座。

第一阶段验收物：

- 稳定训练入口：`examples/nonlinear_fit/train.py`
- 稳定配置文件：`examples/nonlinear_fit/config.yaml`
- 稳定指标输出：`reports/experiment-001/metrics.json`
- 展示图：`reports/experiment-001/psd.png`
- 摘要报告：`reports/experiment-001/summary.md`

## 指标

主指标使用 NMSE：

```text
NMSE(dB) = 10 * log10(mean(|prediction - target|^2) / mean(|target|^2))
```

展示结果使用 PSD 图：

```text
input x
target d
error d - y_hat + x
```

## 后续 Agent 化路线

已完成第一版本地 Agent 状态机：

1. Agent 读取用户请求并生成实验计划。
2. Agent 写入 YAML 配置。
3. Agent 执行训练命令并捕获日志。
4. Agent 解析 `metrics.json`。
5. Agent 检查 NMSE 是否有效、PSD 图是否存在。
6. Agent 生成 Markdown 摘要。
7. Agent 生成面向简历和面试的变更记录。

## 当前求职证据链

```text
plans/agent-dry-run-001.md
configs/agent-dry-run-001.yaml
reports/agent-dry-run-001/agent-summary.md
docs/resume-change-logs/agent-dry-run-001.md
docs/experiment-comparison.md
docs/model-search-summary.md
docs/model-search-results.csv
reports/experiment-good-adam/psd.png
reports/experiment-good-adam/metrics.json
reports/model-search/lstsq-complexmp-o12-m150/psd.png
reports/model-search/lstsq-complexmp-o12-m150/metrics.json
```

## 阶段一副本

阶段一完整工程副本已保存：

```text
D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent-stage1-backup-20260719
```

这个副本用于慢慢阅读，不再作为后续开发主线。后续继续在原项目：

```text
D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent
```

## 下一阶段已完成

已加入实验对比模块：

```text
src/nonlinear_agent/comparison.py
examples/nonlinear_fit/compare_experiments.py
tests/test_experiment_comparison.py
docs/experiment-comparison.md
```

能力：

1. 读取多组实验目录。
2. 解析 `metrics.json` 和 `resolved_config.yaml`。
3. 检查 PSD 图是否存在。
4. 按 NMSE 从优到差排序。
5. 输出面向简历和面试的 Markdown 对比报告。

## 小参数模型搜索结果

目标：

```text
parameter_count <= 4000
metric = NMSE(dB), lower is better
```

当前最优：

```text
complex_lstsq + complex_mp
memory_depth = 150
mp_order_count = 12
parameter_count = 3626
NMSE = -37.4249 dB
```

关键产物：

```text
configs/model-search/lstsq-complexmp-o12-m150.yaml
reports/model-search/lstsq-complexmp-o12-m150/
docs/model-search-summary.md
docs/model-search-results.csv
```

简历角度：

```text
在 4000 参数以内完成模型搜索和结构归纳偏置设计，将原 CNN 拟合问题转化为复数记忆多项式特征 + 闭式最小二乘模型，得到 3626 参数、NMSE -37.42 dB 的可解释轻量模型。
```

## 下一阶段

1. 把当前本地状态机迁移为 LangGraph 节点。
2. 增加 human approval 节点，关键配置写入前需要确认。
3. 增加 failure recovery，训练失败时自动记录 stdout/stderr 和下一步建议。
4. 准备 GitHub README 和简历 bullet。
