# Case Study: DeepSeek Planner Self-Correction

更新时间：2026-07-23

## 1. 面试故事摘要

这个 case study 用来回答：

- Agent loop 和固定 workflow 有什么区别？
- 工具调用失败后怎么恢复？
- LLM planner 怎么利用历史结果修正下一轮计划？
- 怎么证明这个项目不是空壳 demo？

一句话版本：

> 我让 DeepSeek 在 4000 参数约束下自动设计非线性拟合实验。Harness 把每个候选实验转成受控工具链执行，记录 schema rejection、runtime failure、NMSE、PSD 和 reflection。真实运行中 DeepSeek 曾输出错误参数类型，系统把错误写入 history，下一轮 planner 根据错误修正参数并继续探索，最终找到 202 参数、NMSE -36.0275 dB 的轻量候选。

## 2. 任务目标

目标：

```text
在 4000 参数以内，寻找低 NMSE 的非线性系统拟合模型，并输出 PSD 结果图。
```

真实 DeepSeek run 的强化目标：

```text
Target NMSE <= -41 dB under 4000 trainable parameters.
最多 30 个实验，最长 3 小时，神经模型 epoch <= 50。
```

## 3. 系统如何限制 LLM

LLM 不允许直接执行 shell。它只能返回 JSON plan：

```json
{
  "summary": "try stronger memory polynomial candidates",
  "stop": false,
  "experiments": [
    {
      "id": "exp016",
      "reason": "near-budget complex memory polynomial",
      "overrides": {
        "model_type": "complex_lstsq",
        "feature_mode": "complex_mp",
        "memory_depth": 220,
        "mp_order_count": 9,
        "epochs": 0
      }
    }
  ]
}
```

执行前经过：

- schema guard
- 参数预算估算
- 类型/值域检查
- max experiments 限制
- timeout 限制

## 4. 真实失败

DeepSeek 在探索 `spline_mlp` 时输出过不可执行参数，例如 `spline_range` 类型不合法。

系统处理方式：

1. validation guard 在 runtime 前拒绝不可执行计划，记录 `run_status=rejected`。
2. 如果错误进入 runtime，则工具失败被记录为 `run_status=failed`。
3. 错误进入 `history`。
4. 下一轮 planner 看到 history 后修正参数。
5. v1.1 后还会生成 reflection record。

## 5. 真实结果

### Strong near-budget candidate

| Experiment | Model | Feature mode | Memory depth | MP order | Params | NMSE |
|---|---|---|---:|---:|---:|---:|
| exp016 | complex_lstsq | complex_mp | 220 | 9 | 3980 | -37.4875 dB |

![PSD for exp016](../assets/psd-exp016-best-41db-run.png)

### Lightweight self-correction candidate

| Experiment | Model | Feature mode | Memory depth | MP order | Params | NMSE |
|---|---|---|---:|---:|---:|---:|
| exp_019 | complex_lstsq | complex_mp | 24 | 4 | 202 | -36.0275 dB |

![PSD for exp_019](../assets/psd-exp019-self-correction-run.png)

## 6. 为什么没有达到 -41 dB 也有价值

这个项目不是单纯刷指标，而是证明 Agent Harness 能力。

这轮实验的价值：

- DeepSeek 能根据目标设计多组候选。
- Harness 能把候选转为可执行工具链。
- Schema guard 能拦截不可执行计划。
- Runtime 能记录 metric、error、trace、session。
- Reflection 能生成下一轮 recovery action。
- Diagnostics 能聚合多轮结果和失败分布。

没有达到 -41 dB 的判断也很重要：它说明当前 feature family 在 4000 参数约束下接近平台期，继续单纯增大 memory/order 收益很小。

## 7. 面试回答模板

### 问：你的 Agent 怎么 self-correct？

答：

> 我把 self-correction 拆成两层。第一层是 history feedback：每个候选实验的 rejected/failed/succeeded、错误信息和指标都会进入下一轮 planner prompt。第二层是显式 reflection：每轮结束生成 failure_causes、recovery_actions、avoid_next。比如 DeepSeek 输出过非法 `spline_range`，系统把错误记录下来，下一轮 planner 修正参数类型后继续实验。

### 问：这和普通 workflow 有什么区别？

答：

> 普通 workflow 是固定流程，最多跑预设参数。这个项目里 LLM planner 每轮根据目标、历史错误和指标重新设计候选实验；Runtime 只负责受控执行。Planner 和 Runtime 是分离的，所以它既有自主规划，又有工程边界。

### 问：工具失败怎么办？

答：

> 我分三类处理：preflight 失败记为 rejected，不进 runtime；工具执行失败记为 failed，写 trace/session/history；成功但指标不达标保留 metric，由 reflection 给出下一步方向。这样失败不是终点，而是下一轮规划的输入。
