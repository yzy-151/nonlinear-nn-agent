# Nonlinear Search Ablation v2 — 历史先验注入 + 20000 参数预算

> 生成时间：2026-08-04 · 协议：4 策略 × 5 seeds × 10 有效训练 trial = 200 有效 trial
> 数据：`benchmarks/nonlinear-search-v1-v20000/`（trials.jsonl / summary.json / summary.csv / PNG）
> 复现：`python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json --output-dir benchmarks/nonlinear-search-v1-v20000`

## 1. 本次改动：Reflection 读取历史先验

把项目里真实记载的历史最优候选整理成先验文件 `configs/priors/nonlinear-modeling.json`（来源：DeepSeek planner run 2026-07-22 的 exp016/exp019、`docs/model-search-results.csv`、`reports/` 扫描），`llm_with_reflection` 在建议候选时以 60% 概率从先验邻域出发；`llm_no_reflection` 不加载先验，只用当前轮 history。参数预算从 4000 提高到 **20000**（用户要求），`reports/017`（-38.56 dB @ 16034 参数）等历史最优因此进入先验。

## 2. 结果（真实训练，200 有效 trial + 74 rejected）

| 方法 | best NMSE mean | 95% CI | target hit | rejected | runtime fail |
| --- | ---: | --- | ---: | ---: | ---: |
| random_search | -36.02 | [-37.06, -34.85] | 10% | 32.1% | 0 |
| optuna_tpe | -37.02 | [-37.26, -36.81] | 22% | 34.5% | 0 |
| llm_no_reflection | -33.59 | [-37.44, -27.86] | 28% | 9.8% | 0 |
| **llm_with_reflection** | **-37.87** | [-37.87, -37.87] | **78%** | 24.0% | 10% |

**Reflection 配对消融（5 seeds 配对）**：

| 指标 | 值 |
| --- | ---: |
| paired delta mean | **-4.28 dB（负值 = with 更优）** |
| delta 95% CI | [-10.01, -0.42]（不跨 0） |
| significant | **true** |
| per-seed delta | seed7: -0.87 · seed17: -5.12 · seed29: -0.57 · seed43: -14.78 · seed61: -0.04 |

**结论：`llm_with_reflection` 相对 `llm_no_reflection` 出现显著且可复现的提升**（-4.28 dB，hit 率 78% vs 28%）。

## 3. 指标异常分析（诚实记录）

1. **with_reflection 的 best 方差为 0（std=0，CI 完全重合）**：5 个 seed 的最优 trial 全部收敛到先验 `reports-021`（-37.87 dB，mem 800 / mp 6）。提升主要来自**历史先验复用**，而非策略本身的探索稳定性——这是本设计的预期行为（先验即"知识注入"），但报告必须注明，不能把 std=0 解读为策略鲁棒性。
2. **先验 top-1（reports-017，-38.56 dB @ 16034 参数）在 300s 训练超时内不可复现**：smoke 中该候选 `run_training` 超时（trace 显示 300.5s），说明历史记录可能在更长预算/不同环境下完成；当前协议下它只贡献 runtime failure，不贡献 best。
3. **runtime failure 口径**：with_reflection 的 5 个失败全部来自 reports-017 超时；summary 的 `n_effective_trials` 含失败 trial（50），实际成功有效 45。
4. **no_reflection 方差大**（std 6.2）：无先验时 LLM 邻域采样在 20000 空间里容易困在弱候选（tiny_mlp/spline_mlp），部分 seed 好、部分 seed 差。

## 4. Benchmark 成熟化（v2.1）

### 用例 5 → 10

原 5 个（target-hit、invalid-plan、runtime-failure、reflection-recovery、budget-stop）+ 新增 5 个（json-tolerance 噪音 JSON 容错、parameter-budget-edge 预算边界、unknown-tool 非法工具拦截、long-history-compression 长历史压缩、multi-round-self-correction 多轮自我修正）。

### 新增指标

`planner_success_rate`（计划通过 Guard 比例）、`self_correction_count`（rejected/failed 后修正成功次数）、`average_rounds`、`total_prompt_tokens` / `total_completion_tokens` / `estimated_cost_usd`（真实 LLM token 用量与成本）、`tool_call_correct_rate`。LLM client 现在累计 usage；loop result 带回 token。

### Fake benchmark（离线基线，`benchmarks/fake-v21b`）

| 指标 | 值 |
| --- | ---: |
| case_count | 10 |
| target_hit_rate | 0.7（3 个 miss 均为设计预期的拦截/失败 case） |
| rejected_rate | 0.21 |
| planner_success_rate | 0.79 |
| self_correction_count | 2 |

### 真实 DeepSeek benchmark（`--provider deepseek`，`benchmarks/deepseek-v21-final`）

10 个 case 真实 LLM（deepseek-v4-flash）+ 真实训练，成本约 $0.06/run：

| 指标 | 值 |
| --- | ---: |
| target_hit_rate | 0.5 |
| rejected_rate | 0.85（planner_success 0.15） |
| self_correction_count | 6 |
| total tokens | 14,593 prompt + 48,962 completion |
| estimated_cost_usd | 0.0578 |

**真实 LLM 的关键发现：deepseek-v4-flash 对 JSON schema 的遵从性不稳定**。连续 5 次运行中，计划被 Guard 拦截的比例在 80%–98% 间波动；每次换一种违规方式（嵌套 `model/training/data`、`hidden_sizes/dropout/lr`、嵌套 `model_type` 等）。我们迭代了 4 轮改进（注入 allowed fields 白名单 → few-shot 合法示例 → 显式禁止词 → guard 别名规范化 `lr→learning_rate`、`hidden_sizes→hidden_units`、`model:mlp→tiny_mlp` + model_type 白名单），单调用验证可到 100% 合法，但全量运行时仍不稳定。

这说明：**对当前模型，JSON 自由生成 + 白名单 Guard 的契约是薄弱环节**；稳定的真实 LLM benchmark 需要更强的模型、工具调用式（structured tool use）约束或更宽松的规范化。Guard 的高拦截率是系统的正确防御，但暴露了上游 LLM 合规成本。

### 第二轮修复：Guard 拒绝自动重试（v2.1 追加）

针对真实 LLM 计划被 Guard 拒绝的问题，新增 `ExperimentPlannerLoop(planner_retries=N)`：某个实验被 Guard 拒绝后，把拒绝原因回喂给 LLM 重新生成计划（最多 N 次、每轮最多 1 次重试，避免连锁放大），重试候选通过 Guard 即正常执行。配套把训练超时从 300s 提升到 36000s（用户授权长时间运行），使 reports-017 等重候选可训练。

最终运行（`benchmarks/deepseek-v23`，36000s 超时 + 限频重试，约 36 分钟，$0.17）：

| 指标 | 值 |
| --- | ---: |
| target_hit_rate | 0.4（target-hit / invalid-plan / long-history / multi-round 命中） |
| rejected_rate | 0.893 |
| self_correction_count | 8 |
| total tokens | 32,636 prompt + 148,424 completion |
| estimated_cost_usd | 0.172 |

**修复结论（诚实）**：6 轮改进（allowed-fields 注入 → few-shot → 显式禁止词 → guard 别名规范化 + model_type 白名单 → 拒绝自动重试 → 重试限频）后，单次调用可做到 100% schema 合规，但 10 case 全量运行中 Guard 拦截率稳定在 **85%–91%**。这证明当前瓶颈是 deepseek-v4-flash 对复杂 JSON schema 的**模型级遵从性边界**，而非系统缺陷——Guard 始终正确拦截、没有让非法计划进入训练。稳定方案需换更强模型（deepseek-v4-pro）或改用 structured tool-use 约束；已具备的 retry 机制把 LLM 自我修正纳入了系统（self_correction_count=8）。

### 第三轮：-41 dB 参数还原 + Hermes/Claude 式契约 + 根因修复（v26 最终）

**1. 查出 -41 dB 的真实跑法**。全项目扫描发现达到 -41 dB 的不是 complex_lstsq，而是**神经模型长训练**：

| 实验 | 模型 | 参数 | NMSE |
| --- | --- | --- | ---: |
| reports/tiny_md20_mp3_hu96_relu_ep10000 | tiny_mlp | mem=20 mp=3 hu=96 relu **epochs=10000** | **-42.26** |
| reports/tiny_md20_mp3_hu128_relu_ep10000 | tiny_mlp | mem=20 mp=3 hu=128 relu epochs=10000 | -42.08 |
| reports/exp_492 | spline_mlp | mem=40 mp=1 hu=180 silu knots=32 epochs=4000 | -41.99 |
| runs/20260726-222348 | tiny_mlp | hu=256 | -41.34 |

这些参数已写入 `configs/priors/nonlinear-modeling.json`（slow 标记），并作为 **known-best 要求**注入 planner prompt。

**2. 借鉴 Hermes / Claude Code**：
- Hermes 的 `<tools>` + 精确 JSON schema → 本项目给 LLM **"必须照填的 JSON 模板"**（overrides 键与值类型固定），替代"可用字段列表"；
- Claude 的 structured outputs / system prompt 契约 → 强化 system prompt："只输出符合 schema 的 JSON，overrides 键必须来自 allowed 列表，model_type 必须来自白名单"。

**3. 找到并修复两个真实根因**（此前 85–91% 拦截不是模型不行，而是实现 bug）：
- `run_benchmark.py` 创建 DeepSeek planner 时**没有传 domain** → 上述注入全都没进 prompt；
- `ExperimentPlannerLoop.timeout_seconds` 默认 300 且 benchmark 未传 → 即使 runtime 设为 36000s，ToolCall 仍 300s 超时。

**v26 最终结果（10/10 case 真实运行，36000s 训练预算，约 $0.06）**：

| 指标 | v21-final（修复前） | v26（修复后） |
| --- | ---: | ---: |
| target_hit_rate | 0.5 | **0.9** |
| rejected_rate | 0.85 | **0.074** |
| planner_success_rate | 0.15 | **0.93** |
| best NMSE | -37.42 | **-42.43** |
| self_correction_count | 6 | 3 |

命中 case：target-hit **-42.43**、reflection-recovery **-42.26**、json-tolerance **-42.32**、long-history **-42.32**、multi-round **-40.98**、invalid-plan/budget-stop/parameter-budget-edge/unknown-tool（-38.4 ~ -38.7，guard 正确拦截边界）。唯一 miss 是 runtime-failure（设计为验证失败处理的 case）。

**-42.43 的诞生**：LLM 在 known-best（tiny_mlp mem=20/mp=3/hu=96/epochs=10000 → -42.26）基础上改进为 tiny_mlp mem=16/mp=3/hu=128/silu/**epochs=20000** → -42.43 dB，证明先验注入让 LLM 在已知最优邻域上继续搜索是有效的。

## 5. 复现命令

```powershell
python -m unittest discover tests

# fake benchmark（10 case，离线）
python agent.py benchmark --output-dir benchmarks/fake-v21b

# 真实 DeepSeek benchmark（10 case，真实 LLM + 真实训练，约 $0.06）
python examples\nonlinear_fit\run_benchmark.py --provider deepseek --output-dir benchmarks/deepseek-v21-final

# 搜索对照（20000 预算，200 有效 trial）
python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json --output-dir benchmarks/nonlinear-search-v1-v20000
```
