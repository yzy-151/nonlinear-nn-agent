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
| v3.6.0 | Knowledge/Memory Foundation | `memory/`, `knowledge/`, `action_loop.py`, `server.py`, `web_ui.py` |
| v3.6.1 | 混合检索（BM25+向量+rerank）与真实难度评测 | `knowledge/embedder.py`, `knowledge/reranker.py`, `scripts/eval_knowledge_retrieval.py` |
| v3.7.0 (WIP) | Supervisor/ModelRouter/PlanGate 核心 | `model_router.py`, `plan_gate.py`, `supervisor.py` |
| v3.8.0 | Coding/Execution Agent + 3 模型族 E2E | `coding_agent.py`, `execution_agent.py`, `tools.py` |
| v3.9.0 (WIP) | Writing/Reporting：ReportSpec + Fidelity + PDF | `reporting/` |

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
| Task 7 episodic memory | 已完成（v3.6.0） | `memory/ports.py`、`memory/langgraph_store.py`、`knowledge/`、action_loop memory off/on、Web memory inspector | 真实 Postgres 集成与在线 KB 评测待 v3.7+ |
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

### Task 7：P1 成熟 Memory + Knowledge Base

**Files:**

- Create: `src/nonlinear_agent/memory/ports.py`
- Create: `src/nonlinear_agent/memory/langgraph_store.py`
- Create: `src/nonlinear_agent/knowledge/ingest.py`
- Create: `src/nonlinear_agent/knowledge/retriever.py`
- Modify: `src/nonlinear_agent/action_loop.py`
- Create: `tests/test_memory_store.py`
- Create: `tests/test_knowledge_retrieval.py`

- [ ] 先定义 `MemoryBackend`，业务代码不得直接依赖某个厂商 SDK。
- [ ] 使用 LangGraph Store：单测 `InMemoryStore`，生产配置 `PostgresStore`；namespace 固定为 domain + dataset hash + memory kind。
- [ ] memory 分 semantic/episodic/procedural 三类；working memory 由 graph state/checkpointer 管理。
- [ ] 每条 memory 保存 run/action/config/dataset hash、原子事实、指标、时间、created_by、model、prompt hash、evidence refs、confidence 和 supersedes。
- [ ] 建立知识库 ingestion：只收录白名单 docs/configs/benchmark/paper，chunk 带 source path、content hash、version、created_at。
- [ ] Planner 只接收 top-k 检索结果和 citation，不注入整库；memory 写入前做事实校验、去重和冲突处理。
- [ ] 增加 memory off/on、错误记忆注入、stale memory、跨 dataset 污染和 KB citation 消融。

验收：标注查询集上 Recall@3 >= 0.90、citation precision >= 0.95、跨 dataset leakage = 0；stale/冲突 item 不覆盖新证据；删除某 run 后其派生 memory 可追踪清理。

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

## 15. 方案 2：Knowledge + Memory 驱动的 Multi-Agent 实验团队

> 本节是 v3.5.0 之后的唯一后续实施计划。DeepSeek 接手时直接维护本节状态，不再创建新的 plan/handoff 文档。仍只验收 `nonlinear-modeling` Domain。

### 15.1 结论与边界

这个方向值得做，但目标不是“Agent 越多越高级”，而是证明四类职责确实需要不同上下文、工具权限和模型能力。官方 LangChain 文档也明确指出，简单任务往往单 Agent 已足够，多 Agent 会增加模型调用、延迟和 token；因此必须保留当前 single-agent action loop 作为 baseline，并用消融证明 multi-agent 的收益。

采用 **Supervisor + 4 个隔离 Worker + 确定性 Quality Gates**：

```text
User Goal
  -> Supervisor / Orchestrator
      -> Knowledge + Memory Retrieval
      -> Idea & Plan Agent
      -> Plan Gate
      -> Coding Agent (isolated worktree)
      -> Code Gate
      -> Execution Agent (ToolRegistry only)
      -> Result Gate / factual reflection / memory write
      -> Writing Agent -> ReportSpec
      -> Deterministic PDF Renderer + Fidelity Gate
```

Supervisor 负责状态、路由、预算、重试、取消和终态，不负责替 Worker 写长文本。Worker 默认无共享聊天记录，只接收最小结构化输入并返回结构化产物。跨 Agent 只传 artifact reference、事实摘要和 ID，不传内部推理全文。

框架选择：

- 用 LangGraph `StateGraph`、checkpointer 与 Store 表达节点、恢复和长短期 memory；现有 `ExperimentHarnessRuntime`、`ToolRegistry`、Trace、Hook、ControlPlane 保持执行内核，不推倒重写。
- `MemoryBackend` 必须可插拔。第一后端为 LangGraph Store，测试用 `InMemoryStore`，生产 profile 用 `PostgresStore`。Mem0 可作为第二适配器实验，不在第一阶段同时引入图数据库。
- Knowledge Base 与 Memory 分离。KB 是经白名单导入的外部知识；Memory 是运行产生的项目经验。两者均必须返回 citation/provenance，未经验证的 LLM 推测不得写入 semantic memory。
- 参考官方资料：[LangGraph Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)、[LangChain Long-term Memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)、[LangChain Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents)、[Mem0 Graph Memory](https://docs.mem0.ai/open-source/features/graph-memory)。

### 15.2 Agent 职责与最小权限

#### A. Idea & Plan Agent

输入：目标、硬约束、KB top-k、同 dataset episodic memory top-k、当前代码能力清单、历史失败事实。

输出 `IdeaPlanSpec`：

- `hypotheses[]`：假设、物理/算法依据、citation；
- `candidate_experiments[]`：模型族不限于当前枚举，可提出新模型，但必须给参数估算和实现成本；
- `experiment_dag`：依赖、并行组、预算、early-stop；
- `expected_information_gain`、风险、回退方案；
- `required_code_changes` 与 `no_code_change_candidates`。

权限：只读 KB/memory/code inventory；不能改代码、不能训练、不能写入长期 memory。Supervisor/Plan Gate 负责去重、预算和 schema 校验。

#### B. Coding Agent

输入：已批准 `IdeaPlanSpec`、目标文件白名单、测试命令、代码上下文和 coding memory。

输出 `CodeChangeSpec`：branch/worktree、patch、changed files、tests、model/config registration、风险与回滚点。

权限：只在临时 Git worktree 编辑；不能读取 API key；不能直接写 main；不能执行任意训练。允许配置独立 coding model，但模型由 `ModelRouter` 配置，不由 Agent 临时选择。所有改动必须先有失败测试，再通过 Code Gate 才可进入执行阶段。

#### C. Execution Agent

输入：已通过 Code Gate 的 commit SHA、实验 DAG、资源预算和 artifact contract。

输出 `ExecutionResultSpec`：每个 trial 的 tool/action/event IDs、配置 hash、环境、指标、产物、失败分类、资源消耗和终态。

权限：只能调用注册工具；默认不能编辑源码；禁止自由 shell。负责排队、并发、timeout、cancel、resume、OOM/NaN/缺失产物处理。训练失败后只提取事实并回交 Supervisor，是否重新规划由 Plan Agent 决定。

#### D. Writing Agent

输入：只读的 `IdeaPlanSpec`、`CodeChangeSpec`、`ExecutionResultSpec`、metrics JSON、PSD/表格和 trace references。

输出 `ReportSpec`，不直接操作 PDF 二进制。确定性 renderer 根据模板生成 Markdown + PDF。

PDF 至少包含：目标与约束、知识/记忆 citation、实验 DAG、代码变化、环境、基线与最优配置、参数量、NMSE、PSD、消融、失败案例、Agent trace、成本/时延、限制和可复现命令。Fidelity Gate 必须逐数字核对原始 JSON；没有证据的字段显示 unknown，不允许补写。

### 15.3 ModelRouter

新增角色级配置，不把模型名散落在代码：

```yaml
roles:
  supervisor: {provider: deepseek, model: configurable, temperature: 0.0}
  idea_planner: {provider: deepseek, model: configurable, temperature: 0.3}
  coding: {provider: openai_compatible, model: configurable, temperature: 0.0}
  execution: {provider: none}
  writing: {provider: openai_compatible, model: configurable, temperature: 0.1}
```

要求：

- 统一 `ModelClient` 接口，支持 DeepSeek/OpenAI-compatible/fake；coding/writing 可使用不同模型。
- provider、model、base URL、timeout、token/cost budget 来自配置和环境变量；secret 不进 trace、prompt、Git。
- execution 默认无 LLM；只有需要解释未知错误时才请求 Supervisor 批准调用。
- 每次调用记录 role/model/provider/latency/token/cost/prompt-template-version，不记录密钥和完整隐私内容。
- fallback 只在明确 error class 下触发，最多一次；禁止模型之间无限互相重试。

### 15.4 共享状态与 Memory Schema

`MultiAgentRunState` 至少包含：

```text
run_id, goal, constraints, dataset_hash, code_commit
active_stage, approved_plan_id, action_budget, time_budget, cost_budget
idea_plan_ref, code_change_ref, execution_result_ref, report_ref
unresolved_failure_event_ids, retry_counts, terminal_status
```

Memory item 至少包含：

```text
memory_id, kind(semantic|episodic|procedural)
namespace(domain, dataset_hash, model_family)
fact, evidence_refs, run_id, action_id, config_hash
metrics, created_by_role, model, prompt_hash, created_at
confidence, valid_from, supersedes, invalidated_at
```

写入规则：

1. Execution/Guard 产生的可验证事实可进入 episodic memory。
2. Writing Agent 无权写 memory。
3. LLM 总结只有在 evidence refs 可解析时才能写；否则只留在 run artifact。
4. 新证据冲突时不覆盖旧记录，使用 `supersedes`/invalidate 保留审计链。
5. retrieval 按 namespace、硬约束过滤，再做 semantic ranking；返回内容必须带 source 和 score。

### 15.5 可执行版本计划

#### v3.6.0：Knowledge/Memory Foundation

实现：`MemoryBackend`、LangGraph Store adapter、KB ingestion/retrieval、typed memory schema、provenance、namespace isolation、Web memory inspector。

验收：

- 30 条人工标注 query：Recall@3 >= 0.90，citation precision >= 0.95；
- 跨 dataset leakage = 0，错误/stale memory 不进入 planner top-3；
- memory off/on 结果可复算；删除 run 可定位其全部派生 memory；
- 无 Postgres 时 offline tests 可用 InMemoryStore，真实 profile 明确报依赖缺失而非静默降级；
- full offline suite 通过，建立 `version/v3.6.0`。

**2026-08-10 实施完成（v3.6.0 验收）**：

- `MemoryBackend` 端口（`memory/ports.py`）+ `LangGraphMemoryBackend`（InMemoryStore，`memory/langgraph_store.py`）+ `PostgresMemoryBackend`（psycopg 缺失时抛明确 ImportError，不静默降级）；
- typed memory schema：semantic/episodic/procedural、namespace = (domain, dataset_hash, model_family)、evidence refs、run/action/config hash、created_by_role、model、prompt hash、confidence、supersedes、invalidated_at；
- namespace isolation 与审计链：跨 dataset 检索互不可见；新证据不覆盖旧记录（supersedes 保留审计链）；`delete_run` 返回并清理该 run 全部派生 memory；
- KB ingestion（`knowledge/ingest.py`）：白名单 roots、chunk 带 source/content hash/version/created_at/citation；BM25 检索（`knowledge/retriever.py`）纯 Python 无外部 ML 依赖；
- 30 条标注查询：Recall@3 = 1.0、top-1 citation precision = 1.0、跨 dataset leakage = 0（合成关键词对齐集，仅证明词法匹配；真实难度评测见 v3.6.1）；
- `ActionPlannerLoop` 接入 memory off/on：on 时每次 action 写入一条带完整 provenance 的 episodic memory；
- Web memory inspector：`GET /memory` + WebUI Memory Tab（只读展示 namespace/kind/fact/evidence）；
- 验证：fast 77 tests、full 323 tests 全部通过；`version/v3.6.0` 分支已建立。

### v3.6.1：混合检索与真实难度评测（修正合成集虚高）

**测什么能力**：知识库检索（RAG 召回）——给定用户问题，能否在项目真实文档（README/handoff/learning/experiments/configs）里 top-3 命中能回答该问题的章节。

**测评方法**：30 条人工编写的**用户视角中文问句**（问题式、不照抄文档措辞），每条标注 1~4 个人工验证过的等价目标章节 + 1 条术语化扩展查询；跑 4 档配置（BM25 / +bge 向量 / +cross-encoder rerank / +query expansion），指标 recall@3 = top-3 命中任一可接受目标的比例。产物可复现：`python scripts/eval_knowledge_retrieval.py` → `benchmarks/knowledge-eval-v1/`。

**改进过程**（为什么最初 1.0 不可信 → 最终 0.93）：
1. 合成集 Recall@3=1.0 是**关键词对齐虚高**（查询与目标 chunk 逐词重叠），只证明词法匹配；
2. 真实中文查询暴露 BM25 失效（纯中文查询 token 为空 → recall 0.17），修复为**中文字符 tokenize**；
3. MiniLM 多语言模型检索弱 → 换 `BAAI/bge-small-zh-v1.5`（本地下载）+ query instruction + 512 长度；
4. RRF 融合会丢"两路都中游"的候选 → 改 **BM25∪语义 top-100 并集** 交给 rerank；
5. 800 字符大 chunk 语义混杂 → **按段落切 400 字符 chunk + 标题注入正文**；
6. 评测标注"唯一目标章节"把等价命中误判为 miss → 改**多等价目标**口径；
7. 最后加 **query expansion**（术语化扩展查询 + RRF 融合）补齐语义桥接。

**改进结果**（30 条真实查询）：

| 配置 | recall@3 |
| --- | ---: |
| BM25 基线 | 0.53 |
| hybrid（BM25+向量） | 0.53 |
| hybrid + rerank | 0.83 |
| hybrid + rerank + expansion | **0.93** |

**为什么效果好**：
- **召回与精排分离**：BM25+向量只负责"别漏掉"，cross-encoder 负责"精确排序"——rerank 把 0.53 提到 0.83；
- **中文查询词法失效被补上**：中文字符 token 让 BM25 不再空转，向量让语义桥接；
- **多路并集而非融合排序**：两路 top-100 并集保证候选池召回，最后精排；
- **query expansion 用术语补桥**：用户口语问句 ↔ 文档术语（如"防止并发重复执行"→`sqlite dedup atomic claim lease`）由扩展查询补齐，0.83 → 0.93；
- 剩余 2 条真失败（SQLite 控制面短章节、Writing Agent 规格）证明评测有区分度，不是放水。

**诚实边界**：30 条人工查询是小规模集，不是公开基准（BEIR/CMRC）；依赖人工等价目标标注；更硬的做法是 LLM-as-judge 相关性判定 + 100+ 查询 + 公开基准适配（列为后续项）。

**依赖**：`transformers`（已有）+ 本地模型 `BAAI/bge-small-zh-v1.5` / `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`；无模型时 retriever 优雅回退 BM25-only；`LocalTransformerEmbedder` 分批 encode 防 OOM；测试保持 mock 确定性 + 小 KB，完整评测在脚本中不进 fast/full。

#### v3.7.0：Supervisor + Idea/Plan Agent + ModelRouter

实现：LangGraph supervisor、`IdeaPlanSpec`、role model config、structured handoff、plan gate、token/time/cost budget、single-agent baseline adapter。

验收：

- 12 个 planning tasks schema-valid rate = 1.0，citation coverage >= 0.90；
- 计划不得重复历史 config hash；每个候选有参数估算、预算、停止条件和依据；
- 子 Agent 看不到不属于自己的 raw history/API key；所有模型调用可追踪 role/model/token/cost；
- budget/cancel/invalid JSON/model timeout 注入后均得到唯一终态；
- 建立 `version/v3.7.0`。

**2026-08-10 实施进度（v3.7.0 全部核心完成）**：

- `ModelRouter`（`model_router.py`）：role → provider/model/temperature 配置；每次调用记录 role/provider/model/latency/token/cost；secret 不进 usage；可重试错误 fallback 最多一次；cost/token 预算；
- `PlanGate`（`plan_gate.py`）：IdeaPlanSpec schema 校验（hypotheses/candidates 必填字段、budget、stop_condition）、历史 config hash 去重、citation coverage；**12 个 planning tasks schema-valid rate = 1.0**；
- `ExperimentSupervisor`（`supervisor.py`）：action/time/token/cost 预算、唯一终态（completed/stopped/budget_exceeded/error）、子 Agent 不接触 raw secrets；
- **LangGraph 接线**（`supervisor_graph.py`）：StateGraph 单节点 supervisor + PlanGate；invalid JSON / model timeout / budget / cancel 注入均得到唯一终态；
- **structured handoff**（`plan_handoff.py`）：gate 通过的计划投影为 ExecutionStep（config hash / budget / stop condition / citations），下游不再重推意图；
- **single-agent baseline adapter**（`single_agent_adapter.py`）：包装 ActionPlannerLoop 为统一 SupervisorResult，供 v4.0 消融对照；
- 测试：`test_model_router.py` / `test_plan_gate.py` / `test_supervisor.py` / `test_supervisor_graph.py` / plan handoff，full offline suite **351 tests OK**；
- 验收：12 planning tasks schema-valid rate = 1.0、citation coverage >= 0.90（PlanGate 断言）、历史 config hash 去重、子 Agent 密钥隔离、budget/cancel/invalid JSON/timeout 唯一终态——全部通过；
- 待 v4.0：single-agent vs multi-agent 消融、role-model 消融、真实 DeepSeek 规划任务评测。

#### v3.8.0：Coding Agent + Execution Agent

实现：隔离 worktree、patch/test gate、模型/激活/训练组件动态注册、执行队列、并发、resume、资源预算与失败回交。

验收：

- 10 个 coding fixtures 中 >= 9 个首次或一次修复后通过目标测试；未经允许写文件数 = 0；
- Coding Agent 不能改 main、不能读取 `.env.local`、不能跳过失败测试证据；
- Execution Agent 任意 shell 调用数 = 0，所有训练来自 ToolRegistry；
- timeout/cancel/OOM/NaN/missing artifact 各至少一个回归 case，终态一致率 = 1.0；
- 从新模型 idea 到注册、训练、验证的 E2E 至少成功 3 个不同模型族；
- 建立 `version/v3.8.0`。

**2026-08-10 实施完成（v3.8.0 验收）**：

- `CodingAgent`（`coding_agent.py`）：临时 git worktree 隔离（绝不改 main）、文件白名单（未授权写入计数 = 0）、`.env.local` 不可读/不可写、patch 后 test gate（目标测试通过才放行）；**10 个 coding fixtures 中 9 个通过 gate**（8 个等价实现 + 新增文件场景；错误实现被正确拒绝）；
- `ExecutionAgent`（`execution_agent.py`）：只允许注册工具（`ToolRegistry.get_tool` 新增公开接口）、任意 shell 调用审计 = 0、故障分类唯一终态（timeout / oom / nan / missing_artifact / error / cancelled）；
- 测试：`tests/test_coding_agent.py` / `test_execution_agent.py` / `test_e2e_model_family.py`；full offline suite **364 tests OK**（含真实轻量训练 E2E）；
- **E2E 通过**：3 个模型族（complex_lstsq / tiny_mlp / spline_mlp）从 IdeaPlanSpec → PlanGate → PlanHandoff → ExecutionAgent → 真实训练 → verify_artifacts 全链路成功（NMSE 有限 + 产物齐全，shell 审计 = 0）；
- 并发执行回归：3 个工具并发全部终态一致、审计 shell = 0；
- 验收全部通过：10 coding fixtures 9/10、未授权写文件 = 0、Coding Agent 不改 main / 不读 .env.local、Execution Agent 任意 shell 数 = 0、timeout/cancel/OOM/NaN/missing artifact 唯一终态、E2E 3 模型族成功；`version/v3.8.0` 已建立。

### v3.6/v3.8 验收缺口补齐（2026-08-11）

- **v3.6 缺口 1（citation precision）**：`scripts/eval_knowledge_retrieval.py` 新增 `hybrid_rerank_expansion_citation_precision_top1` 指标，真实 30 查询评测会输出 precision（产物 `benchmarks/knowledge-eval-v1/`）；
- **v3.6 缺口 2（stale 过滤接入 planner）**：新增 `memory/planner_context.py`（`PlannerContextBuilder`）——planner 只收到 top-k 知识 citation + top-k **有效** memory（invalidated 被过滤、namespace 隔离），测试覆盖 stale 不进 top-3 / 跨 dataset / citation 保留；
- **v3.8 缺口（resume / 资源预算 / 失败回交）**：新增 `execution_queue.py`（并发限制 + completed 记录 + resume 跳过）、`ExecutionAgent(max_executions=...)` 预算、`failure_handoff.py`（分类 → retryable / suggested_action，supervisor 可消费）；
- full offline suite **380 tests OK**。

### v3.9.0：Writing Agent + PDF Evidence（实施完成，验收）

- `reporting/report_spec.py`：`ReportSpec` + `ReportSpecBuilder`（从 source JSON 提取数字，不手工填）；
- `reporting/fidelity.py`：`FidelityChecker`——报告数字与 source JSON 逐项比对，mismatch = 0 才允许渲染（篡改数字会被检出）；
- `reporting/markdown_renderer.py`：Markdown 报告含 Baseline / Current / Best Candidates / Failure Cases / Cost / Trace / Reproduce 必需章节；
- `reporting/pdf_renderer.py`：reportlab 纯 Python PDF（数字写入 + PSD 图嵌入）；缺 PSD → `RenderError(errors=[...])` 结构化可重试；
- Web 下载：`/artifacts/reports/report-*.pdf` 经既有 artifacts 端点（reports/ 白名单 + resolve 防逃逸）直接可下载（FileResponse application/pdf）；
- 测试：7 个 reporting 测试 + PDF 下载 server 测试；PDF 文本经 pdfplumber 验证含关键数字；3 份不同 run 报告生成成功；
- 示例报告（`benchmarks/report-examples-v1/`）：exp016-lstsq（-37.49 dB）、exp_019-self-correction（-36.03 dB）、v26-llm-designed（-42.43 dB）三份 PDF 均 1 页、文本可读、数字与 source 一致；
- 验收：数字 fidelity mismatch=0 ✅、必需内容 ✅、结构化错误（缺 PSD → RenderError）✅、Web 下载（/artifacts/reports/*.pdf）✅、3 份报告生成+文本验证 ✅；PDF 视觉无裁切/重叠/乱码由示例文件可复核。

**任务级中文报告（2026-08-11 追加）**：

- 报告单位从"单个 run"修正为**任务级**（文档 15.2 要求）：`reporting/task_report_spec.py` 的 `TaskReportSpec` 覆盖 目标/约束/知识引用/计划（假设+候选+DAG）/代码变更/多次执行聚合/消融/失败案例/汇总成本/trace/复现/限制；
- **中文渲染**：`render_task_markdown`（Markdown 表格 + ✅/⭐ 标注）与 `render_task_pdf`（reportlab 注册 `C:\Windows\Fonts\simhei.ttf`，中文字体嵌入；表格用纯文字"达标/未达标/最优"标注，避免 SimHei 无 emoji 字形）；
- 结果用**表格 + PSD 图片**呈现；最优实验自动标注；达标行标"达标"；
- `TaskFidelityChecker`：每个 run 的 NMSE/参数量/基线/成本与 source 逐项核对，篡改可检出；
- 示例：`benchmarks/report-examples-v1/task-001/task-report-task-001.pdf`（中文，fitz 验证段落文本可提取、数字正确）；
- 测试：`tests/test_task_reporting.py` 6 个（builder/最优标注/fidelity/中文 Markdown/中文 PDF/缺图错误）；full offline suite **386 tests OK**。

**报告工具化（nnagent 自主作报告，2026-08-11）**：

- **`write_task_report` 已注册为 ToolRegistry 工具**（`reporting/tool.py` + `experiment_tools.py`）：Writing Agent 通过 ExecutionAgent 调用一个工具即可生成分析型中文 HTML+PDF 报告；
- 报告内容（HTML + Edge headless 转 PDF）：网络原理框图（matplotlib 绘制，含 hidden_units/memory_depth/activation）、PSD 功率谱对比（含图注）、改进效果柱状图（标注 dB 提升）、实验结果表（最优/达标标注）、**数据化总结**（达标率/最优/平均 NMSE/提升/成本）、**Agent 提供的分析文本**（改进过程/为什么有效/经验总结，经 `analysis` 参数注入）、消融/失败案例/复现/限制、fidelity 校验标记；
- 工具内部：`TaskFidelityChecker` 逐项核对数字 → 缺执行数据或 fidelity 不符 → 结构化错误返回给 Agent（error_policy=return_error）；
- 测试：`tests/test_reporting_tool.py` 4 个——Agent 调用工具生成报告（completed、artifacts 含 html+pdf）、HTML 必需章节与图片、PDF 中文可读、空数据失败；
- 说明：PSD 为示意谱（图注已注明），真实谱以实验产出的 psd.png 为准；架构图由工具自动绘制。

### v3.6 检索评测最终状态（2026-08-11）

真实 30 查询（用户视角中文，2242 chunks）：

| 配置 | recall@3 | citation precision@1 |
| --- | ---: | ---: |
| BM25 基线 | 0.53 | — |
| hybrid + rerank（池 150） | 0.90 | — |
| hybrid + rerank + expansion | **1.00** | **0.80** |

- Recall@3 = 1.0 达标（≥0.90）；**citation precision top-1 = 0.80，未达 0.95 验收线**；
- 提升路径已用尽：补全 6 条被漏标的等价目标、rerank 池 100→150、难例扩展查询增强（0.67 → 0.80）；
- 剩余 6 个 miss 集中在短规格小节（Writing Agent / Idea & Plan Agent / 接手命令列表等），cross-encoder 对"长查询×短文本"排序弱，为当前管线上限；
- 结论：v3.6 标记为**部分达标**（recall ✅ / precision ⚠️ 0.80），数字真实可复算；若要继续追 0.95 需更强 reranker 或多轮标注迭代（成本高、不保证）。

#### v3.9.0：Writing Agent + PDF Evidence

实现：`ReportSpec`、Markdown/PDF renderer、图表生成、数字 fidelity checker、Web 下载和 report trace。

验收：

- PDF 中所有指标、参数和配置与 source JSON 完全一致，numeric mismatch = 0；
- PDF 必含 baseline/current PSD、最优表格、失败案例、成本、trace 与复现命令；
- 缺图/缺指标/LaTeX 或 renderer failure 有结构化错误和可重试路径；
- 桌面/移动 Web 可下载 PDF；至少 3 份不同 run 报告通过视觉检查，无裁切、重叠、乱码；
- 建立 `version/v3.9.0`。

#### v4.0.0：Multi-Agent Evaluation & Closeout

实现：single-agent vs multi-agent、memory off/on、shared-model vs role-model、writer off/on 四组消融；更新 README、学习文档、简历证据。

验收：

- 固定同一任务、seed、训练预算、候选空间和失败注入，至少 6 个代表任务 x 3 seeds；
- 分开报告 plan quality、code pass rate、execution success、best NMSE、参数量、wall time、token 和成本；
- multi-agent 若未显著优于 baseline，必须如实报告，不允许只挑成功 case；
- 至少证明一项可量化收益：有效候选率、故障恢复率或人工介入次数相对 single-agent 改善 >= 20%，且总成本不超过 baseline 3 倍；
- 关键 E2E pass@1 >= 0.80、pass@3 >= 0.95；完整 trace/replay/report 均可打开；
- full offline suite、真实 DeepSeek suite、PDF fidelity、Web visual checks 全部通过；建立 `version/v4.0.0` 并推 main。

### 15.6 DeepSeek 执行纪律

1. 每次只实施一个版本，先写失败测试，再写实现，再跑 fast/full。
2. 每个版本只维护本 handoff、README 和 learning 最新版本；禁止新建 plan/handoff/诊断碎片文档。
3. 分支统一 `version/vX.Y.Z`；验收未通过不得改版本号、打 tag 或推 main。
4. scripted fixture、simulated search、真实 DeepSeek、真实训练必须分开标注。
5. 不得删除或覆盖用户未提交文件；临时文件放 `C:\Users\yzy\Desktop\codex\nonlinear-nn-agent\`。
6. 每个 Agent 的输入、输出、模型、工具权限、预算和 provenance 必须可从 Web/trace 回放。
7. 所有 PDF 数字从结构化结果读取；Writing Agent 只能组织叙事，不能创造实验事实。

### 15.7 Codex 复验结论（2026-08-11，覆盖本节更早的“完成”口径）

#### 总体判定

`v3.6-v3.9` 已形成一组质量不错、可单测的组件原型，但**尚未形成四角色 Multi-Agent 主链路**。当前可准确描述为：single-agent action-loop + 可注入 RAG/memory + 独立 Supervisor/PlanGate/CodingAgent/ExecutionAgent/reporting 组件。`supervisor_graph.py` 仍是单个 supervisor 节点；Idea/Coding/Execution/Writing 没有在同一 StateGraph 中完成真实 handoff、失败回路与终态汇总，因此不得对外宣称“multi-agent runtime 已完成”。

#### 本轮已修复

1. **CodingAgent 路径逃逸**：补丁目标现在必须是该 Agent 自己创建的 worktree，拒绝 `../`、绝对路径和主仓库根写入；新增反例测试。
2. **报告证据真实性**：`write_task_report` 不再生成合成 PSD；必须读取最优真实 execution 的 `psd_path`，且产物必须位于 workspace 内、真实存在。缺失时返回结构化失败。NMSE“相对基线提升”统一改为 `baseline_nmse_db - current_nmse_db`，使越低越好的指标显示为正提升。
3. **Memory 真正回到决策**：`ActionPlannerLoop` 新增 `planner_context_builder`，每次规划注入 top-3 knowledge citation 和 top-3 未失效 memory；CLI action 模式默认启用，可用 `--planner-context off` 做对照。
4. **多模型成本**：ModelRouter 支持按 role 配置输入/输出每百万 token 单价，不再把所有 provider/model 按同一 DeepSeek 价格计算。
5. **安装完整性**：补充 LangGraph、reportlab 运行依赖及 retrieval/Postgres/PDF 测试可选依赖；修正 Postgres JSONB 写入的序列化参数。

#### 复验结果与未通过项

| 能力 | 复验结论 | 证据/缺口 |
| --- | --- | --- |
| 全量离线回归 | 通过 | DeepSeek 提交基线 390/390；本轮修复后 396/396（87.7 秒） |
| KB recall@3 | 通过 | 保存结果 1.00，30 条项目内查询 |
| citation precision@1 | 未通过 | 0.80 < 0.95；`v3.6` 只能标记部分达标 |
| Memory 写入与 planner 消费 | 通过（本地 action-loop） | 有 provenance、stale 过滤、top-k 注入测试；默认 InMemoryStore 仍不是跨进程长期记忆 |
| Supervisor/PlanGate | 组件通过 | LangGraph 仅单节点，不是 multi-agent orchestration |
| CodingAgent 隔离 | 修复后通过 | worktree/path traversal/主仓库根写入反例已覆盖；所谓 9/10 fixture 是 test-gate 样例，不是 LLM coding pass rate |
| ExecutionAgent | 组件通过 | tool-only、故障分类、并发/resume 有测试；尚未由 Supervisor 主图调度 |
| Writing Agent | 工具通过 | 报告生成和 fidelity 可用；没有独立 LLM writing role 的调用与 handoff，不能称完整 Writing Agent |
| v4.0 消融 | 未开始 | 缺 single vs multi、memory off/on、role-model、writer off/on 的 6 tasks x 3 seeds 结果 |

#### 后续唯一主线

1. 把 `supervisor_graph.py` 扩为 `idea_plan -> plan_gate -> coding(optional) -> execution -> reflection/failure_handoff -> writing -> terminal`，每个节点只接收结构化最小上下文。
2. 把 ModelRouter 的真实 role client 配置接入上述节点，trace 记录 role/model/token/cost；Execution 节点保持无 LLM。
3. Web 增加同一 run 的角色时间线、handoff payload、memory/knowledge citation、预算与报告下载，不再只展示互相独立的组件结果。
4. 完成 v4.0 固定协议消融；没有量化收益就如实保留 single-agent baseline，不得只挑成功样例。

### 15.8 方案 A：开放式 Coding Agent 与证据驱动 Writing Agent（已批准）

#### 目标与非目标

目标：Coding Agent 能依据需求自主设计并实现**未预置模型族**；Writing Agent 能读取模型契约、源码结构和实验事实，为任意新架构生成专业、可信、可展示的中文报告。

非目标：不允许 LLM 绕过 worktree、ToolRegistry、测试门或证据校验；不让 LLM 自由填写指标；不把“执行任意 shell”当作自主性；首版只覆盖 nonlinear-modeling domain。

#### 体系结构

```text
Goal + KB/Memory + RepoMap
          |
          v
IdeaPlanAgent -> CodeChangePlan -> CodingAgent(LLM)
                                      |
                              isolated worktree
                                      |
                    patch -> static gate -> tests -> repair(max 2)
                                      |
                                      v
ModelPlugin Registry -> ExecutionAgent -> EvidenceBundle
                                            |
                                            v
                                  WritingAgent(LLM)
                                            |
                       NarrativeSpec + ArchitectureGraphSpec
                                            |
                           FidelityGate -> HTML/PDF Renderer
```

#### Coding Agent 契约

1. 输入 `CodingTaskSpec`：goal、approved plan、repo map、相关源码片段、知识 citation、历史失败事实、允许目录、测试命令、参数/时间预算。
2. LLM 输出 `CodeChangePlan`：设计理由、待新增/修改文件、接口影响、测试计划、风险，以及 unified diff；不得输出完整仓库或直接执行命令。
3. 新模型实现统一 `ModelPlugin`/`ModelDescriptor`：唯一名称、配置 schema、参数估算、build/train/predict 或 domain adapter、architecture graph metadata、支持的 evidence 字段。
4. Registry 通过显式受控注册或入口发现新插件；现有 `complex_lstsq/tiny_mlp/spline_mlp/...` 只是插件实例，不再构成模型能力白名单。
5. Gate 顺序固定：路径边界 -> patch 解析 -> Python AST/import -> plugin contract -> 配置 schema -> 参数预算 -> 目标测试 -> domain smoke training。
6. 失败只回传事实：错误类型、失败命令、关键 stderr、失败测试、相关文件；LLM 最多修复两轮，仍失败则返回可审计终态，不污染 main。
7. Coding Agent 不读取 `.env.local`，不直接获得 API key，不运行未注册 shell，不修改 handoff/README 来伪造完成证据。

#### Writing Agent 契约

1. 输入只接受 `ReportEvidenceBundle`：goal/constraints、IdeaPlan、CodeChange、ModelDescriptor、源码/AST 摘要、execution trace、真实 metrics、真实 PSD/artifacts、成本、失败案例、citation。
2. LLM 输出结构化 `ReportNarrativeSpec` 和 `ArchitectureGraphSpec`，包括章节目标、事实引用、架构节点/边/张量或信号含义、图表选择、归因陈述与限制；renderer 不再按模型名写 `if/elif`。
3. 架构图由通用 graph renderer 绘制，节点来自 descriptor + 源码分析；未知模型也能画。若 descriptor 与 AST 冲突，报告失败并要求 Coding Agent 修复 metadata，禁止猜测。
4. 所有数值、表格、PSD 和实验结论绑定 evidence path/hash；LLM 只能引用，不能创建或修改数值。归因必须标记为“实验证据”“代码事实”或“Agent 推断”。
5. 报告采用专业双层输出：HTML 为完整可交互证据报告；PDF 为 4-8 页精选版。统一中文字体注册、表格字体、页眉页脚、分页规则、色彩、图注、引用和 provenance。
6. 禁止黑方块、空白尾页、被截表格、示意 PSD 冒充真实 PSD、固定模型原理图、无证据的“为什么有效”。

#### 数据与安全边界

- LLM 只看任务所需的 top-k repo/context，不看完整 history 和 secret。
- `EvidenceRef` 至少包含 type、path/event_id、content_hash、producer、created_at；报告中的每项指标能反查 source。
- worktree 之外写入数必须为 0；工具调用和模型调用均写 trace；ExecutionAgent 继续保持 tool-only。
- Coding 与 Writing 可配置不同 provider/model/temperature/预算，ModelRouter 记录实际 role/model/token/cost。

#### 分阶段实现

1. **v4.0.0-a：开放模型契约**：ModelDescriptor、ModelPlugin、Registry、现有模型适配、descriptor/AST 一致性检查。
2. **v4.0.0-b：LLM Coding 闭环**：CodingTaskSpec、CodeChangePlan、diff parser、static/test/smoke gate、两轮事实修复、trace。
3. **v4.0.0-c：动态 Writing**：EvidenceBundle、NarrativeSpec、ArchitectureGraphSpec、通用架构图、专业 HTML/PDF、字体与分页修复。
4. **v4.0.0-d：Supervisor E2E**：Idea -> Code -> Execute -> Write 状态图、Web 角色时间线、失败回路和预算终态。
5. **v4.0.0：评测收口**：固定协议消融、真实 DeepSeek E2E、README/learning/简历证据更新。

#### 验收标准

- 5 个未在仓库预置名称的模型需求中，至少 4 个在最多两轮 repair 后通过 plugin contract、目标测试和 smoke training；不得靠修改测试放行。
- 新模型写入 main 数 = 0、worktree 外写入 = 0、secret access = 0、未注册 shell = 0。
- 3 个陌生架构生成结构明显不同的原理图；节点/边与 descriptor 和 AST 一致率 = 1.0，不存在模型名固定分支。
- 3 份报告 numeric mismatch = 0、artifact hash mismatch = 0、无真实 PSD 时结构化失败；全部通过 PDF 文本、分页和图片检查。
- PDF 无中文黑块、空白尾页、内容裁切和重叠；桌面 Web 能查看完整 evidence、角色来源和下载 HTML/PDF。
- 至少 1 次真实 DeepSeek `idea -> code -> execute -> write` E2E 成功，完整 trace 可 replay；失败注入能在唯一终态结束。
- full offline suite 全通过；新增 acceptance fixtures 明确区分 scripted、fake LLM、真实 LLM 和真实训练。

#### 面试口径

完成前：称“开放式 Coding/Writing Agent 的契约与组件实现中”。完成并通过 E2E 后：可称“基于结构化 handoff、隔离代码生成、tool-only 执行与 evidence-grounded reporting 的多 Agent 实验运行时”。任何测试桩结果不得包装成真实 LLM coding pass rate。

### 15.9 v4.0.0-a 实施计划：开放模型契约与可执行 CandidateRegistry

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. 本项目按用户要求只维护本 handoff，不新增 plan 文档。

**Goal:** 让 CodingAgent 未来生成的未知模型插件，在隔离 worktree 中经过契约校验后，可由 ExecutionAgent 通过注册工具启动固定 runner、完成训练并返回统一证据。

**Architecture:** 插件用 JSON manifest 指向 worktree 内 Python entrypoint；CandidateRegistry 只负责边界检查、动态加载和契约验证。ExecutionAgent 只调用 `run_candidate_model`，该工具以固定 `python -m nonlinear_agent.model_plugins.runner` 子进程运行插件，并对结果 JSON、指标和 artifact 路径做二次校验。

**Tech Stack:** Python dataclasses/Protocol、importlib、subprocess、JSON、现有 ToolRegistry/ExecutionAgent/unittest。

#### Task 1：定义开放模型与证据契约

**Files:**
- Create: `src/nonlinear_agent/model_plugins/__init__.py`
- Create: `src/nonlinear_agent/model_plugins/contracts.py`
- Test: `tests/test_model_plugin_contracts.py`

- [ ] 写失败测试：`ModelDescriptor` 接受未知模型名、配置 schema、训练模式、架构节点/边；拒绝空名称、非法训练模式、重复 node id 和悬空 edge。
- [ ] 运行：`python -m unittest tests.test_model_plugin_contracts`，预期因模块不存在而失败。
- [ ] 实现以下稳定接口：

```python
@dataclass(frozen=True)
class ArchitectureNode:
    node_id: str
    label: str
    operation: str
    details: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ArchitectureEdge:
    source: str
    target: str
    label: str = ""

@dataclass(frozen=True)
class ModelDescriptor:
    name: str
    version: str
    training_mode: str
    config_schema: dict[str, Any]
    nodes: tuple[ArchitectureNode, ...]
    edges: tuple[ArchitectureEdge, ...]

@dataclass(frozen=True)
class TrainingRequest:
    run_id: str
    workspace: str
    config: dict[str, Any]
    output_dir: str
    seed: int = 42

@dataclass(frozen=True)
class TrainingResult:
    status: str
    metrics: dict[str, float]
    artifacts: tuple[str, ...]
    descriptor_hash: str

class ModelPlugin(Protocol):
    descriptor: ModelDescriptor
    def estimate_parameters(self, config: dict[str, Any]) -> int: ...
    def train(self, request: TrainingRequest) -> TrainingResult: ...
```

- [ ] `validate_descriptor()` 实施上述结构规则，`descriptor_hash()` 使用 canonical JSON + SHA-256。
- [ ] 重跑测试，预期全部通过。

#### Task 2：实现安全 CandidateRegistry

**Files:**
- Create: `src/nonlinear_agent/model_plugins/registry.py`
- Test: `tests/test_candidate_registry.py`

- [ ] 写失败测试：从临时 workspace 的 `models/candidates/unseen_model.py` 加载未知插件；拒绝绝对 entrypoint、`../`、workspace 外 symlink、manifest/descriptor 名称不一致、缺失方法和参数估算超预算。
- [ ] 运行测试确认失败。
- [ ] manifest 固定 schema：

```json
{
  "schema_version": 1,
  "name": "unseen_residual_net",
  "entrypoint": "models/candidates/unseen_residual_net.py:UnseenResidualPlugin"
}
```

- [ ] 实现 `CandidateRegistry(workspace, allowed_root="models/candidates")` 的 `load_manifest()`、`load_plugin()`、`validate_candidate(config, parameter_count_max)`；所有 resolve 后路径必须仍位于 workspace/allowed_root。
- [ ] 动态模块名包含文件 content hash，避免不同 worktree 模块缓存串扰；加载后验证 descriptor、Protocol 方法和 manifest name。
- [ ] 重跑测试，预期路径逃逸和坏契约全部被拒。

#### Task 3：实现固定子进程 runner 与结果证据校验

**Files:**
- Create: `src/nonlinear_agent/model_plugins/runner.py`
- Create: `src/nonlinear_agent/model_plugins/execution.py`
- Test: `tests/test_candidate_execution.py`

- [ ] 写失败测试：候选插件执行后产生 `metrics.json` 和真实 PNG；runner 返回 status/metrics/artifacts/descriptor hash；拒绝 NaN、descriptor hash 不符、workspace 外 artifact、缺失 artifact 和非零终态。
- [ ] 运行测试确认失败。
- [ ] runner CLI 只接受 `--workspace --manifest --request --result`，加载 request JSON、调用 registry 和 `plugin.train()`，原子写 result JSON；异常写结构化 error 后返回非零。
- [ ] `run_candidate_model_tool()` 使用固定命令，不接受调用方 command：

```python
[
    sys.executable, "-m", "nonlinear_agent.model_plugins.runner",
    "--workspace", str(root), "--manifest", manifest_rel,
    "--request", request_rel, "--result", result_rel,
]
```

- [ ] 父进程重新计算 descriptor hash，检查 metrics 全部有限、artifact 存在且在 workspace 内，并返回 ExecutionAgent 兼容的 `metrics/artifacts/context_summary`。
- [ ] 重跑测试，预期通过。

#### Task 4：接入 ToolRegistry 与 ExecutionAgent E2E

**Files:**
- Modify: `src/nonlinear_agent/experiment_tools.py`
- Modify: `src/nonlinear_agent/domains/nonlinear_modeling.py`
- Test: `tests/test_candidate_execution_agent.py`
- Modify: `scripts/run_tests.py`

- [ ] 写失败测试：注册表含 `validate_candidate_model` 与 `run_candidate_model`；ExecutionAgent 能执行一个仓库从未预置名称的插件，返回有限 NMSE、参数量和 PSD；`audit_shell_calls()==0`。
- [ ] 运行测试确认失败。
- [ ] 注册两个 ToolSpec，schema 禁止 `command` 和额外字段；Domain planner tools 暴露候选模型验证/执行工具，但未知模型只有 manifest 通过后才能执行。
- [ ] 将新测试加入 fast profile；运行聚焦、fast、full。

#### Task 5：记录阶段证据

**Files:**
- Modify: `README.md`
- Modify: `docs/handoff/llm-continuation-plan.md`
- Modify: `docs/learning/experiment-agent-harness-v1.6.2.md`

- [ ] 记录“开放模型执行”而不是“LLM 已自主写模型”；列出契约、边界、固定 runner、测试数量和剩余 v4.0.0-b 工作。
- [ ] `git diff --check`；确认没有修改用户原有 dashboard、删除文件和未跟踪实验目录。
- [ ] 验收后建立 `version/v4.0.0-a`，按功能拆分提交；未完成真实 LLM coding 前不得写 Coding pass rate。
