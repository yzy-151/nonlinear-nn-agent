# Nonlinear NN Agent Harness 交接与维护文档

更新时间：2026-08-10

本文件是唯一维护中的交接文档。它合并了原 DeepSeek continuation plan、DeepSeek planner self-correction case study 和 experiment-agent-harness-plan。

## 1. 项目路径

```text
D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent
```

GitHub：

```text
https://github.com/yzy-151/nonlinear-nn-agent
```

不要把本项目误放到 `storm` 工作区执行。

## 2. 当前定位

目标岗位方向：Agent Harness / Runtime / Agent Coding / LLM 应用工程。

项目定位：

> 面向算法实验的 Agent Harness Runtime，用真实神经网络非线性拟合任务展示 Agentic Loop、工具系统、Hook、session 持久化、trace logging、失败重试、指标评估、reflection、benchmark、MCP bridge 和 Web UI。

不要写成“自动训练脚本”。应该写成“受控 Agent Runtime + 可观测实验工具链”。

## 3. 接手前必须运行

```powershell
cd D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent
python -m unittest discover tests
python agent.py benchmark
python agent.py dashboard
```

预期：测试通过，benchmark 生成 `benchmarks/` 产物，dashboard 生成 `docs/diagnostics/agent-runtime-dashboard.html`。

## 4. Git 操作规则

先检查：

```powershell
git status -sb
git diff --stat
```

不要覆盖用户未提交改动。提交前只 stage 本次相关文件。

不要提交：

- `.env.local`
- `.claude/settings.local.json`
- API key
- 大量 `runs/`、`reports/`、`benchmarks/` 运行产物
- `.pt`、`.pth`、`.xlsx`

如果网络需要代理：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7890'
$env:HTTPS_PROXY='http://127.0.0.1:7890'
git push origin main
```

## 5. 当前版本能力总览

| 版本 | 能力 | 主要文件 |
|---|---|---|
| v0.1 | Harness Runtime | `runtime.py`, `tools.py`, `hooks.py`, `session.py`, `trace.py` |
| v0.2 | 真实实验工具 | `experiment_tools.py`, `replay.py` |
| v0.3 | FastAPI SSE 服务层 | `server.py` |
| v0.4 | LLM Planner Loop | `llm.py`, `planner.py`, `loop.py` |
| v0.5 | Planner Schema Guard | `planner_validation.py` |
| v0.6 | Run Artifacts | `run_artifacts.py` |
| v0.7 | Validation Guard 强化 | `planner_validation.py` |
| v0.8 | Benchmark Evaluation | `benchmark.py`, `run_benchmark.py` |
| v0.9 | Context / Memory Compression | `context_memory.py` |
| v1.0 | Tool Registry / Skill 化 | `ToolSpec`, `describe_tools()` |
| v1.1 | Reflection / Recovery Policy | `reflection.py` |
| v1.2 | MCP Server / Tool Protocol | `mcp_server.py` |
| v1.3 | Async Runtime Hardening | `runtime_errors.py`, `run_control.py` |
| v1.4 | Diagnostics Dashboard | `diagnostics.py`, `dashboard.py` |
| v1.5 | Unified CLI / Local Dashboard | `cli.py`, `agent.py` |
| v1.6 | Onboarding / Demo UI | `web_ui.py`, docs |
| v1.6.1 | 状态审查修复 | path guard, reflection history, 5-case benchmark |
| v1.6.2 | 维护定版 | artifact path guard, reflection context, docs consolidation, dark UI |
| v1.7.0 | 仓库与实验协议收口 | `artifact_paths.py`, `configs/baselines|examples/`, `.gitignore` |
| v1.8.0 | Harness 与领域解耦 | `domains/`（base + nonlinear + synthetic） |
| v1.9.0 | 搜索与 Reflection 对照 | `search/`, `evaluation_protocol.py`, `evaluation_statistics.py`, `benchmarks/nonlinear-search-v1/` |
| v2.0.0 | Runtime 可靠性与最终投递 | `control_plane.py`, `sse_replay.py`, `stress.py`, 层级 Trace, Strategy Comparison |
| v2.1.0 | 先验注入 + Benchmark 成熟化 | `priors.py`, `configs/priors/`, 10-case benchmark, `--provider deepseek` |
| v3.0.0 | Web 可优化方向白名单与多 Domain 展示 | `web_ui.py`, `domains/` |
| v3.1.0 | PIM / Register 等领域插件与数据选择 | `domains/pim_cancellation.py`, `domains/register_config.py` |
| v3.2.0 | 50-case 参数化回归、真实 LLM 搜索与多 seed 报告 | `benchmark_cases.py`, `search/llm_search.py` |
| v3.3.0 | synthetic-large/hard、真实 API 搜索和 LLM client watchdog | `compare_runner.py`, `llm.py` |

## 6. 核心代码入口

```text
src/nonlinear_agent/tools.py              ToolCall / ToolResult / ToolRegistry / ToolSpec
src/nonlinear_agent/runtime.py            HarnessRequest / ExperimentHarnessRuntime
src/nonlinear_agent/experiment_tools.py   generate_config / run_training / verify_artifacts / write_report
src/nonlinear_agent/planner.py            LLM plan JSON parser and prompt
src/nonlinear_agent/planner_validation.py Planner output guard and parameter budget
src/nonlinear_agent/loop.py               Planner -> Guard -> Runtime -> History -> Reflection
src/nonlinear_agent/context_memory.py     history-summary + recent window
src/nonlinear_agent/reflection.py         deterministic reflection policy
src/nonlinear_agent/benchmark.py          benchmark metrics and artifacts
src/nonlinear_agent/diagnostics.py        aggregate run/benchmark artifacts
src/nonlinear_agent/server.py             FastAPI + SSE endpoints
src/nonlinear_agent/web_ui.py             browser UI
src/nonlinear_agent/mcp_server.py         MCP-compatible bridge
src/nonlinear_agent/domains/              DomainPlugin 协议 + 两个插件
src/nonlinear_agent/search/               SearchStrategy + Random/Optuna/LLM 策略
src/nonlinear_agent/evaluation_protocol.py  统一实验协议
src/nonlinear_agent/evaluation_statistics.py bootstrap CI / paired delta
src/nonlinear_agent/compare_runner.py     4 策略真实对照执行器
src/nonlinear_agent/control_plane.py      SQLite 控制面（去重/lease/事件）
src/nonlinear_agent/sse_replay.py         SSE Last-Event-ID 重放
src/nonlinear_agent/stress.py             并发压测
```

## 7. Web / CLI 功能

CLI：

```powershell
python agent.py run --provider fake
python agent.py run --provider deepseek
python agent.py benchmark
python agent.py diagnostics
python agent.py dashboard
python agent.py serve --host 127.0.0.1 --port 8000
```

Web UI：

```text
GET  /                          首页
GET  /health                    健康检查
GET  /diagnostics/{name}        诊断文件
POST /runs/{session_id}/events  Fixed Workflow SSE
POST /agent/{session_id}/events LLM Planner Loop SSE
POST /benchmark/events          Benchmark SSE
```

## 8. DeepSeek self-correction case

这个 case 用来回答：

- Agent loop 和固定 workflow 有什么区别？
- 工具调用失败后怎么恢复？
- LLM planner 怎么利用历史结果修正下一轮计划？
- 怎么证明项目不是空壳 demo？

一句话：

> 我让 DeepSeek 在 4000 参数约束下自动设计非线性拟合实验。Harness 把每个候选实验转成受控工具链执行，记录 schema rejection、runtime failure、NMSE、PSD 和 reflection。真实运行中 DeepSeek 曾输出错误参数类型，系统把错误写入 history，下一轮 planner 根据错误修正参数并继续探索，最终找到 202 参数、NMSE -36.0275 dB 的轻量候选。

目标：

```text
在 4000 参数以内，寻找低 NMSE 的非线性系统拟合模型，并输出 PSD 结果图。
```

真实 DeepSeek run 的强化目标：

```text
Target NMSE <= -41 dB under 4000 trainable parameters.
最多 30 个实验，最长 3 小时，神经模型 epoch <= 50。
```

系统限制：

- LLM 不能直接执行 shell，只能返回 JSON plan。
- 执行前经过 schema guard、参数预算估算、类型/值域检查、max experiments、timeout。
- rejected/failed/succeeded 都写入 history。
- reflection 现在也进入下一轮 planner prompt。

真实失败：

- DeepSeek 探索 `spline_mlp` 时输出过非法 `spline_range`。
- Guard 或 runtime 将错误记录为 rejected/failed。
- 下一轮 planner 根据 history 修正参数。

代表结果：

| Experiment | Model | Feature mode | Memory depth | MP order | Params | NMSE |
|---|---|---|---:|---:|---:|---:|
| exp016 | complex_lstsq | complex_mp | 220 | 9 | 3980 | -37.4875 dB |
| exp_019 | complex_lstsq | complex_mp | 24 | 4 | 202 | -36.0275 dB |

结果图：

```text
docs/assets/psd-exp016-best-41db-run.png
docs/assets/psd-exp019-self-correction-run.png
```

为什么没到 -41 dB 也有价值：

- DeepSeek 能根据目标设计多组候选。
- Harness 能把候选转为可执行工具链。
- Schema guard 能拦截不可执行计划。
- Runtime 能记录 metric、error、trace、session。
- Reflection 能生成下一轮 recovery action。
- Diagnostics 能聚合多轮结果和失败分布。
- 结果说明当前 feature family 在 4000 参数约束下接近平台期，继续单纯加 memory/order 收益有限。

## 9. Benchmark 维护说明

Benchmark 指标：

- `target_hit_rate` = 达标 case 数 / 总 case 数。
- `rejected_rate` = rejected 记录数 / 全部实验记录。
- `runtime_failure_rate` = failed 记录数 / 全部实验记录。
- `average_experiments_used` = 消耗实验数 / case 数。
- `best_nmse_db` = 全部 case 最优 NMSE，越小越好。

当前 canonical benchmark 覆盖 10 类行为模板：

- target hit under budget
- invalid planner output rejection
- runtime failure handling
- reflection-based recovery
- experiment budget stop
- noisy JSON tolerance
- parameter budget edge
- unknown tool rejection
- long-history compression
- multi-round correction sequence

50-case 模式只是把这 10 个模板修改阈值和轮数后重复，不是 50 个独立 Agent 任务。它可以作为参数敏感性回归，不应作为任务多样性证据。当前评测的详细问题和重构方向见 `docs/diagnostics/agent-engineering-review-2026-08-10.md`。

### v1.9 搜索对照实验

统一 Trial Protocol（`benchmarks/protocol/nonlinear-search-v1.json`）下的 4 策略 × 5 seeds × 10 有效训练 trial 真实对照已落地，见：

```text
benchmarks/nonlinear-search-v1/trials.jsonl
benchmarks/nonlinear-search-v1/summary.json / summary.csv
benchmarks/nonlinear-search-v1/best-so-far.png / reflection-ablation.png
docs/experiments/nonlinear-search-ablation-v1.md
```

关键结论（诚实口径）：

- Optuna TPE best NMSE 均值最高（-37.07 dB，std 0.27 dB）。
- `llm_program_reflection` 相对 `llm_direct` paired delta = +2.34 dB，**不显著**，未观察到稳定优势。
- 每条 trial 记录真实 `config_hash` / `dataset_hash` / `git_commit`；rejected 单独统计、不占用有效预算。

LLM 策略当前为离线邻域采样模拟（token/cost = 0），真实 LLM 证据仍以 DeepSeek case study（exp016 / exp_019）为准。

### v2.0 Runtime 可靠性

- `RuntimeControlPlane`：SQLite 请求去重、原子 claim、lease 过期重领、max_attempts、单调事件序列（WAL + busy timeout）。
- SSE：事件 ID、15s heartbeat、`/cancel/{session_id}`、Last-Event-ID 断线重放。
- 层级 Trace：`trace_id/span_id/parent_span_id/attempt/model/config_hash/token_count/cost_usd`。
- 压测验收线（`benchmarks/runtime-v2/stress.json`，PASS）：重复执行率 0、事件丢失率 0、终态一致率 1.0、注入 10% 故障后恢复率 1.0。

## 10. 当前状态修复记录

### 根目录实验产物

历史原因：`output_dir: exp_001` 这类裸路径会让 `train.py` 在项目根目录写产物。

当前修复：

- `artifact_paths.normalize_experiment_output_dir()` 统一路径策略。
- planner guard 与 config generation 都会把裸实验目录改成 `reports/<name>`。
- 已有根目录实验产物已移动到 `reports/relocated-root-artifacts/`。
- `.gitignore` 防止未来误产物污染 git status。

### Reflection 决策闭环

旧问题：reflection 只落盘，不进入下一轮 history。

当前修复：

- reflection 以 `run_status: reflection` 写入 history。
- 下一轮 planner prompt 能读到结构化 `facts` 和 `failure_causes`。
- benchmark/leaderboard 过滤 reflection/summary，不污染实验统计。

当前设计：确定性 reflection 只做事实提取，不输出恢复策略；下一轮 LLM 根据干净事实自行推理。Web 控制台会在新 plan 前展示上一轮错误原因、reflection facts 和新计划。

已知评测问题：现有 `self_correction_count` 只统计相邻的 failed/rejected -> succeeded，不能证明发生了新的 LLM 决策。方案 1 会用 planner/action/event 因果 ID 重写该指标。

## 11. 文档维护规则

保留并维护：

- `README.md`
- `docs/onboarding/newcomer-guide.md`
- `docs/handoff/llm-continuation-plan.md`
- `docs/resume/experiment-agent-harness-resume.md`
- `docs/learning/experiment-agent-harness-v*.md`
- `docs/diagnostics/agent-runtime-dashboard.md`
- `docs/diagnostics/agent-runtime-dashboard.html`
- `docs/experiments/*.md`
- `docs/assets/*`

不要再新增零散“开心型”文档。新内容优先合并到：

- 上手/当前状态：`docs/onboarding/newcomer-guide.md`
- 交接/维护/版本计划：`docs/handoff/llm-continuation-plan.md`
- 简历/面试表达：`docs/resume/experiment-agent-harness-resume.md`
- 版本学习：`docs/learning/experiment-agent-harness-v*.md`

## 12. 后续边界

本项目 v1.7.0 → v2.0.0 计划已完成（仓库收口、DomainPlugin、搜索对照、SQLite 控制面、SSE 重放、压测）。后续修改以修 bug、更新面试 Q&A、更新 case study、稳定 UI 和测试为主。

以下内容交给 Storm 或其他项目：

- RAG 全流程
- BM25 / vector hybrid search / rerank
- Ragas 评测
- GraphRAG
- 长期语义记忆
- 多 Agent 协作和并发

## 13. 验证命令

```powershell
python -m unittest discover tests
python examples\nonlinear_fit\run_benchmark.py --output-dir benchmarks\fake-check
python agent.py dashboard
python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json --dry-run
python agent.py stress-runtime --concurrency 2 --requests 10 --failure-rate 0.1 --output-dir benchmarks/runtime-smoke
```

v1.6.2 定版验证记录：

- `python -m unittest discover tests`：95 tests OK。
- Benchmark 当前为 5 case：target hit、非法计划拒绝、runtime failure、reflection recovery、budget stop。
- Web UI 和 diagnostics dashboard 已统一为深色主题，并在页面说明 benchmark 指标口径。

v2.0.0 验证记录：

- `python -m unittest discover tests`：208 tests OK（含 DomainPlugin、搜索策略、评估统计、控制面、SSE 重放、并发压测）。
- `benchmarks/nonlinear-search-v1/`：200 个有效训练 trial（+120 rejected），hash 完整，PASS。
- `benchmarks/runtime-v2/stress.json`：并发 8 × 100 请求，重复执行率 0 / 事件丢失率 0 / 终态一致率 1.0 / 恢复率 1.0，PASS。

v2.1.0 验证记录：

- `python -m unittest discover tests`：227 tests OK。
- 20000 参数预算 + 历史先验注入：`llm_program_reflection` paired delta **-4.28 dB（显著）**，hit 78% vs 28%（`benchmarks/nonlinear-search-v1-v20000/`，报告 `docs/experiments/nonlinear-search-ablation-v2.md`）。
- Benchmark 10 case：fake 模式 hit 7/10；DeepSeek 模式 hit 5/10，但 Guard 拦截率 80–98%（模型 schema 遵从性不稳定，已知边界）。

v3.3.0 当前审查基线：

- `pyproject.toml` 当前版本 `3.3.0`，`main` 与 `origin/main` 指向 `f751f78`。
- 排除真实 API 长链路 `tests/test_real_llm_search.py` 后：263 tests OK。
- 首次 `python -m unittest discover tests` 在外层 120 秒限制下超时；源码核验确认 `test_real_llm_search.py` 使用 FakeLLM/mock，测试目录没有未 mock 的真实 API 调用。排除该模块后 263 tests 在 68.9 秒内通过。后续按耗时拆分 fast/full profile，不把超时错误归因于网络。
- 真实 DeepSeek v26 是 10 case、target hit 9/10，不是 50 case。
- `llm_program_reflection` 当前同时引入 reflection facts 与 historical priors，不能把 paired delta 全部归因于 reflection。

## 14. 方案 1：Agent 证据增强实施计划

> 当前只验收 `nonlinear-modeling` Domain。其他 Domain 保持可运行，但不进入本阶段 Benchmark，避免用横向扩域代替纵向做深。

**Goal:** 把当前“LLM 生成实验配置 + 固定四步工具链”升级为可逐步选择工具、可追踪因果修正、可用独立任务评测的单 Domain Agent Harness。

**Architecture:** 保留现有 fixed workflow 作为可靠基线，新增 action-level agent mode。Planner 每次产生一个 `AgentAction`（tool call 或 stop），Action Guard 使用 ToolSpec 校验工具和参数，Runtime 执行后把 observation、event IDs 和 planner call ID 写回上下文。Benchmark 分离 Contract、Agent Task、Search Quality、Runtime Reliability，禁止再用一个 hit rate 混合所有能力。

**Tech Stack:** Python 3.9+、现有 asyncio/FastAPI/SQLite/unittest、ToolRegistry/ToolSpec、DeepSeek OpenAI-compatible client。

### 2026-08-10 实施进度（v3.4.0）

| 工作包 | 状态 | 已有证据 | 尚未完成 |
| --- | --- | --- | --- |
| Task 1 因果纠错指标 | 已完成 | 新旧指标并存；测试覆盖同 batch 假修正与跨 planner 因果修正 | 真实 DeepSeek 数据尚未重跑 |
| Task 2 AgentAction/Guard | 已完成 | `actions.py`、共享 ToolSpec、contract tests | P2 的 prompt injection/超大输出防护未做 |
| Task 3 action loop | 核心完成 | CLI action mode、逐 action observation、failure event 因果约束、action budget | SSE/WebUI action stream、time/token budget 尚未接入 |
| Task 4 独立任务 | 离线链路完成 | 18 个唯一任务、生产 ToolSpec fault fixture、CLI/SSE/WebUI runner、逐 action provenance、scripted pass@1=1.0 | 6 个 DeepSeek representative runs 尚未完成；scripted 分数不得包装成模型能力 |
| Task 5 正交消融 | 已完成 | direct/history/facts/priors 四组；三段 paired increment | 真实多 seed 结果尚未生成 |
| Task 6 测试入口 | 已完成 | `python scripts/run_tests.py fast/full`；fast 48 tests、full 298 tests 通过 | 无 |
| Task 7 episodic memory | 未开始 | 现有 `HistoryCompressor` 仅属短期上下文 | SQLite namespace/provenance/污染测试全部待做 |
| Task 8 文档收口 | 进行中 | README 与简历文档已区分旧 50 变体、真实 10-case 和 action loop | PDF 本体、真实 benchmark 数字需在在线运行后更新 |

注意：当前可以宣称“action-level loop 与独立任务评测框架已实现”，不能宣称“18 个任务已由 DeepSeek 达到某个 pass rate”。

### v3.5.0 增量

- 加固四个生产 ToolSpec：补齐 properties、类型和 `additionalProperties: false`，Action Guard 与 MCP 继续共享 schema。
- 新增 `agent-benchmark` CLI，正式结果保存到 `benchmarks/agent-tasks-v1/`。
- 新增 `/agent-benchmark/events` SSE 和 Web Benchmark 按钮；每个 case 展示 planner call、action、event、caused-by 与 observation。
- WebUI 在真实 390px 设备模拟下 `innerWidth = scrollWidth = 390`，无页面级横向溢出。

### Task 1：修正 Benchmark 指标语义

**Files:**

- Modify: `src/nonlinear_agent/benchmark.py`
- Modify: `src/nonlinear_agent/loop.py`
- Modify: `tests/test_benchmark.py`
- Modify: `tests/test_llm_planner.py`

- [ ] 先写失败测试：同一 plan batch 内的 failed -> succeeded 不算 self-correction。
- [ ] 先写失败测试：只有新 `planner_call_id` 消费对应 `failure_event_id` 且动作改变，才算 causal correction。
- [ ] 给 history record 增加 `round`、`planner_call_id`、`caused_by_event_ids`。
- [ ] 新增 `causal_correction_count`、`causal_correction_success_rate`；旧字段保留一版兼容但标记 legacy。
- [ ] 运行 `python -m unittest tests.test_benchmark tests.test_llm_planner -v`。

验收：构造 1 个同 batch 假修正和 1 个跨 planner 真修正，前者计 0、后者计 1。

### Task 2：建立逐步 AgentAction 与 Action Guard

**Files:**

- Create: `src/nonlinear_agent/actions.py`
- Modify: `src/nonlinear_agent/planner.py`
- Modify: `src/nonlinear_agent/tools.py`
- Create: `tests/test_agent_actions.py`

- [ ] 先写失败测试：Planner 能解析 `{"type":"tool_call","tool":"generate_config","arguments":{...}}`。
- [ ] 先写失败测试：未知工具、缺少参数、多余参数和嵌套危险值被 Action Guard 拒绝。
- [ ] 定义 `AgentAction`：`tool_call`、`stop` 两类；包含 `action_id`、`reason`、`tool_name`、`arguments`、`caused_by_event_ids`。
- [ ] ToolSpec 成为 Action Guard 的唯一 schema 来源。
- [ ] 保留现有 ExperimentPlan API，不破坏 fixed workflow。
- [ ] 运行 `python -m unittest tests.test_agent_actions tests.test_experiment_tools tests.test_mcp_server -v`。

验收：同一 ToolSpec 同时服务本地 action 校验与 MCP tools/list，工具名和 required arguments 不漂移。

### Task 3：实现 action-level Agent Loop

**Files:**

- Create: `src/nonlinear_agent/action_loop.py`
- Modify: `src/nonlinear_agent/server.py`
- Modify: `src/nonlinear_agent/cli.py`
- Create: `tests/test_action_loop.py`
- Modify: `tests/test_server_streaming.py`

- [ ] 先写失败测试：模型可按 observation 依次选择 generate_config、run_training、verify_artifacts、write_report、stop。
- [ ] 先写失败测试：工具失败后下一次 action 必须引用 failure event ID。
- [ ] 先写失败测试：达到 action/experiment/time/token budget 后强制终止。
- [ ] 实现 `ActionPlannerLoop`，每轮只执行一个 action，然后立即把 observation 回给 Planner。
- [ ] 增加 CLI `run --mode action` 与 SSE action events；默认仍为 fixed mode，便于对照。
- [ ] 运行 `python -m unittest tests.test_action_loop tests.test_server_streaming tests.test_cli -v`。

验收：FakeLLM 可完成一条五步链路；插入一次失败后会产生新的 planner call，并用 event ID 建立因果边。

### Task 4：重建 18 个独立单 Domain Agent 任务

**Files:**

- Create: `src/nonlinear_agent/agent_benchmark_cases.py`
- Create: `src/nonlinear_agent/agent_benchmark.py`
- Create: `tests/test_agent_benchmark_cases.py`
- Modify: `src/nonlinear_agent/cli.py`
- Modify: `src/nonlinear_agent/web_ui.py`

- [ ] 先写失败测试：case ID、initial state、fault injection、expected terminal state 全部唯一。
- [ ] 先写失败测试：不得通过正则删除 `-vN` 后复用同一模板生成所谓独立 case。
- [ ] 实现诊断报告第 5 节列出的至少 18 个任务。
- [ ] 每个 case 使用确定性 fake 环境做离线回归；其中 6 个代表 case 支持 DeepSeek online run。
- [ ] 输出 Contract 与 Agent Task 两份 summary，不和 NMSE Search Quality 混合。
- [ ] Web UI 展示每个指标的来源 case、planner call、action 和 observation。

验收：18 个独立任务、无模板阈值复制；每个 task 有明确 pass/fail predicate；支持 pass@1/pass@3。

### Task 5：正交化 Reflection/History/Prior 消融

**Files:**

- Modify: `src/nonlinear_agent/search/llm_search.py`
- Modify: `src/nonlinear_agent/compare_runner.py`
- Modify: `src/nonlinear_agent/evaluation_protocol.py`
- Create: `tests/test_reflection_ablation.py`

- [ ] 先写失败测试：四组策略只在指定 context source 上不同。
- [ ] 策略组固定为 `direct`、`history_only`、`history_facts`、`history_facts_priors`。
- [ ] 相同 seed 下候选空间、预算、模型参数和 retry 配置一致。
- [ ] 报告 history、facts、priors 各自增量，不再把 priors 收益命名为 reflection 收益。

验收：测试可检查四组最终 prompt section；paired report 分别输出 facts delta 和 priors delta。

### Task 6：拆分 fast/full 测试入口

**Files:**

- Create: `scripts/run_tests.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Create: `tests/test_test_profiles.py`

- [ ] 先统计各测试模块耗时，fast 集只按耗时选择，不把 mocked real-LLM tests 误判成在线测试。
- [ ] 提供 `python scripts/run_tests.py fast` 与 `python scripts/run_tests.py full`。
- [ ] 真正 DeepSeek eval 保持在 benchmark/compare 命令中，必须显式选择 provider。

验收：fast profile 适合提交前回归，full profile 覆盖全部单元测试；二者均不访问网络。

### Task 7：P1 结构化 episodic memory

**Files:**

- Create: `src/nonlinear_agent/episodic_memory.py`
- Modify: `src/nonlinear_agent/action_loop.py`
- Create: `tests/test_episodic_memory.py`

- [ ] 先写失败测试：成功和失败 episode 可按约束、模型族和指标检索。
- [ ] 每条 memory 保存 run/action/config/dataset hash、事实、指标、时间和 provenance。
- [ ] namespace 固定为 domain + dataset hash，禁止不同数据集泄漏。
- [ ] Planner 注入 top-k 结构化 episode，不引入向量数据库。
- [ ] 增加 memory off/on 与污染记忆消融。

验收：正确 namespace recall@3 = 1.0，跨 dataset leakage = 0；stale/冲突 item 不覆盖更新证据。

### Task 8：文档、简历与最终证据

**Files:**

- Modify: `README.md`
- Modify: `docs/resume/experiment-agent-harness-resume.md`
- Modify: `docs/onboarding/newcomer-guide.md`
- Modify: `docs/diagnostics/agent-engineering-review-2026-08-10.md`
- Modify: `docs/handoff/llm-continuation-plan.md`

- [ ] 把“50-case 0.9”改为“真实 DeepSeek 10-case 9/10”。
- [ ] 删除或补证 `24656 -> 19490`。
- [ ] 区分 simulated search、real DeepSeek、fixed workflow 和 action loop。
- [ ] 只引用 repository 内可复算 JSON/CSV。
- [ ] 更新面试讲法：为什么 fixed baseline 和 action mode 同时保留。

验收：README、简历文档、PDF 建议和原始结果之间无数字冲突。

### 实施顺序和阶段门

```text
P0-A: Task 1 + Task 2
  -> 指标可信，Action schema 可用
P0-B: Task 3 + Task 4
  -> 真正逐步 Agent + 独立任务 Eval
P0-C: Task 5 + Task 6
  -> 因果消融 + 快速/完整测试入口
P1: Task 7
  -> 跨 run 结构化经验记忆
Closeout: Task 8
```

每个阶段完成后必须运行对应测试和完整 offline suite。禁止在 P0 指标语义未修正前继续宣传 self-correction 数字。

### 方案 1 总验收

- [ ] 只用 `nonlinear-modeling` Domain 完成评测。
- [ ] 至少 18 个独立 Agent 行为任务，非模板阈值复制。
- [ ] action-level loop 支持 tool_call/stop、逐步 observation 与预算终止。
- [ ] causal correction 可追溯 failure event、planner call 和 changed action。
- [ ] direct/history/facts/priors 四组正交消融。
- [ ] Contract、Agent Task、Search Quality、Runtime Reliability 分开报告。
- [ ] fast/full 单元测试均无网络；真实 LLM eval 独立显式运行。
- [ ] structured episodic memory 跨 dataset 泄漏为 0。
- [ ] 简历只保留有原始证据的数字。
- [ ] `git diff --check` 通过；完整 offline suite 通过。
