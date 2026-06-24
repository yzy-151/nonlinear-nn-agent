# 5 分钟演示脚本 — nonlinear-nn-agent v2.0.0

## 时间线

### 00:00-00:40：Harness 与自动训练脚本的区别

- 展示架构图：Planner → Guard → Runtime → ToolRegistry → Reflection
- **核心论点**：这不是固定流程的训练脚本。LLM 每轮根据目标、历史错误和指标重新决策；
  Guard 拦截无效计划；Runtime 通过注册工具执行；Reflection 把结构化事实喂回下一轮。
- 演示：`python agent.py run --provider fake --max-rounds 2`
- 展示结构化 plan 输出：`{"summary": "策略摘要", "experiments": [...]}`
- **面试要点**：LLM 只输出 JSON plan，永远不直接执行命令。规划与执行完全解耦。

### 00:40-01:30：ToolSpec、Guard 和 DomainPlugin

- 展示 `ToolSpec` 定义：name、description、input_schema、category、error_policy——
  这是 LLM 能读懂的"工具说明书"。
- 展示 Guard 拦截无效覆盖（用 fake plan 里设 `spline_range: null` 的 case）
- 展示 `NonlinearModelingDomain`（非线性 RF 建模）和 `SyntheticRegressionDomain`（合成回归）——
  同一个 Planner/Runtime，不同的工具集合、不同的设计空间、不同的指标。
- **核心论点**：Harness 是领域无关的。新增一个 DomainPlugin 就新增一个实验领域，
  Planner/Guard/Runtime 代码一行不用改。
- 两个 domain 的互换性验证：`python -c "..." ` 展示两个 domain 通过同一 Planner 路径。

### 01:30-02:30：Fake Planner SSE 流、Trace、取消、恢复

- 启动 server：`python agent.py serve --port 8001`
- 打开 Web UI：http://127.0.0.1:8001
- 选 "Agent Planner" tab，Provider 选 Fake，点 Start
- 展示实时 SSE 事件流：plan_generated → tool_start → tool_end → metric → complete
- 展示 v2.0 SSE event ID：每帧 SSE 带 `id: <sequence>` 单调递增
- 展示 Stop 按钮：POST /cancel/{session_id} 在训练中途停止运行
- 展示 Trace：`traces/{session_id}.jsonl` 含层级 span（trace_id/span_id/parent_span_id）
- **面试要点**：可观测性不是后加的——每个事件从 Runtime 产生到浏览器展示，
  经过 ToolRegistry → TraceLogger → SSE encode → EventSource，全链路可追踪。

### 02:30-03:40：Random / TPE / LLM / Reflection 对照实验

- 展示协议：`python agent.py compare-search --dry-run`
  4 methods × 5 seeds × 10 trials = 200 个有效训练 trial
- 展示 smoke 模式实际运行：`python agent.py compare-search --smoke`
  输出 24 个 trial，包含 trials.jsonl + summary.json + summary.csv
- 展示每种方法的统计：best NMSE、target hit rate、rejected rate、runtime failure rate——
  全部带 95% bootstrap CI（固定 seed=20260802，2000 次重采样）
- 展示 Reflection paired delta：`llm_with_reflection` vs `llm_no_reflection`，
  delta 按 seed 配对计算，不混合不同 seed
- **核心论点**：如果 CI 跨零，如实报告"未观察到稳定优势"，不挑最好 seed 展示。
- 打开 Dashboard：展示 Strategy Comparison 区块（对照表 + paired delta 说明）

### 03:40-04:30：真实 DeepSeek 自我修正案例

- 展示真实 DeepSeek 运行中 LLM 输出 `spline_range: null` 的 bad case
- 展示 Guard 拒绝记录："Unsupported planner override fields: rank"
- 展示 Reflection 如何捕获失败原因：`failure_causes: ["spline_range must be a number"]`
- 展示下一轮：LLM 看到 failure_causes 后主动避开错误
- **核心论点**：Guard 不崩溃——它产出结构化的拒绝记录，喂回 Planner 的上下文。
  这就是 plan-run-observe-reflect 闭环中的 "observe" 和 "reflect"。

### 04:30-05:00：SQLite 控制面、项目边界和"没做什么"

- 展示 `RuntimeControlPlane`：SQLite + WAL 模式，原子 job claim，单调 event sequence，
  SSE replay 通过 Last-Event-ID
- 压测验证：`python agent.py stress-runtime --concurrency 8 --requests 100`
  （dup rate = 0，event loss = 0，consistency = 1.0）
- **明确边界**：
  - 不做 RAG / GraphRAG / 长期语义 Memory / Multi-Agent Team → 这些属于 PaperStorm 项目
  - SQLite 不描述成分布式生产数据库 → 是本地单进程可靠性方案
  - MCP bridge 不描述成完整官方 SDK Server → 是 JSON-RPC 桥接
  - 不根据单个 seed 声称 Agent 优于 Optuna → 看 5-seed 均值和 CI
  - 模型类型是 domain 预设的设计空间，LLM 在其中做智能搜索和策略调整，
    不是让 LLM 写 PyTorch 代码自主设计新架构
- 收尾："对整个技术栈哪一层有问题？"
