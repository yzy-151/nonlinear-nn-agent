# Nonlinear Search Ablation v1 — 4 策略 × 5 seeds 真实对照

> 生成时间：2026-08-04 · 协议版本：1.9.0
> 复现命令：见文末；原始数据：`benchmarks/nonlinear-search-v1/`（trials.jsonl / summary.json / summary.csv / best-so-far.png / reflection-ablation.png）

## 1. 协议与预算

在统一 Trial Protocol 下对比四种搜索策略：

| 项 | 值 |
| --- | --- |
| 方法 | `random_search`、`optuna_tpe`、`llm_no_reflection`、`llm_with_reflection` |
| seeds | 7, 17, 29, 43, 61 |
| 每个 method-seed 的有效训练 trial | 10（rejected 不计入有效预算，单独统计） |
| 有效训练 trial 总量 | 4 × 5 × 10 = 200 |
| 参数上限 | `parameter_count_max = 4000` |
| 达标阈值 | `nmse_threshold_db = -39.0 dB` |
| 数据 | `examples/nonlinear_fit/data/Simulation_MPDPD_Data.mat`（dataset SHA-256 写入每条 trial） |
| 训练超时 | 300 s / trial |

所有 trial 的 `config_hash`、`dataset_hash`、`git_commit` 均为实际值（见 trials.jsonl），不包含模拟字段。本报告的结论全部可从 `benchmarks/nonlinear-search-v1/` 复算。

## 2. 结果摘要

统计口径：每个 method-seed 取 10 个有效训练 trial 中的 best NMSE，再跨 5 seeds 汇总（mean / median / std / 2000 次 bootstrap 95% CI，bootstrap seed `20260802`）。

| 方法 | best NMSE mean (dB) | 95% CI | median | target hit rate | rejected rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| random_search | -36.07 | [-37.06, -35.05] | -36.69 | 8% [2%, 14%] | 43.9% |
| optuna_tpe | **-37.07** | [-37.30, -36.87] | **-37.05** | 26% [16%, 34%] | 45.7% |
| llm_no_reflection | -33.77 | [-36.93, -28.33] | -36.09 | 34% [12%, 64%] | 22.5% |
| llm_with_reflection | -31.43 | [-37.02, -25.83] | -36.54 | 38% [6%, 70%] | 13.1% |

要点：

- **Optuna TPE 的 best NMSE 均值最高且方差最小**（std 0.27 dB，CI 最窄），是当前 4000 参数约束下最稳定的策略。
- **两个 LLM 策略的 target hit rate 更高**，但 best NMSE 均值更差、跨 seed 方差明显更大（std 6.0 / 7.6 dB），说明其表现依赖 seed，不稳定。
- 所有方法的 `runtime_failure_rate = 0`。此前把 `metric_threshold_error` 误记为 runtime 故障，已修正分类（未达标是实验结果，不是运行时故障）。

## 3. Reflection 配对消融

`llm_with_reflection` vs `llm_no_reflection` 按 seed 配对（不混合不同 seed）：

| 指标 | 值 |
| --- | ---: |
| paired seed 数 | 5 |
| delta mean (dB) | +2.34（正值 = with 更差） |
| delta median (dB) | 0.0 |
| delta 95% CI | [-0.27, +7.30] |
| per-seed delta | seed7: 0.0 · seed17: +12.17 · seed29: 0.0 · seed43: 0.0 · seed61: -0.45 |
| 显著性 | **不显著（significant = false）** |

结论：**未观察到 `llm_with_reflection` 对 `llm_no_reflection` 的稳定优势**。点估计反而更差，且置信区间跨 0。本报告不展示单一 seed 或单一成功案例作为“Agent 更优”的证据。

实现说明：本实验的 LLM 策略为离线可复现的邻域采样模拟（读历史最优 + 30% 随机探索），`llm_with_reflection` 额外消费 ReflectionPolicy 事实、避免被拒/失败的 model_type。因此 `prompt_tokens / completion_tokens / estimated_cost_usd` 均为 0——这些数字不代表真实 LLM 成本，只代表该模拟器未调用 LLM API。真实 DeepSeek 调用的证据见 `docs/handoff/llm-continuation-plan.md`（exp016 / exp_019 案例）。

## 4. 失败与低效 case（不删除、不美化）

200 个有效 trial 之外，guard 拦截了 120 个 rejected 候选（单独统计，不计入有效预算）：

| 方法 | rejected 数 | 主要被拒 model_type |
| --- | ---: | --- |
| random_search | 43 | tiny_mlp ×22、spline_mlp ×19 |
| optuna_tpe | 48 | tiny_mlp ×25、spline_mlp ×19 |
| llm_no_reflection | 21 | spline_mlp ×13 |
| llm_with_reflection | 8 | tiny_mlp ×4、spline_mlp ×2 |

被拒原因集中在神经模型候选超出 4000 参数预算或字段非法，由 schema guard 在训练前拦截。`llm_with_reflection` 在被拒后不再重提同类 model_type，其 rejected 率最低（13.1%），但该“避免”行为并未转化为 best NMSE 优势。

## 5. 效率与成本

| 方法 | 平均训练时长 (s/有效 trial) |
| --- | ---: |
| random_search | 23.5 |
| optuna_tpe | 25.9 |
| llm_no_reflection | 15.3 |
| llm_with_reflection | 11.8 |

整体：200 个有效训练 trial + 120 个 rejected，全矩阵真实训练耗时约 65 分钟（本机单进程）。

## 6. 结论与边界

1. 在 4000 参数约束、-39 dB 目标下，**没有一种策略在所有指标上占优**：Optuna 在 best NMSE 上最稳，LLM 策略在 hit rate 上更高但方差大。
2. **Reflection 消融未观察到稳定优势**，这是需要诚实写入简历的结论，而不是挑选 seed 展示“自我修正成功”。
3. 本实验的 LLM 策略是确定性邻域采样模拟，不包含真实 LLM API 成本；真实 LLM 自我修正证据由 DeepSeek case study 单独提供。
4. 所有数据、hash、脚本均可复现；任何最终数字必须能追溯到 `trials.jsonl`。

## 7. 复现命令

```powershell
python -m unittest discover tests

# smoke：24 个有效训练 trial（2 seeds × 3 trials × 4 methods）
python agent.py compare-search `
  --methods random_search,optuna_tpe,llm_no_reflection,llm_with_reflection `
  --seeds 7,17 --trial-budget 3 --parameter-count-max 4000 `
  --nmse-threshold-db -39.0 --output-dir benchmarks/search-smoke

# full matrix：200 个有效训练 trial（rejected 不计预算）
python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json `
  --output-dir benchmarks/nonlinear-search-v1 --timeout-seconds 300

# 统计报告（summary.json/csv、best-so-far.png、reflection-ablation.png 自动生成）
python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json --dry-run
```
