# Nonlinear NN Agent Harness：Agent 工程诊断报告

更新时间：2026-08-10

## 1. 审查范围与结论

本报告基于以下证据交叉审查：

- 当前 `main` 分支代码与最近提交；
- `README.md`、实验报告、Benchmark 原始 JSON/JSONL；
- `袁振洋_agent开发.pdf` 中“面向非线性建模实验的网络寻优 Agent”描述；
- 排除真实 API 长链路后的离线测试：263 tests，全部通过；
- BFCL、tau-bench、MLE-bench、MLAgentBench 等公开 Agent/ML Agent 评测方法。

总体判断：项目不是空壳或单纯自动训练脚本，已经具备较完整的 Agent Harness 工程骨架；但 LLM 自主行动、因果评测与持久化经验学习仍偏弱。当前最准确的定位是：

> 面向非线性建模实验的 LLM 规划与受控执行 Harness。LLM 负责生成候选实验配置，确定性 Runtime 负责 Guard、固定工具链执行、事件流、恢复和审计。

不应将当前版本描述为“LLM 自主选择任意工具并动态编排”的通用 Agent Runtime。

## 2. 已经具备的有效 Agent 工程证据

| 能力 | 当前证据 | 评价 |
| --- | --- | --- |
| Agentic Loop | `loop.py` 实现 plan -> validate -> execute -> observe -> reflect | 真实存在；以轮次和批量实验为单位 |
| Planner/Runtime 解耦 | Planner 只生成结构化计划，Runtime 不依赖具体 LLM | 边界清晰 |
| Schema Guard | 字段、类型、模型、参数预算、输出路径校验 | 是项目强项 |
| Tool Runtime | ToolRegistry、ToolCall、timeout、retry、error taxonomy | 工程完整，但工具序列目前固定 |
| 可观测性 | SSE、Trace、Session、Artifact、Dashboard | 证据充分 |
| 可靠性 | SQLite 去重、lease、事件序列、Last-Event-ID replay、cancel | 本地单进程基线较完整 |
| Domain 解耦 | DomainPlugin 提供设计空间、Guard、工具与指标语义 | 可迁移边界成立 |
| 真实执行 | PyTorch/SciPy 非线性建模、NMSE、PSD、真实产物 | 避免了纯 mock Demo |
| 统计评估 | 多 seed、bootstrap CI、paired delta、原始 JSONL | 方法意识较强 |
| 工程质量 | 263 个离线测试通过 | 对个人项目是明显加分项 |

## 3. 主要缺口与 toy 风险

### 3.1 LLM 没有真正选择工具

当前 Planner 输出实验 `overrides`，随后 `NonlinearModelingDomain.build_harness_steps()` 固定生成：

```text
generate_config -> run_training -> verify_artifacts -> write_report
```

LLM 能决定“实验参数是什么”，不能根据 observation 决定“下一步调用哪个工具、是否重试、是否先读历史、是否跳过报告”。因此：

- 可以讲“受控 Tool Runtime”和“结构化计划驱动工具执行”；
- 暂时不宜讲“模型原生 Function Calling”或“自主工具编排”；
- 下一阶段应增加 action-level loop，但保留固定 workflow 作为可靠基线。

### 3.2 Reflection 消融存在混杂变量

`llm_program_reflection` 与 `llm_direct` 的差异不只包含 reflection facts：前者还独享 historical priors，模拟策略也会以固定概率直接从 prior 候选采样。因此 `-4.28 dB`、78% vs 28% 证明的是“带先验和反思的程序策略优于 direct”，不能单独证明 Reflection 的因果收益。

后续至少拆成四组：

```text
direct
history_only
history_plus_facts
history_plus_facts_plus_priors
```

各组必须保持模型、temperature、候选空间、预算、seed 和重试策略一致。

### 3.3 self-correction 指标定义不成立

当前 `self_correction_count` 只统计相邻记录的：

```text
rejected/failed -> succeeded
```

它没有确认中间发生了新的 Planner 调用，也没有确认新计划消费了对应错误。一个 batch 中预先生成的第二个实验成功，也会被计为“自我修正”。真实 DeepSeek v26 中多个所谓 correction 都发生在同一轮，因此不能作为 LLM 自我修正证据。

正确指标应要求完整因果链：

```text
failure_event
  -> reflection facts
  -> later planner_call_id
  -> plan context contains failure/reflection id
  -> changed candidate/action
  -> success or measurable improvement
```

### 3.4 当前 Benchmark 混合了三类不同问题

现有结果把以下指标放在同一张表：

- Agent 行为正确性；
- Runtime/Guard 回归；
- 非线性模型最终 NMSE。

这会导致 `target_hit_rate` 主导结果，而 invalid-plan、unknown-tool、reflection-recovery 等 case 在真实 LLM 模式下并未稳定触发它们声称测试的场景。例如真实 v26 的 reflection-recovery 没有 rejection、只运行一轮，实际上没有测试 reflection recovery。

50-case 也不是 50 个独立任务，而是 10 个模板重复修改阈值和轮数。它适合参数敏感性回归，不能包装成 50 个独立 Agent 任务。

### 3.5 Memory 仍是短期上下文，不是经验记忆

当前 HistoryCompressor 只做旧记录摘要加最近窗口，historical priors 是静态配置。缺少：

- 跨 run 的实验经验写入与检索；
- dataset/domain/config provenance；
- success/failure 记忆分层；
- 过期、冲突、污染与 namespace 隔离；
- 检索是否真正改善决策的消融。

本项目只做单 Domain 时，无需引入向量数据库。SQLite/JSONL 的结构化 episodic memory 足以形成可信证据。

### 3.6 MCP 与主循环的关系较弱

当前 MCP 是自研 JSON-RPC 兼容桥，有 tools/list 和 tools/call 测试，但不是官方 SDK Server，也没有成为 Planner Loop 的实际工具发现与调用通道。简历应写“MCP-compatible bridge”；若后续升级，应优先让同一份 ToolSpec 同时驱动本地 Registry 和 MCP schema，避免两套定义漂移。

### 3.7 测试时长较长，但当前测试不访问真实 API

首次全量 discover 在外层 120 秒命令限制下超时；排除 `test_real_llm_search.py` 后，263 个测试在 68.9 秒内通过。进一步源码核验确认：该文件虽然名为 real LLM search，但 DeepSeek client 均由 FakeLLM/mock 替换，测试目录未发现未 mock 的真实 API 调用。因此不能把超时归因于 `.env.local` 或网络。后续只需按耗时划分 fast/full profile，并让真正 online eval 使用独立命令，不需要为现有单元测试增加错误的网络隔离叙事。

## 4. 简历事实审计

### 4.1 必须立即修正

1. “50-case 全量验证命中率 0.9”应改为“真实 DeepSeek 10-case 运行 target hit 9/10”。当前 50-case 是 fake 参数化回归，hit rate 为 0.38。
2. “参数 24656 -> 19490”在仓库正式报告中未找到 24656 的原始证据。补齐可复算来源前应删除。
3. “Reflection 相比 Optuna”应改成“带历史先验的 program-reflection 策略相比 Optuna”，并注明当前离线搜索矩阵的 LLM 策略是模拟策略，否则容易让面试官误认为是全程真实 LLM。
4. “self-correction 3 次”暂时不应作为核心成果，现有定义不能证明 LLM 重新规划后修正。

### 4.2 可以保留

- plan -> validate -> execute -> observe -> reflect 链路；
- Planner、Guard、Runtime、ToolRegistry、Hook、Session、Trace 的模块拆分；
- timeout/retry/cancel、SSE、SQLite 控制面和本地压测结果；
- DomainPlugin 与真实非线性训练；
- -42.43 dB 与 19490 参数，但必须明确是单次最佳实验结果；
- 263 个离线测试和原始 JSON/CSV 可复算证据。

### 4.3 完成下一阶段后才能写

- LLM 自主 Tool Calling / action-level loop；
- 可验证的跨轮 self-correction success rate；
- Reflection facts 的独立因果增益；
- 跨 run episodic memory 与 memory-assisted hit rate；
- 15+ 个独立 Agent 行为任务及 pass@k。

## 5. Benchmark 重构原则

不存在可直接替换本项目评测的“官方非线性实验 Agent Benchmark”。BFCL 适合借鉴工具选择和参数 exact match，tau-bench 适合借鉴终态检查与 pass^k，MLE-bench/MLAgentBench 适合借鉴有限预算下的实验改进任务。项目应建立单 Domain、执行可验证的内部 Benchmark。

Benchmark 分成四层，禁止混为一个总分：

| 层级 | 测什么 | 核心指标 |
| --- | --- | --- |
| Contract Eval | JSON/action schema、工具名、参数、Guard | exact match、argument validity、rejection precision |
| Agent Task Eval | 多步决策、失败恢复、停止、预算遵守 | task success、pass@1、pass@3、causal correction rate |
| Search Quality Eval | 固定数据和预算下的实验质量 | best NMSE、AUC、target hit、cost、paired delta |
| Runtime Reliability | 并发、重复、断线、取消、故障注入 | duplicate rate、event loss、recovery、terminal consistency |

第一阶段只评估 `nonlinear-modeling` Domain，但任务必须是独立语义任务，不通过复制阈值凑数量。建议至少覆盖：

- 合法候选生成；
- 非法字段修正；
- 类型错误修正；
- 参数预算超限修正；
- 未知工具拒绝；
- 工具顺序依赖；
- 训练 timeout 后降预算；
- metric threshold 失败后换模型族；
- 重复候选避免；
- 历史最优利用；
- reflection facts 利用；
- conflicting history 处理；
- context compression 后保持约束；
- 达标后停止；
- 达到实验预算后停止；
- 报告产物缺失时补验证；
- cancel 后不继续发起训练；
- API/JSON 输出异常恢复。

## 6. 推荐实施路线

### P0：先把 Agent 证据做实

1. 定义 `AgentAction` 和 action-level loop，让 LLM 每次只选择一个允许的工具或 stop；固定 workflow 继续保留为 baseline。
2. 每个 action 记录 `planner_call_id`、`caused_by_event_ids`、tool schema、arguments、observation 和终态。
3. 重写 Benchmark case schema 与评分，建立 18 个独立单 Domain 行为任务。
4. 修正 self-correction 为因果指标，分离 Guard recovery、runtime recovery、metric improvement。
5. 把 reflection、history、prior 做正交消融。
6. 增加 fast/full 测试入口；真正 online eval 使用独立显式命令。

### P1：增加持久化实验经验

1. SQLite episodic memory：保存成功、失败、数据 hash、配置 hash、指标和来源 run。
2. Planner 按目标与约束检索 top-k 历史实验；所有 memory item 带 provenance。
3. 增加 memory off/on、污染记忆和 stale memory 测试。

### P2：安全和协议加分项

1. Tool output 视为不可信输入，加入 prompt-injection 与 oversized-output case。
2. ToolSpec 统一生成本地 Registry schema 与 MCP schema。
3. 评估官方 MCP SDK 迁移，但不为了标签重写稳定 Runtime。

## 7. 完成定义

方案 1 只有同时满足以下条件才算完成：

- 单 Domain 至少 18 个独立 Agent 任务，不用阈值复制凑 case；
- LLM 可逐步选择工具或 stop，action 经过 ToolSpec/Guard 校验；
- fixed workflow 与 action loop 均可运行，且结果可对照；
- self-correction 必须能追踪 failure -> new plan -> changed action -> outcome；
- direct/history/facts/priors 四组消融变量正交；
- Contract、Agent Task、Search Quality、Runtime Reliability 四套指标分开报告；
- 单元测试保持无网络；真实 LLM eval 使用独立显式命令；
- README、handoff、简历表述只引用可复算证据；
- 全量离线测试通过，关键真实 DeepSeek suite 至少完成 3 seeds 或报告实际限制。

## 8. 当前评级

| 维度 | 当前评级 | 完成 P0 后目标 |
| --- | ---: | ---: |
| Runtime 工程 | 8/10 | 8.5/10 |
| 可观测与可靠性 | 8/10 | 8.5/10 |
| LLM 自主决策 | 4.5/10 | 7.5/10 |
| Benchmark 有效性 | 5/10 | 8/10 |
| Memory | 3.5/10 | 6/10 |
| 简历证据可信度 | 6/10 | 8.5/10 |

当前最值得投入的不是继续追求更低 NMSE，而是让“Agent 为什么这样行动、失败后如何修正、评测如何证明”成为可运行、可追踪、可复算的主证据。

## 9. 本轮落地结果

本报告形成后已启动方案 1，当前只针对 `nonlinear-modeling` Domain：

- 已新增逐步 `AgentAction`/Action Guard/Action Planner Loop；fixed workflow 继续作为对照基线。
- 已记录 `planner_call_id`、`event_id`、`caused_by_event_ids`，并把旧相邻计数与因果纠错指标分开。
- 已建立 18 个语义独立任务及 outcome scorer，支持 pass@1/pass@k；尚未生成真实 DeepSeek pass rate。
- v3.5.0 已补确定性 fault fixture、CLI/SSE/WebUI runner 和逐 action provenance；scripted pass@1=1.0 仅作为 Harness 契约回归。
- 已把 history、facts、priors 拆为四组策略，并分别输出三段 paired increment。
- 已增加 fast/full 离线测试入口，并同步修正 README 与简历包装文档中的 benchmark 口径。

因此当前评级可以把“LLM 自主决策”的代码实现上调，但 Benchmark 有效性仍需等待确定性 fault environment、Web/CLI runner 和真实多 seed 结果后再上调。后续进度由本地维护文档持续记录。
