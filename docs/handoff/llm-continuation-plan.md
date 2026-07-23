# Nonlinear NN Agent Harness 交接与维护文档

更新时间：2026-08-04

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

当前覆盖 5 类 case：

- target hit under budget
- invalid planner output rejection
- runtime failure handling
- reflection-based recovery
- experiment budget stop

3 个 case 只能算 smoke test。当前 5 个 case 可以支撑面试中的“我有评估体系”说法，但更强版本仍应加入多 seed、长上下文压缩、timeout/retry、真实 DeepSeek replay。

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
- `llm_with_reflection` 相对 `llm_no_reflection` paired delta = +2.34 dB，**不显著**，未观察到稳定优势。
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
- 下一轮 planner prompt 能读到 `recovery_actions` 和 `avoid_next`。
- benchmark/leaderboard 过滤 reflection/summary，不污染实验统计。

推荐设计：确定性 reflection 负责错误分类和恢复策略；LLM reflection 只适合做受控假设生成。

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
- 20000 参数预算 + 历史先验注入：`llm_with_reflection` paired delta **-4.28 dB（显著）**，hit 78% vs 28%（`benchmarks/nonlinear-search-v1-v20000/`，报告 `docs/experiments/nonlinear-search-ablation-v2.md`）。
- Benchmark 10 case：fake 模式 hit 7/10；DeepSeek 模式 hit 5/10，但 Guard 拦截率 80–98%（模型 schema 遵从性不稳定，已知边界）。
