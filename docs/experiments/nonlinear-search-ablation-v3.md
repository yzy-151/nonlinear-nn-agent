# Nonlinear Search Ablation v3 — 策略对比放大至 1000 trial（合成回归域）

> 生成时间：2026-08-08 · 协议：4 策略 × 5 seeds × 50 trial = **1000 trial**（250 trial/方法）
> 数据：`benchmarks/synthetic-compare-v1000/`（trials.jsonl / summary.json / summary.csv / PNG）
> 复现：`python agent.py compare-search --domain synthetic --methods random_search,optuna_tpe,llm_direct,llm_program_reflection --seeds 7,17,29,43,61 --trial-budget 50 --parameter-count-max 100 --output-dir benchmarks/synthetic-compare-v1000`

## 1. 目的

v2 的搜索对照在真实非线性拟合域上受限于训练成本（200 有效 trial，单 trial 秒~分钟级）。本次把"**LLM vs Optuna vs Random 谁收敛更快**"的问题放大到 1000 trial：

- 合成回归域（`synthetic`）：单 trial 毫秒级真实计算，可承受 1000 次采样；
- 4 策略在同一数据划分、同一 seeds 下公平对照；
- 全程零 LLM 成本、零拒绝、零运行失败，统计干净。

## 2. 协议

| 项 | 值 |
| --- | --- |
| 领域 | synthetic（合成回归，真实前向计算） |
| 策略 | random_search / optuna_tpe / llm_direct / llm_program_reflection |
| seeds | 7, 17, 29, 43, 61（5 个） |
| trial 预算 | 50 / seed / 方法（合计 1000 trial） |
| 指标 | val_mse（越小越好） |
| 参数预算 | ≤100 参数（保证单 trial 毫秒级） |

## 3. 结果

### 3.1 最终最优

| 方法 | best val_mse mean | std | 95% CI |
| --- | ---: | ---: | --- |
| random_search | 0.0434 | 0 | [0.0434, 0.0434] |
| optuna_tpe | 0.0593 | 0.0114 | [0.0505, 0.0677] |
| llm_direct | 0.0434 | 0 | [0.0434, 0.0434] |
| **llm_program_reflection** | **0.0434** | 0 | [0.0434, 0.0434] |

### 3.2 收敛速度（首次触达该 seed 最优的 trial，0-based 平均）

| 方法 | 平均收敛 trial | per-seed |
| --- | ---: | --- |
| random_search | 18.6 | [4, 9, 31, 19, 30] |
| optuna_tpe | 26.0 | [9, 32, 46, 41, 2] |
| **llm_direct** | **11.4** | [4, 14, 5, 13, 21] |
| **llm_program_reflection** | **11.4** | [4, 14, 5, 13, 21] |

**LLM 两组收敛最快**（平均第 11.4 个 trial 触达最优），Random 次之（18.6），Optuna TPE 最慢（26.0）。在合成域上，邻域采样 + exploitation 的 LLM 式策略比 TPE 更早命中平台区；TPE 的前期建模样本在小设计空间上反而成为负担。

![四策略收敛速度对比](../assets/experiments/strategy-convergence-speed.png)

## 4. Reflection 消融

paired delta = 0，5 个 seed 完全一致，**不显著**。原因：合成域没有可注入的历史先验（`historical_priors()` 为空），`llm_direct` 与 `llm_program_reflection` 的采样行为相同——这符合设计预期：**reflection 的增益来自历史知识注入，没有知识可注入时两者等价**。真实非线性域的 reflection 增益见 v2（-4.28 dB、hit 78% vs 28%）。

## 5. 诚实边界

1. **LLM 策略在合成域是离线模拟**（`_LLMSearch`：围绕历史最优邻域采样 + reflection 规则，token=0），不调用真实 LLM。它回答的是"**这种 exploitation/exploration 编排在固定预算下的收敛行为**"，不代表真实 LLM 的推理质量；真实 LLM 能力用 `run_benchmark.py --provider deepseek` 单独评估。
2. **Optuna 在此域反而最慢**：设计空间小、随机与邻域采样很快命中平台区，TPE 的拟合开销无收益。不能外推到真实高维搜索空间。
3. **target_hit_rate 全 0**：该 run 的 target 阈值（0.04）高于合成域可达最优（0.0434），是阈值设置问题，不构成策略失败；best val_mse 与收敛速度才是本协议的有效指标。
4. **1000 trial 不改变 v2 结论**：v2（真实训练、20000 参数、200 有效 trial）仍证明 reflection + 历史先验在真实非线性域显著更优；v3 补充的是大规模固定预算下的收敛效率视角。

## 6. 复现命令

```powershell
python agent.py compare-search --domain synthetic --methods random_search,optuna_tpe,llm_direct,llm_program_reflection --seeds 7,17,29,43,61 --trial-budget 50 --parameter-count-max 100 --output-dir benchmarks/synthetic-compare-v1000
```
