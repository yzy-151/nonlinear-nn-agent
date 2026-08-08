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

## 3. 结果（Optuna 适配器修复后）

### 3.1 最终最优

| 方法 | best val_mse mean | std | 95% CI |
| --- | ---: | ---: | --- |
| random_search | 0.0434 | 0 | [0.0434, 0.0434] |
| optuna_tpe | 0.0434 | 8.5e-7 | [0.0434, 0.0434] |
| llm_direct | 0.0434 | 0 | [0.0434, 0.0434] |
| **llm_program_reflection** | **0.0434** | 0 | [0.0434, 0.0434] |

四策略最终都收敛到合成域全局最优 0.0434（degree=5, reg=1e-4）。**本协议的有效区分指标是收敛速度**，而非最终最优。

### 3.2 收敛速度（首次触达该 seed 最优的 trial，0-based 平均）

| 方法 | 平均收敛 trial | per-seed |
| --- | ---: | --- |
| random_search | 18.6 | [4, 9, 31, 19, 30] |
| optuna_tpe | 13.4 | [6, 15, 2, 19, 25] |
| **llm_direct** | **11.4** | [4, 14, 5, 13, 21] |
| **llm_program_reflection** | **11.4** | [4, 14, 5, 13, 21] |

收敛速度排序：**LLM（11.4）< Optuna（13.4）< Random（18.6）**。

![四策略收敛速度对比](../assets/experiments/strategy-convergence-speed.png)

## 4. 重要修正：Optuna 适配器 bug

第一版结果中 Optuna best=0.0593、收敛 26.0，**不是 Optuna 方法本身不行，而是适配器实现 bug**：

- `src/nonlinear_agent/search/optuna_search.py` 把设计空间的**离散枚举列表**（如 `reg_strength: [1e-4, 0.001, ..., 100]`）当**连续区间**用 `suggest_float` 采样；
- 结果：250 次采样命中合法 `reg_strength` 值 **0 次**，Optuna 只能采到 degree=5 + reg≈1e-4 的连续近似值（0.04336~0.04337），永远无法精确命中离散点 reg=1e-4（0.0434）；
- 该问题对所有含离散 float/int 枚举的 domain 都存在（nonlinear-modeling 的 `learning_rate`/`memory_depth` 等同样会采到非法值）；
- **修复**：按白名单离散采样——连续整数区间用 `suggest_int`，其余一律 `suggest_categorical`（保序值用 TPE 分类建模），并新增两个单测（`test_optuna_respects_discrete_enum_values` / `test_optuna_synthetic_reaches_global_optimum`）。

修复前后对比：

| 指标 | 修复前 | 修复后 |
| --- | ---: | ---: |
| Optuna best val_mse | 0.0593 | **0.0434** |
| Optuna 平均收敛 trial | 26.0 | **13.4** |
| 合法值命中 | 0/250 | 全部 |

## 5. 为什么 random 的 std=0（"random 凭什么"）

RandomSearch 内置**去重**（SHA-256 去重 + 重采样，等价于无放回洗牌），而合成域只有 5×10=**50 个合法组合**，50 trial 预算 ≈ 枚举整个空间（每 seed 实际覆盖 42~50 个唯一组合）。因此：

- 每个 seed 都必然扫到全局最优 → best std=0、CI 为 0；
- **这不是 random 的优势，而是"trial 预算 ≈ 空间大小"的假象**：任何策略只要不犯蠢（如上面的 Optuna bug），最终都能到 0.0434；
- 四策略最终全部打平，说明**该合成域作为策略对照区分度不足**——真正能区分策略的是收敛速度，以及空间远大于预算的场景（真实 nonlinear-modeling 空间组合数远超 200 trial 预算，v2 中 reflection 获得 -4.28 dB 显著增益即证据）。

## 6. Reflection 消融

paired delta = 0，5 个 seed 完全一致，**不显著**。原因：合成域没有可注入的历史先验（`historical_priors()` 为空），`llm_direct` 与 `llm_program_reflection` 的采样行为相同——这符合设计预期：**reflection 的增益来自历史知识注入，没有知识可注入时两者等价**。真实非线性域的 reflection 增益见 v2（-4.28 dB、hit 78% vs 28%）。

## 7. 诚实边界

1. **LLM 策略在合成域是离线模拟**（`_LLMSearch`：围绕历史最优邻域采样 + reflection 规则，token=0），不调用真实 LLM。它回答的是"**这种 exploitation/exploration 编排在固定预算下的收敛行为**"，不代表真实 LLM 的推理质量；真实 LLM 能力用 `run_benchmark.py --provider deepseek` 单独评估。
2. **合成域空间只有 50 点**：50 trial 预算下任何无放回策略都近似全枚举，无法外推真实高维搜索空间。本协议的有效结论是**收敛速度排序**（LLM 11.4 < Optuna 13.4 < Random 18.6）。
3. **target_hit_rate 全 0**：该 run 的 target 阈值（0.04）高于合成域可达最优（0.0434），是阈值设置问题，不构成策略失败。
4. **1000 trial 不改变 v2 结论**：v2（真实训练、20000 参数、200 有效 trial）仍证明 reflection + 历史先验在真实非线性域显著更优；v3 补充的是大规模固定预算下的收敛效率视角。

## 8. 复现命令

```powershell
python agent.py compare-search --domain synthetic --methods random_search,optuna_tpe,llm_direct,llm_program_reflection --seeds 7,17,29,43,61 --trial-budget 50 --parameter-count-max 100 --output-dir benchmarks/synthetic-compare-v1000

# Optuna 白名单采样回归测试
$env:PYTHONPATH = "src"
python -m unittest tests.test_search_baselines -v
```
