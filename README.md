# Nonlinear NN Agent Harness

基于 LLM 的**模型寻优提效工具**（Agent Harness Runtime）：把人工遍历候选模型与超参（模型族、卷积核长度、网络层数、学习率、scheduler、epoch 等）的实验组织为 **plan → validate → execute → observe → reflect** 的可复现工作流——LLM 负责设计实验，Harness 负责受控工具调用、Schema Guard、可定制白名单、真实训练、指标验证、SSE 实时观测与结果落盘。

项目把"让模型做实验"这件事工程化：**计划与执行解耦**、**领域知识插件化**、**四种搜索策略可公平对照**、**运行可靠性可压测**。所有结论都能从 JSON/CSV 复算。

## 界面预览

Agent Planner 界面——内置多种任务 Domain（非线性建模 / PIM 对消 / 寄存器配置 / 合成回归），切换即更新可寻优白名单：

![Agent Planner 界面](docs/assets/screenshots/web-ui-agent-planner.png)

Benchmark 页签（10-case 评估，含 planner 成功率、自我修正、token/成本指标）：

![Benchmark 页签](docs/assets/screenshots/web-ui-benchmark.png)

可优化方向白名单（3.0）：勾选/取消勾选可寻优的模型与超参方向，实时更新 Guard 白名单与 LLM 设计空间（未勾选的方向被固定、不再被搜索）：

![可优化方向白名单勾选](docs/assets/screenshots/web-ui-optimize-1.png)

Agent Loop 实际运行的 SSE 事件日志（plan → tool → metric → complete 实时流）：

![运行日志](docs/assets/screenshots/web-ui-optimize-2.png)

Strategy Comparison 页签（四策略对照，含 95% CI 与 paired delta）：

![Strategy Comparison 页签](docs/assets/screenshots/web-ui-compare.png)

本地诊断 Dashboard（聚合全部实验指标、错误分布与策略对照）：

![Diagnostics Dashboard](docs/assets/screenshots/dashboard.png)

## 核心特性

- **Planner / Runtime 解耦**：LLM 只输出结构化 JSON 实验计划，不直接执行命令；Runtime 只调用已注册工具
- **Schema Guard 与预算控制**：白名单字段校验、结果字段黑名单、参数预算估算、`model_type` 白名单；被拒计划单独统计并回喂给 LLM 自动修正
- **可定制可优化方向（3.0）**：Web UI 可逐个开启/关闭可优化的模型与超参方向（模型族 `model_type`、卷积核 `kernel_size`、层数 `num_layers`、`learning_rate`、`scheduler`、`epochs` 等），开关实时更新 Guard 白名单与 LLM 设计空间——关闭的方向被固定，只搜开启的方向
- **DomainPlugin 可迁移**：非线性建模与合成回归两个领域插件共用同一套 Harness，证明系统可迁移
- **四种搜索策略统一对照**：`random_search`、`optuna_tpe`、`llm_direct`（LLM 直接决策，无反思）、`llm_program_reflection`（程序基于实验结果做确定性反思/路由）在同一协议、同一数据划分下公平比较，输出 bootstrap 95% CI 与 paired delta
- **历史先验注入**：把历史最优候选（-42 dB 级）作为知识注入 Reflection 策略，让 LLM 在已知最优邻域继续搜索
- **结构化 Memory Backend（3.6）**：typed memory（semantic/episodic/procedural）带完整 provenance（run/action/config/dataset hash、evidence refs、model、prompt hash、confidence），namespace = domain + dataset hash + model family 隔离，`supersedes`/invalidate 保留审计链；CLI action-loop 默认把 top-k 有效 memory 与知识 citation 注入下一次 planner，可用 `--planner-context off` 做消融；Web Memory 页只读检查
- **Knowledge Base（3.6）**：白名单目录 ingestion（chunk 带 source/content hash/version/citation）+ **混合检索**（BM25 + 本地多语言向量召回 + cross-encoder rerank + query expansion）。当前 30 条项目内中文查询 recall@3 = **1.00**、citation precision@1 = **0.80**（未达到计划中的 0.95）；真实评测可复现：`python scripts/eval_knowledge_retrieval.py`
- **受控执行与证据报告（3.8-3.9）**：CodingAgent 使用独立 worktree、文件白名单和 test gate；ExecutionAgent 只调用 ToolRegistry；`write_task_report` 只接受真实实验 PSD，缺图时结构化失败，不生成示意数据冒充证据
- **SSE 实时观测**：事件 ID、15 秒心跳、`/cancel`、Last-Event-ID 断线重放
- **SQLite 控制面**：请求去重、任务 lease、原子 claim、单调事件序列（WAL + busy timeout），并发压测通过
- **层级 Trace**：`trace_id/span_id/parent_span_id/attempt/model/config_hash/token/cost` 全链路
- **Hybrid Operations Console（v4.1.0）**：Multi-Agent 为默认首页，统一承载 Agent Planner、Fixed Workflow、实验对照、Benchmark、Memory、Reports 与 Diagnostics。SSE 同时驱动 Timeline、Console、Raw Events 和 Inspector；Multi-Agent 结果区展示经服务端安全裁剪的搜索/终评摘要、NMSE、参数量、PSD 与报告链接。知识库文件、启用开关和 Sources 预览已预留 UI 契约，但当前明确标记为“尚未接入”，不会伪装成已影响 PlanAgent
- **开放模型候选执行（v4.0.0-a）**：CodingAgent 未来生成的模型不再受现有 `model_type` 名称白名单限制；候选代码以 `ModelPlugin + ModelDescriptor + manifest` 描述模型、训练入口和架构图，经 CandidateRegistry 路径/契约/配置/参数预算校验后，由 ExecutionAgent 调用固定子进程 runner 执行。父进程复核有限指标、参数量、descriptor hash 和全部 artifact 路径；当前阶段提供执行基础设施，尚不代表真实 LLM coding pass rate
- **LLM Coding 闭环（v4.0.0-b）**：CodingAgent 通过 `ModelRouter` 的 `coding` 角色调用可配置模型，要求一次返回完整候选包（源码、manifest、descriptor、参数估算和 `train()`），而非只给 `ModelClass`。严格 JSON/候选目录/AST capability gate 通过后，固定 runner 执行 contract validation 与真实 smoke training；失败只提取语法、契约、预算或产物事实，最多回传两轮让 coding LLM 重写完整候选包。每轮只落 prompt/response/file hash 与 gate facts，避免把源码或密钥写进 trace。离线双轮修复 E2E 已覆盖，真实 DeepSeek pass rate 留待固定任务集评测
- **证据驱动 WritingAgent（v4.0.0-c）**：`EvidenceBundle` 把目标、约束、`ModelDescriptor`、执行指标、真实 PSD、失败和 trace 压缩成带 ID 的事实；WritingAgent 通过 `ModelRouter(writing)` 输出六段 `NarrativeSpec`，每段必须引用已有 evidence ID，任何未知引用或源数据不存在的数字都会被 fidelity gate 拒绝。架构图按 descriptor 的任意 nodes/edges 动态布局，不再按 `model_type` 猜固定原理图；HTML 与 PDF 共用同一份 print-ready 页面，中文字体、A4 分页、表头续页和移动端均已覆盖。离线陌生 Wavelet-LUT fixture 的 3 页 PDF 已完成视觉复验，真实模型写作质量仍需在固定任务集上评测
- **四角色 Supervisor 主链（v4.0.0-d）**：LangGraph 现在真实连接 `Idea/Plan -> PlanGate -> Coding -> tool-only Execution -> evidence-grounded Writing -> terminal`，不再只是互相独立的组件。结构化 state 保留 plan、code/execution/report result、失败事实和角色 timeline；timeout/NaN/缺产物可在有限预算内回到下一轮 Plan，cancel、invalid plan、模型预算越界和不可恢复错误都只产生一个终态。`MultiAgentRuntime` 复用现有 CodingAgent、ExecutionAgent、WritingAgent 和 ModelRouter，训练产物会从隔离 worktree 确定性发布到主工程 `reports/<run>/evidence/`，Web 的 Multi-Agent 面板通过 SSE 展示每个角色的输入/输出引用、provider/model、token、cost、latency、失败 handoff 和报告路径。离线 E2E 与故障注入已覆盖，真实 DeepSeek 全链评测留给 v4.0.0 收口
- **真实 3x3 因果搜索（v4.0.0-e）**：一个连续 DeepSeek run 完成 3 轮、9 个搜索候选和 1 次独立终评。Round 2/3 接收的是压缩后的指标/失败事实，不含源码与原始 history；CodingAgent 为每个候选生成完整插件并在独立 worktree 做最多两次修复。固定 MPDPD `x/d`、`train_ratio=0.8`、seed=42；9 个候选中 8 个完成，最优 `LUTSplineV3` 为 24 参数、搜索/终评 NMSE 均为 `-23.0778 dB`，未达到 `-41 dB`。这次真实运行验证了失败隔离、跨轮修正和通用 WritingAgent，但也证明当前 LLM 自主算法质量仍明显弱于历史先验模型

## v4.0.0-e 真实 DeepSeek 验收

运行协议：`deepseek-chat` 分别承担 Idea/Plan、Coding、Writing；三个 round 每轮恰好三个候选，单候选参数不超过 4000、epoch 不超过 50，最后重新执行全局最优候选。主搜索 timeline 记录 21 次模型调用、37,914 prompt tokens、71,483 completion tokens，估算成本约 `$0.0889`（不含报告视觉调整时单独重跑的 Writing 调用）。

| Round | Candidate | Status | NMSE / dB | Params |
| --- | --- | --- | ---: | ---: |
| 1 | ComplexMemoryPolynomial | completed | -0.0149 | 38 |
| 1 | LUTSpline | failed | - | - |
| 1 | ComplexRational | completed | -0.0474 | 146 |
| 2 | ComplexMemoryPolynomialV2 | completed | 1.1011 | 20 |
| 2 | ComplexRationalV2 | completed | -0.0272 | 34 |
| 2 | LUTSplineV2 | completed | 0.6773 | 130 |
| 3 | ComplexRationalV3 | completed | 12.9968 | 698 |
| 3 | CompactComplexMLP | completed | -6.7960 | 266 |
| 3 | **LUTSplineV3** | completed | **-23.0778** | **24** |
| Final | **LUTSplineV3** | completed | **-23.0778** | **24** |

[下载完整 6 页 PDF 报告](docs/reports/v4.0.0-e-deepseek-3x3-report.pdf)

![最终模型架构](docs/assets/results/v4.0.0-e/architecture.png)

![最终复评 PSD](docs/assets/results/v4.0.0-e/final-psd.png)

![九次搜索实验 NMSE](docs/assets/results/v4.0.0-e/nine-experiment-nmse.png)

结论边界：本轮目标未命中，不能把 `-23.08 dB` 包装成通信算法最优；它的价值是证明 Agent Harness 能让真实模型生成代码、受控执行、从失败事实调整计划并形成可审计报告。下一项质量硬化应由 Executor 根据标准预测 artifact 重新计算 NMSE，避免仅信任候选自报指标。

## 内置实验领域（3.1）

Web UI 的 Agent Planner 可直接切换以下领域，且自动扫描 `data/` 与 `examples/*/data/` 下的 `.mat` 文件，在"Experiment Data"下拉框中选择本次实验的数据集：

| 领域 | 实验内容 | 可寻优参数 | 主指标 |
| --- | --- | --- | --- |
| Nonlinear Modeling | RF MPDPD 非线性建模 | model_type / memory_depth / learning_rate / kernel_size / num_layers 等 | nmse_db |
| PIM Cancellation | 三阶 PIM 对消：`tx(32×L)` 拟合 `rx(32×L)` | model_type / memory_depth / reg / normalize_power | res_db（残余，含参数量/每通道最大功率/参数分布等中间变量） |
| Register Config | 寄存器表单配置实验 | mu / optimizer(adam\|sgd) / data_choice / lut_choice | final_mse_db |
| Synthetic Regression | 合成回归演示 | degree / reg_strength | val_mse |

任务 Domain 与实验数据选择：

![Domain 选择](docs/assets/screenshots/web-ui-domain-picker.png)

![实验数据选择](docs/assets/screenshots/web-ui-data-picker.png)

> 扩展接口：通过 `DomainPlugin` 接入新实验领域——实现 `design_space` / `validate_candidate` / `build_tool_registry` 等方法后，Planner、Guard、搜索策略与前端自动获得支持，无需改动 Harness 主链路；也可以用 `SimpleDomain`（设计空间 + 一个执行函数）零样板接入。

## 快速开始

环境要求：Python 3.9+，Windows / Linux / macOS。

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行测试（确认环境正常）
python -m unittest discover tests

# 3. 离线跑一次完整 Agent Loop（无需 API Key）
python agent.py run --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\my-first-run

# 4. 启动 Web UI（浏览器打开 http://127.0.0.1:8000）
python agent.py serve --host 127.0.0.1 --port 8000
```

Web 首页默认进入 `Multi-Agent`。左栏选择运行模式，中栏在 `Timeline / Console / Raw Events` 间切换，点击 Timeline 事件可在右侧 Inspector 查看 `input_refs`、`output_refs`、`model_usage`、失败事实和原始 payload。`docs/knowledge/nonlinear-modeling/` 目前只是下一阶段检索接线的预留路径，禁用状态是有意的真实性约束。

![v4.1.0 Hybrid Operations Console](docs/assets/ui/v4.1.0-operations-console.png)

## 架构

```mermaid
flowchart LR
    User -->|goal / constraints| Planner
    Planner -->|JSON plan| Guard
    Guard -->|validated overrides| Runtime
    Runtime -->|ToolCall| ToolRegistry
    ToolRegistry -->|execution| Train["train.py / fit"]
    Runtime -->|TraceEvent / metric| SSE["SSE / Trace / Session"]
    SSE --> History["History + Reflection"]
    History -->|compressed context| Planner
    SSE --> SQLite["Control Plane (idempotent / lease / replay)"]
```

开放模型的代码生成与执行链路独立受控：

```mermaid
flowchart LR
    Idea["Idea / Plan"] --> Task["CodingTaskSpec"]
    Task --> Coding["CodingAgent via ModelRouter(coding)"]
    Coding --> Plan["CodeChangePlan: complete candidate package"]
    Plan --> Gate["JSON + path + AST capability gates"]
    Gate --> Registry["CandidateRegistry contract validation"]
    Registry --> Runner["Fixed subprocess runner"]
    Runner --> Evidence["NMSE + parameter count + metrics.json + PSD"]
    Gate -->|failure facts, at most 2 repairs| Coding
    Runner -->|failure facts, at most 2 repairs| Coding
```

核心模块：

| 模块 | 职责 |
| --- | --- |
| `planner.py` | 构造 prompt、解析 LLM 返回的 JSON 计划（容错 + few-shot + 字段契约） |
| `planner_validation.py` | Schema Guard：白名单/黑名单、类型、参数预算、别名规范化 |
| `loop.py` | 主循环：plan → validate → execute → observe → reflect，含被拒自动重试 |
| `runtime.py` | Harness Runtime：逐步执行工具链、事件流、session/trace |
| `tools.py` | ToolCall / ToolResult / ToolSpec / ToolRegistry |
| `domains/` | DomainPlugin 协议 + nonlinear-modeling / synthetic-regression 插件 |
| `search/` | SearchStrategy 协议 + Random / Optuna TPE / LLM 策略 |
| `evaluation_statistics.py` | bootstrap 95% CI、paired delta、summary 生成 |
| `control_plane.py` | SQLite 控制面（请求去重、任务 lease、事件序列） |
| `coding_agent.py` | 完整候选包 JSON 契约、候选路径/AST 闸、coding 角色路由、两轮事实修复与 hash trace |
| `model_plugins/` | 开放模型 descriptor/plugin 契约、CandidateRegistry、固定子进程 runner 和证据复核 |
| `server.py` | FastAPI + SSE 服务层（含 Last-Event-ID 重放与取消） |
| `web_ui.py` / `web/` | 静态资产白名单入口，以及无构建步骤的 HTML/CSS/ES modules Operations Console |
| `dashboard.py` | 离线诊断 Dashboard 生成器 |

## 命令行速查

| 命令 | 用途 |
| --- | --- |
| `python agent.py run --provider fake` | 离线 Agent Loop（预设计划） |
| `python agent.py run --provider deepseek` | 真实 LLM Agent Loop（需 `DEEPSEEK_API_KEY`） |
| `python agent.py multi-agent --provider deepseek --rounds 3 --experiments-per-round 3 --final-evaluation` | 四角色真实 3x3 搜索、独立终评与证据报告 |
| `python agent.py benchmark` | Agent 行为回归 Benchmark（离线 fake，默认 10 case） |
| `python examples\nonlinear_fit\run_benchmark.py --provider fake --case-count 50` | 参数化 **50-case** 对比（10 类型 × 5 阈值变体），[报告](docs/experiments/nonlinear-benchmark-50case.md) |
| `python examples\nonlinear_fit\run_benchmark.py --provider deepseek` | 真实 LLM + 真实训练的 Benchmark（可 `--case-count` 扩展） |
| `python agent.py compare-search` | 四种搜索策略真实对照 |
| `python agent.py stress-runtime` | SQLite 控制面并发压测 |
| `python agent.py serve` | 启动 Web UI / SSE 服务 |
| `python agent.py dashboard` | 生成诊断 Dashboard |

## 实验任务：非线性系统建模与对消

项目解决的信号处理问题：射频非线性系统（记忆多项式 MPDPD）的输入 `x` 经系统产生带非线性失真的输出 `d`。任务是学习系统的校正模型，使校正后的信号逼近理想目标 `d`——即**非线性对消 / 线性化**。

**指标 NMSE（归一化均方误差，dB）**：

```text
NMSE = 10 * log10( mean(|prediction - target|^2) / mean(|target|^2) )
```

- `baseline NMSE`：不建模时输入 `x` 相对目标 `d` 的误差（未对消）
- `current NMSE`：MPDPD 模型输出相对目标的误差（对消后）
- 提升量 = baseline − current（越大越好）

**频谱证据**：PSD 图中校正后信号（绿线）与目标（橙线）重合得越好，说明非线性失真被对消得越干净：

![PSD 对消结果](docs/assets/psd-exp016-best-41db-run.png)

**代表性实验结果**：

| 实验 | 模型 | 关键参数 | 参数量 | NMSE (dB) | 来源 |
| --- | --- | --- | ---: | ---: | --- |
| exp016 | complex_lstsq | mem=220 mp=9 | 3980 | -37.49 | LLM 规划 run |
| tiny_md20_mp3_hu96 | tiny_mlp | mem=20 mp=3 hu=96 relu **epochs=10000** | 12386 | **-42.26** | 历史最优 |
| exp_492 | spline_mlp | mem=40 mp=1 hu=180 silu epochs=4000 | 21062 | -41.99 | 历史最优 |
| v26 LLM 设计 | tiny_mlp | mem=16 mp=3 hu=128 silu **epochs=20000** | 19490 | **-42.43** | 真实 LLM benchmark |

**为什么同时存在 -37 dB 与 -42 dB 两类结果（两套实验的边界）**：

- 搜索对照矩阵（`compare-search`）使用**离线模拟 LLM**（邻域采样，token=0），且为避免全矩阵训练爆炸，过滤了超长训练候选（epochs>2000），因此该矩阵只探索到 complex_lstsq 平台区（-37~-38 dB）——它回答"固定预算下哪种搜索策略更高效"；
- 真实 LLM benchmark（36000s 训练预算）允许 epochs=10000+ 的神经模型长训练，才到达 -42 dB 区——它回答"真实 LLM 在足够预算下能否找到历史最优区域并继续改进"。

## 实验证据

### 搜索策略对照（真实训练）

统一协议（`benchmarks/protocol/nonlinear-search-v1.json`）下，4 策略 × 5 seeds × 10 有效训练 trial，20000 参数预算：

| 方法 | best NMSE mean (dB) | target hit | rejected |
| --- | ---: | ---: | ---: |
| random_search | -36.02 | 10% | 32% |
| optuna_tpe | -37.02 | 22% | 35% |
| llm_direct | -33.59 | 28% | 10% |
| **llm_program_reflection（含历史先验）** | **-37.87** | **78%** | 24% |

Reflection 配对消融：**delta = -4.28 dB，95% CI [-10.0, -0.4]，显著**。

**策略命名语义**：

- `llm_direct`：LLM 直接根据目标/历史给出下一轮候选，不消费任何反思信息；
- `llm_program_reflection`：**程序针对实验结果做确定性反思与路由**——由 ReflectionPolicy 规则从结果中提取失败原因/事实，结合历史先验候选注入下一轮建议；
- LLM 自主反思（模型自己撰写反思并据此决策）是后续对照方向，当前版本以程序确定性反思为准。

![Best-so-far 对比](benchmarks/nonlinear-search-v1-v20000/best-so-far.png)

![Reflection 消融](benchmarks/nonlinear-search-v1-v20000/reflection-ablation.png)

### 大规模策略对比（合成域，1000 trial，早期对照）

> 早期对照：空间仅 50 组合，50 trial 无放回 ≈ 全枚举，random 的 best 接近最优是空间太小所致；升级为 [synthetic-hard 单点命中](#真实-api-策略对比synthetic-large400-组合空间) 后 random 命中率降至 0.4%。

把"固定预算下哪种搜索策略收敛更快"放大到 1000 trial（4 策略 × 5 seeds × 50 trial，合成回归域、真实计算、零 LLM 成本、零拒绝）。详见 [v3 报告](docs/experiments/nonlinear-search-ablation-v3.md)。

| 方法 | best val_mse mean | 平均收敛 trial（0-based） |
| --- | ---: | ---: |
| random_search | 0.0434 | 18.6 |
| optuna_tpe | 0.0434 | 13.4 |
| llm_direct | 0.0434 | **11.4** |
| **llm_program_reflection** | **0.0434** | **11.4** |

**LLM 式策略（邻域采样 + exploitation）收敛最快（11.4），Optuna 次之（13.4），Random 最慢（18.6）**。四策略最终都收敛到全局最优 0.0434——因为合成域只有 50 个合法组合、50 trial 无放回 ≈ 全枚举，真正的差异体现在收敛速度；本表早期版本中 Optuna 更差，根因是 Optuna 适配器把离散枚举当连续区间采样（已修复，详见 [v3 报告](docs/experiments/nonlinear-search-ablation-v3.md)）。合成域无历史先验可注入，reflection 与 direct 等价（paired delta = 0）——reflection 的增益来自知识注入，见上节真实非线性域 -4.28 dB 的显著提升。

![四策略收敛速度对比](docs/assets/experiments/strategy-convergence-speed.png)

### 真实 API 策略对比（synthetic-large，400 组合空间）

> 400 组合版：最优区域占 3.2%，random 无放回 50 次仍能摸到区域边缘（best 持平、收敛慢）；随机因素在下方 synthetic-hard 版中被单点命中指标消除。

把 LLM 策略换成**真实 DeepSeek 调用**（deepseek-v4-flash，prompt+Guard 重试+token/成本统计），并把空间放大到 20 degree × 20 reg = 400 组合（50 trial 只覆盖约 12%）。4 策略 × 5 seeds × 50 trial，LLM 总成本约 $0.34：

| 方法 | best val_mse | 平均收敛 trial | token 用量 | 成本 |
| --- | ---: | ---: | ---: | ---: |
| random_search | 0.0434 | 23.0 | 0 | $0 |
| optuna_tpe | 0.0434 | 26.2 | 0 | $0 |
| **llm_direct（真实 API）** | **0.0434** | **3.8** | 293,843 | $0.165 |
| **llm_program_reflection（真实 API）** | **0.0434** | **4.2** | 309,987 | $0.171 |

**真实 LLM 收敛快约 6 倍**：模型从 prompt 直接推理出"真函数是 degree-5、小正则最优"，首轮即给出 degree≈5 候选；Optuna/Random 需 20+ 次采样。flash 在 `json_object`+低温度下会输出空串，已通过关 json_mode、temperature=0.7、max_tokens=512 稳定到 3~6s/次（详见 [v3 报告](docs/experiments/nonlinear-search-ablation-v3.md)）。

![真实 API 四策略收敛速度对比](docs/assets/experiments/strategy-convergence-speed-real.png)

**Reflection 先验注入版（验收目标）**：给 `synthetic-large` 补充模拟历史先验（degree=5/reg=0.01 → val_mse 0.0434 等真实评估值），`llm_program_reflection` 的 prompt 注入 "Known best candidates"，`llm_direct` 不注入：

| 方法 | best val_mse | 平均收敛 trial | per-seed |
| --- | ---: | ---: | --- |
| random_search | 0.0434 | 23.0 | [16,10,49,29,11] |
| optuna_tpe | 0.0434 | 26.2 | [17,33,26,38,17] |
| llm_direct（真实 API） | 0.0434 | 12.0 | [2,42,4,2,10] |
| **llm_program_reflection（真实 API + 先验）** | **0.0434** | **2.4** | **[2,3,4,2,1]** |

**llm_program_reflection 平均 2.4 个 trial 收敛**（每个 seed 前 4 个 trial 内命中全局最优），比 direct 快 5 倍、比 Optuna/Random 快约 10 倍——reflection 的增益来自历史知识注入，在真实 API 下依然成立。

![先验注入版收敛速度对比](docs/assets/experiments/strategy-convergence-speed-real-priors.png)

**更难的域（synthetic-hard，2500 组合 + 单点命中指标）**：400 点空间里 random 靠"最优区域占 3.2% + 无放回 50 次"仍能摸到区域边缘；升级到 2500 组合（最优区域 0.6%）后运气因素被消除：

| 方法 | 单点命中（250 trial） | seed 命中 | 平均首命 trial |
| --- | ---: | ---: | --- |
| random_search | 1（0.4%） | 1/5 | 24.8 |
| optuna_tpe | 1（0.4%） | 1/5 | 23.8 |
| llm_direct（真实 API） | 64（26%） | 3/5 | 14.8 |
| **llm_program_reflection（真实 API + 先验）** | **131（52%）** | **5/5** | **2.6** |

**random/optuna 250 次采样各只命中单点最优 1 次；reflection 5/5 seed 命中、命中率是它们的约 130 倍**。单点命中指标把"碰运气"和"真找到"区分开。

![synthetic-hard 收敛对比](docs/assets/experiments/strategy-convergence-speed-hard.png)

![单点最优命中率](docs/assets/experiments/strategy-single-point-hit-rate.png)

### 指标可视化

![各策略 best NMSE 分布](docs/assets/experiments/strategy-best-nmse-distribution.png)

![命中率与 Guard 拒绝率](docs/assets/experiments/strategy-hit-vs-rejected.png)

![单 trial 训练时长](docs/assets/experiments/strategy-training-time.png)

真实 LLM benchmark 逐 case：

![Benchmark 逐 case NMSE](docs/assets/experiments/benchmark-per-case-nmse.png)

![LLM token 用量](docs/assets/experiments/benchmark-llm-tokens.png)

### 历史先验注入：达到 -42 dB

项目历史记录显示，达到 -41 dB 需要**神经模型长训练**（`tiny_mlp` + `epochs=10000` 等），而非 complex_lstsq 平台区。把这些候选写入 `configs/priors/nonlinear-modeling.json` 并注入 planner prompt 后，真实 DeepSeek 在已知最优邻域上继续搜索，设计出 **-42.43 dB**（tiny_mlp mem=16 / mp=3 / hu=128 / silu / epochs=20000）：

![-41 dB 目标 run 的最优候选 PSD](docs/assets/psd-exp016-best-41db-run.png)

### 旧版参数敏感性回归（10 模板 → 50 变体）

10 个基础行为 case 之上按 5 档目标阈值参数化扩到 **50 case**（10 类型 × 5 变体），指标全量上报：

| 运行方式 | case | target_hit | rejected | planner_success | self_correction | runtime_failure | best NMSE | tokens | 成本 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 离线 fake（确定性） | 50 | 0.38 | 22% | 0.78 | 15 | 6.6% | -36.5 | 0 | $0 |
| 真实 DeepSeek + 真实训练（v26，10 case） | 10 | **0.9** | **7.4%** | **0.93** | 3 | 7.4% | **-42.43** | 73,523 | $0.065 |
| 真实 DeepSeek + 真实训练（50 case） | 50 | 运行中… | | | | | | | |

这两行不能直接比较：50-case 是离线 fake 的 10 类模板 × 5 阈值/轮次变体，0.38 只反映参数敏感性；0.9 来自真实 DeepSeek 的 10-case 运行（9/10）。表中的 `self_correction` 是旧版相邻记录计数，不代表 LLM 发起新规划后的因果纠错。新版评测使用独立 Agent 任务和 `causal_correction_*` 指标。

### Action-level Agent 与独立任务评测

`run --mode action` 保留 fixed workflow 作为可靠基线，同时新增真正的逐步循环：LLM 每次只返回一个 `tool_call` 或 `stop`，Action Guard 按 `ToolSpec` 校验，Runtime 执行后把 observation、`planner_call_id`、`event_id` 与 `caused_by_event_ids` 回传给下一次规划。

当前单独定义了 18 个 `nonlinear-modeling` 独立行为任务，覆盖工具契约、失败恢复、产物验证、停止条件、历史与压缩上下文。`agent-benchmark` 使用生产 ToolSpec 和确定性 fault fixture 回归 Guard/Loop/scorer，并把每个 planner/action/event/observation 写入结果；Web Benchmark 页也可通过 SSE 查看。scripted pass@1 只能证明 Harness 契约回归，真实 DeepSeek pass@1/pass@3 仍需显式运行后才可引用。

```powershell
python agent.py run --mode action --provider fake --fake-action '{"type":"stop","action_id":"demo-stop","reason":"demo","caused_by_event_ids":[]}'
python agent.py agent-benchmark --provider scripted --attempts 1 --output-dir benchmarks/agent-tasks-v1
python scripts/run_tests.py fast
python scripts/run_tests.py full
```

离线独立任务证据：[逐 case 结果](benchmarks/agent-tasks-v1/results.json) / [摘要](benchmarks/agent-tasks-v1/summary.md)。

真实 LLM 运行结果与原始数据：

```text
benchmarks/deepseek-v26/results.json
benchmarks/fake-v21b/results.json
docs/experiments/nonlinear-search-ablation-v1.md
docs/experiments/nonlinear-search-ablation-v2.md
docs/experiments/nonlinear-search-ablation-v3.md
```

## 可靠性压测

```powershell
python agent.py stress-runtime --concurrency 8 --requests 100 --failure-rate 0.1 --output-dir benchmarks/runtime-v2
```

验收线（本地单进程 SQLite 基线）：重复执行率 0、事件丢失率 0、终态一致率 1.0、注入 10% 故障后恢复率 ≥ 0.95。

## 目录结构

```text
src/nonlinear_agent/       核心包（planner/guard/loop/action/runtime/tools/domains/search/eval/control-plane/memory/knowledge/server/web-ui）
examples/nonlinear_fit/    可运行入口（train.py / run_harness.py / run_benchmark.py / serve）
configs/                   基础配置（baselines/、examples/、priors/）
benchmarks/                实验与 Benchmark 产物（trials/summary/PNG/stress）
docs/                      UI 截图、实验报告、交接文档
tests/                     单元测试（230+）
```

## 复现与验证

```powershell
python -m unittest discover tests
python agent.py benchmark --output-dir benchmarks/fake-v21b
python agent.py compare-search --protocol benchmarks/protocol/nonlinear-search-v1.json --output-dir benchmarks/nonlinear-search-v1-v20000
python agent.py compare-search --domain synthetic --methods random_search,optuna_tpe,llm_direct,llm_program_reflection --seeds 7,17,29,43,61 --trial-budget 50 --parameter-count-max 100 --output-dir benchmarks/synthetic-compare-v1000
python agent.py compare-search --domain synthetic-large --llm-provider deepseek --seeds 7,17,29,43,61 --trial-budget 50 --parameter-count-max 100 --output-dir benchmarks/synthetic-real-v1000
python agent.py stress-runtime --concurrency 8 --requests 100 --failure-rate 0.1 --output-dir benchmarks/runtime-v2
```

所有实验产物（trials.jsonl / summary.json / summary.csv / PNG）都随仓库提交，任何结论都可以从原始数据复算。

## 文档

- 实验报告：[v1 搜索对照](docs/experiments/nonlinear-search-ablation-v1.md) · [v2 先验注入与 Benchmark 成熟化](docs/experiments/nonlinear-search-ablation-v2.md) · [v3 合成域 1000-trial 策略对比](docs/experiments/nonlinear-search-ablation-v3.md)
- 学习文档：[docs/learning/](docs/learning/)

## 设计借鉴与原创性

系统化借鉴了业界成熟方法，但实现均为本项目原创：

| 借鉴来源 | 借鉴点 | 本项目落地 |
| --- | --- | --- |
| Hermes（Nous Research） | `<tools>` 内函数签名 + 精确 JSON schema | planner prompt 内置"必须照填的 JSON 模板"与字段契约 |
| Claude Code / Claude | structured outputs、system prompt 格式契约、tool-result 错误回馈 | 强化 system prompt + Guard 拒绝后带错误重试（每轮限频 1 次） |
| 通用 Agent 工程 | plan → execute → observe → reflect 循环 | 完整主循环 + 历史压缩 + Reflection 事实提取 |

原创部分：**DomainPlugin 领域解耦**、**统一 Trial Protocol 与 bootstrap 统计**、**历史先验注入（-42 dB 候选）**、**SQLite 控制面**（幂等 / lease / SSE 重放）、**10-case Benchmark 指标体系**与**并发压测验收线**。
