import { classifyEvent, formatConsole, normalizeEvent } from "/ui/event_view_model.js";

const $ = (id) => document.getElementById(id);
const state = { events: [], selected: null, currentRunId: null, controller: null, approvalTimer: null, currentApproval: null, experiments: [], finalEvaluation: null, terminalStatus: null, runMode: null, runConfig: {}, graphMode: "multiagent", graphPreviousRole: null, coding: { candidates: 0, passed: 0, failed: 0, attempts: 0 } };
const titles = { multiagent: "Multi-Agent 运行", controlled: "受控模型搜索", agent: "Agent Planner", workflow: "Fixed Workflow", experiments: "实验策略对照", benchmark: "Benchmark 评估", memory: "Memory Inspector", reports: "报告与产物", diagnostics: "运行诊断" };
const CONTROLLED_DEFAULT_FIELDS = new Set(["feature_mode", "memory_depth", "mp_order_count", "hidden_units", "spline_knots", "epochs", "learning_rate", "optimizer"]);

function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])); }
function number(id) { return Number($(id).value); }
function setStatus(status, label) { $("statusDot").className = `status-light ${status}`; $("statusLabel").textContent = label; }
function artifactUrl(path) { return "/artifacts/" + String(path).replaceAll("\\", "/").split("/").map(encodeURIComponent).join("/"); }

function setView(view) {
  if (!titles[view]) view = "multiagent";
  document.querySelectorAll(".nav-item").forEach((item) => {
    const active = item.dataset.view === view;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
  });
  document.querySelectorAll(".control-view").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === view));
  document.querySelectorAll(".mode-node").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  if (WORKFLOW_GRAPHS[view]) renderWorkflowGraph(view);
  $("viewTitle").textContent = titles[view] || view;
  $("sidebar").classList.remove("open");
  if (view === "memory") loadMemory();
  history.replaceState(null, "", `?view=${view}`);
}

document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));
document.querySelectorAll(".mode-node").forEach((item) => item.addEventListener("click", () => setView(item.dataset.view || "multiagent")));
$("menuBtn").addEventListener("click", () => $("sidebar").classList.toggle("open"));
$("closeInspectorBtn").addEventListener("click", () => $("inspector").classList.remove("open"));
$("newRunBtn").addEventListener("click", clearEvents);

document.querySelectorAll("[data-event-view]").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll("[data-event-view]").forEach((item) => item.classList.toggle("active", item === button));
  $("timeline").classList.toggle("hidden", button.dataset.eventView !== "timeline");
  $("evBox").classList.toggle("hidden", button.dataset.eventView !== "console");
  $("rawBox").classList.toggle("hidden", button.dataset.eventView !== "raw");
}));

function clearEvents() {
  state.events = [];
  state.selected = null;
  state.experiments = [];
  state.finalEvaluation = null;
  state.terminalStatus = null;
  state.runMode = null;
  state.runConfig = {};
  state.coding = { candidates: 0, passed: 0, failed: 0, attempts: 0 };
  $("timeline").innerHTML = '<li class="timeline-empty">等待运行事件</li>';
  $("evBox").textContent = "Ready. Select a mode and start a run.";
  $("rawBox").textContent = "[]";
  $("evCount").textContent = "0";
  $("inspectorContent").classList.add("hidden");
  $("inspectorEmpty").classList.remove("hidden");
  $("resultPreview").classList.add("hidden");
  $("multiExperimentTable").classList.add("hidden");
  $("runSummary").classList.add("hidden");
  $("runSummary").innerHTML = "";
  $("resultLinks").innerHTML = "";
  resetAgentGraph();
}
$("clearBtn").addEventListener("click", clearEvents);

function renderTimelineEvent(event) {
  if (state.events.length === 1) $("timeline").innerHTML = "";
  const item = document.createElement("li");
  item.className = `timeline-event ${event.tone}`;
  item.dataset.eventId = event.id;
  item.innerHTML = `<time class="event-time">${esc(event.timeLabel)}</time><span class="event-dot"></span><span class="event-copy"><b>${esc(event.type)}</b><small>${esc(event.title)}</small></span><span class="event-role">${esc(event.role)}</span>`;
  item.addEventListener("click", () => inspectEvent(event, item));
  $("timeline").appendChild(item);
  $("timeline").scrollTop = $("timeline").scrollHeight;
}

function inspectEvent(event, item) {
  document.querySelectorAll(".timeline-event").forEach((node) => node.classList.remove("selected"));
  item?.classList.add("selected");
  state.selected = event.id;
  $("inspectorEmpty").classList.add("hidden");
  $("inspectorContent").classList.remove("hidden");
  $("inspector").classList.add("open");
  $("inspectKind").textContent = event.tone;
  $("inspectTitle").textContent = event.type;
  $("inspectMeta").textContent = `${event.timeLabel} / ${event.role}`;
  $("inspectFacts").innerHTML = Object.entries(event.facts).map(([key, value]) => `<dt>${esc(key)}</dt><dd>${esc(typeof value === "object" ? JSON.stringify(value) : value)}</dd>`).join("") || "<dt>summary</dt><dd>No normalized facts</dd>";
  $("inspectInputs").textContent = event.inputs.join("\n") || "none";
  $("inspectOutputs").textContent = event.outputs.join("\n") || "none";
  $("inspectRaw").textContent = JSON.stringify(event.raw, null, 2);
}

function updatePreview(raw) {
  const payload = raw.payload || {};
  const metrics = payload.output?.metrics || payload.metrics || {};
  const refArtifacts = (payload.output_refs || []).filter((item) => String(item).startsWith("artifact:")).map((item) => String(item).slice(9));
  const artifacts = payload.output?.artifacts || payload.artifacts || payload.final_evaluation?.artifacts || refArtifacts;
  const psd = artifacts.find((item) => String(item).replaceAll("\\", "/").toLowerCase().endsWith("psd.png"));
  if (!psd) return;
  const url = `${artifactUrl(psd)}?t=${Date.now()}`;
  $("psdPreview").src = url;
  $("psdLink").href = url;
  $("psdLink").classList.remove("hidden");
  $("psdFigure").classList.remove("hidden");
  $("chipNmse").textContent = metrics.nmse_db != null ? `${Number(metrics.nmse_db).toFixed(2)} dB` : "-";
  $("chipBase").textContent = metrics.baseline_nmse_db != null ? `${Number(metrics.baseline_nmse_db).toFixed(2)} dB` : "-";
  $("chipGain").textContent = metrics.nmse_improvement_db != null ? `${Number(metrics.nmse_improvement_db).toFixed(2)} dB` : "-";
  $("chipParams").textContent = metrics.parameter_count ?? "-";
  $("previewMeta").textContent = `source=${raw.tool || raw.event_type || "run"} | artifact=${psd}`;
  $("resultPreview").classList.remove("hidden");
}

function bestExperiment() {
  const all = [...state.experiments, ...(state.finalEvaluation ? [state.finalEvaluation] : [])];
  return all.filter((item) => item.status === "completed" && Number.isFinite(Number(item.metrics?.nmse_db))).sort((a, b) => Number(a.metrics.nmse_db) - Number(b.metrics.nmse_db))[0];
}

const WORKFLOW_GRAPHS = {
  multiagent: {
    nodes: [
      ["start", "START", "配置目标与预算", 440, 14, 120, 54, "start"],
      ["idea_plan", "Idea / Plan", "先验 · 假设 · 候选计划", 35, 130, 155, 112],
      ["plan_gate", "PlanGate", "Schema · 引用 · 预算", 235, 148, 100, 76, "gate"],
      ["coding", "Coding", "候选代码 · AST · Smoke", 380, 130, 155, 112],
      ["execution", "Execution", "Tool call · 训练 · Metrics", 610, 130, 155, 112],
      ["writing", "Writing", "证据归因 · PDF / HTML", 815, 130, 150, 112],
      ["result", "Result", "报告与可下载产物", 815, 300, 150, 82, "result"],
    ],
    edges: [
      ["start-idea", "control", "M500 68 C500 102 112 88 112 130"],
      ["idea-gate", "control", "M190 174 C208 174 217 186 235 186"],
      ["idea-plan-artifact", "artifact", "M112 242 C112 274 457 274 457 242"],
      ["gate-coding", "control", "M335 186 C352 186 363 174 380 174"],
      ["coding-execution", "control", "M535 174 C562 142 583 142 610 174"],
      ["coding-model-artifact", "artifact", "M457 242 C457 282 687 282 687 242"],
      ["execution-writing", "control", "M765 174 C785 174 795 174 815 174"],
      ["execution-evidence-artifact", "artifact", "M687 242 C687 270 890 270 890 242"],
      ["writing-result", "artifact", "M890 242 C890 266 890 276 890 300"],
      ["coding-plan", "feedback", "M457 130 C457 78 112 78 112 130"],
      ["execution-plan", "feedback", "M687 130 C687 52 112 52 112 130"],
      ["gate-plan", "feedback", "M285 148 C285 96 112 96 112 130"],
      ["writing-plan", "feedback", "M890 130 C890 26 112 26 112 130"],
    ],
  },
  controlled: {
    nodes: [["start","START","模型与参数白名单",440,14,120,54,"start"],["planner","Planner","受控候选配置",35,145,155,105],["guard","Whitelist Guard","字段 · 值域 · 参数量",235,145,155,105],["training","Train / Evaluate","固定训练与 NMSE",455,145,155,105],["reflection","Facts","结果事实与去重",675,145,135,105],["best","Best Result","对照与最优产物",840,145,130,105,"result"]],
    edges: [["start-planner","control","M500 68 C500 105 112 105 112 145"],["planner-guard","control","M190 197 C208 197 217 197 235 197"],["guard-training","control","M390 197 C415 197 430 197 455 197"],["training-facts","artifact","M532 250 C532 280 742 280 742 250"],["facts-planner","feedback","M742 145 C742 80 112 80 112 145"],["facts-best","control","M810 197 C822 197 828 197 840 197"]],
  },
  agent: {
    nodes: [["start","START","目标与动作预算",440,14,120,54,"start"],["planner","Planner","选择一个工具动作",35,145,145,105],["tool_call","Tool Call","Schema 与参数检查",225,145,145,105],["runtime","Runtime","执行注册工具",415,145,145,105],["observation","Observation","指标 · 错误 · 产物",605,145,145,105],["reflection","Reflection","仅提取事实",795,145,145,105]],
    edges: [["start-planner","control","M500 68 C500 105 107 105 107 145"],["planner-tool","control","M180 197 C198 197 207 197 225 197"],["tool-runtime","control","M370 197 C388 197 397 197 415 197"],["runtime-observation","artifact","M487 250 C487 280 677 280 677 250"],["observation-reflection","control","M750 197 C768 197 777 197 795 197"],["reflection-planner","feedback","M867 145 C867 70 107 70 107 145"]],
  },
  workflow: {
    nodes: [["start","START","确定性请求",440,14,120,54,"start"],["generate_config","Generate Config","解析并冻结配置",35,145,155,105],["run_training","Run Training","固定训练入口",245,145,155,105],["verify_artifacts","Verify Artifacts","指标与文件复核",455,145,155,105],["write_report","Write Report","摘要与证据报告",665,145,155,105],["result","Result","产物下载",855,145,115,105,"result"]],
    edges: [["start-config","control","M500 68 C500 105 112 105 112 145"],["config-training","artifact","M190 197 C210 197 225 197 245 197"],["training-verify","artifact","M400 197 C420 197 435 197 455 197"],["verify-report","control","M610 197 C630 197 645 197 665 197"],["report-result","artifact","M820 197 C835 197 840 197 855 197"]],
  },
};

function renderWorkflowGraph(mode) {
  const graph = WORKFLOW_GRAPHS[mode] || WORKFLOW_GRAPHS.multiagent;
  state.graphMode = mode;
  state.graphPreviousRole = null;
  const edges = graph.edges.map(([id, type, d]) => `<path class="edge-${type}" data-wire="${id}" data-edge-type="${type}" d="${d}"/>`).join("");
  const nodes = graph.nodes.map(([id, label, detail, x, y, width, height, kind = "agent"]) => `<button class="agent-node workflow-node pending ${kind}" data-agent-node="${id}" style="left:${x}px;top:${y}px;width:${width}px;height:${height}px"><i class="node-port input port-control" title="Control input"></i><i class="node-port output port-control" title="Control output"></i><i class="node-port artifact port-artifact" title="Artifact output"></i><i class="node-port feedback port-feedback" title="Feedback / replan"></i><small class="node-runtime">waiting</small><b>${esc(label)}</b><p>${esc(detail)}</p><footer><span class="node-state">PENDING</span><span class="node-cost">${id === "execution" || id === "runtime" || id === "run_training" ? "runtime" : "$0.0000"}</span></footer></button>`).join("");
  $("graphStage").innerHTML = `<svg class="graph-wires" viewBox="0 0 1000 410" aria-hidden="true">${edges}</svg>${nodes}`;
  $("nodeArtifactPanel").classList.add("hidden");
  bindGraphNodeClicks();
}

function bindGraphNodeClicks() {
  document.querySelectorAll(".workflow-node").forEach((node) => node.addEventListener("click", () => {
    if (node.dataset.agentNode === "start") { setView(state.graphMode); return; }
    if (["writing", "result", "write_report", "best"].includes(node.dataset.agentNode) && $("writingArtifacts").children.length) $("nodeArtifactPanel").classList.remove("hidden");
    const found = [...state.events].reverse().find((event) => (event.raw.payload || {}).role === node.dataset.agentNode);
    if (found) inspectEvent(found, null);
  }));
}

function resetAgentGraph() {
  document.querySelectorAll(".agent-node").forEach((node) => {
    node.classList.remove("running", "complete", "failed", "rejected", "review");
    node.classList.add("pending");
    node.querySelector(".node-state").textContent = "PENDING";
    node.querySelector(".node-runtime").textContent = "waiting";
    node.querySelector(".node-cost").textContent = node.dataset.agentNode === "execution" ? "runtime" : "$0.0000";
  });
  document.querySelectorAll("[data-wire]").forEach((wire) => wire.classList.remove("active", "complete"));
  $("writingArtifacts").innerHTML = "";
  $("nodeArtifactPanel").classList.add("hidden");
  state.graphPreviousRole = null;
}

function setGraphRunning(role) {
  document.querySelectorAll(".agent-node").forEach((node) => node.classList.remove("running"));
  const node = document.querySelector(`[data-agent-node="${role}"]`);
  if (node) {
    node.classList.remove("pending");
    node.classList.add("running");
    node.querySelector(".node-state").textContent = "RUNNING";
  }
}

function setEdgeState(id, value) {
  const edge = document.querySelector(`[data-wire="${id}"]`);
  if (!edge) return;
  edge.classList.remove("active", "complete", "failed");
  if (value) edge.classList.add(value);
}

function routeGraphEvent(payload) {
  const role = payload.role;
  const status = payload.status;
  const failed = ["failed", "error", "budget_exceeded", "rejected", "invalid_plan"].includes(status);
  if (state.graphMode !== "multiagent") return;
  if (role === "idea_plan") {
    if (state.graphPreviousRole === "execution") {
      setEdgeState("execution-writing", null);
      setEdgeState("execution-evidence-artifact", "complete");
      setEdgeState("execution-plan", "active");
    }
    else setEdgeState("start-idea", "complete");
    setEdgeState("idea-gate", failed ? "failed" : "active");
    setEdgeState("idea-plan-artifact", failed ? "failed" : "active");
    if (!failed) setGraphRunning("plan_gate");
  } else if (role === "plan_gate") {
    setEdgeState("idea-gate", failed ? "failed" : "complete");
    setEdgeState("idea-plan-artifact", failed ? "failed" : "complete");
    if (failed) { setEdgeState("gate-plan", "active"); setGraphRunning("idea_plan"); }
    else { setEdgeState("gate-coding", "active"); setGraphRunning("coding"); }
  } else if (role === "coding") {
    setEdgeState("gate-coding", failed ? "failed" : "complete");
    if (failed) { setEdgeState("coding-plan", "active"); setGraphRunning("idea_plan"); }
    else { setEdgeState("coding-execution", "active"); setEdgeState("coding-model-artifact", "active"); setGraphRunning("execution"); }
  } else if (role === "execution" || role === "final_evaluation") {
    setEdgeState("coding-execution", failed ? "failed" : "complete");
    setEdgeState("coding-model-artifact", failed ? "failed" : "complete");
    if (failed || payload.next_node === "idea_plan") {
      setEdgeState("execution-writing", null);
      setEdgeState("execution-evidence-artifact", failed ? "failed" : "complete");
      setEdgeState("execution-plan", "active");
      setGraphRunning("idea_plan");
    } else {
      setEdgeState("execution-writing", "active");
      setEdgeState("execution-evidence-artifact", "active");
      if (payload.next_node === "final_evaluation") setGraphRunning("execution");
      else setGraphRunning("writing");
    }
  } else if (role === "writing") {
    setEdgeState("execution-writing", failed ? "failed" : "complete");
    setEdgeState("execution-evidence-artifact", failed ? "failed" : "complete");
    setEdgeState("writing-result", failed ? "failed" : "active");
    if (payload.next_node === "idea_plan") {
      setEdgeState("writing-plan", "active");
      setGraphRunning("idea_plan");
    }
  }
  state.graphPreviousRole = role;
}

function updateAgentGraph(raw) {
  const payload = raw.payload || {};
  routeOperationalEvent(raw);
  if (raw.event_type === "multi_agent_terminal") {
    document.querySelectorAll("[data-wire].active").forEach((wire) => { wire.classList.remove("active"); wire.classList.add("complete"); });
    const resultNode = document.querySelector('[data-agent-node="result"]');
    if (resultNode && ["completed", "succeeded"].includes(raw.status)) {
      resultNode.classList.remove("pending", "running"); resultNode.classList.add("complete");
      resultNode.querySelector(".node-state").textContent = "READY";
    }
    return;
  }
  if (raw.event_type !== "multi_agent_role") return;
  const node = document.querySelector(`[data-agent-node="${payload.role}"]`);
  routeGraphEvent(payload);
  if (!node) return;
  const usage = payload.model_usage || [];
  const latency_ms = Number(payload.latency_ms || usage.reduce((sum, item) => sum + Number(item.latency_ms || 0), 0));
  const cost_usd = Number(payload.cost_usd || usage.reduce((sum, item) => sum + Number(item.cost_usd || 0), 0));
  const failed = ["failed", "error", "budget_exceeded", "rejected", "invalid_plan"].includes(payload.status);
  node.classList.remove("pending", "running", "complete", "failed", "rejected", "review");
  node.classList.add(failed ? payload.status : "complete");
  node.querySelector(".node-state").textContent = String(payload.status || "complete").toUpperCase();
  node.querySelector(".node-runtime").textContent = latency_ms ? `${(latency_ms / 1000).toFixed(2)}s` : "local runtime";
  node.querySelector(".node-cost").textContent = cost_usd ? `$${cost_usd.toFixed(4)}` : (payload.role === "execution" ? "tool runtime" : "$0.0000");
  const outputs = payload.output_refs || [];
  if (payload.role === "writing") {
    const reports = outputs.filter((item) => String(item).startsWith("report:"));
    $("writingArtifacts").innerHTML = reports.map((ref) => { const path = String(ref).slice(7); return `<a href="${artifactUrl(path)}" target="_blank"><b>${esc(path.toLowerCase().endsWith(".pdf") ? "PDF" : "REPORT")}</b><span>PDF path: ${esc(path)}</span></a>`; }).join("");
    $("nodeArtifactPanel").classList.toggle("hidden", reports.length === 0);
  }
}

function routeOperationalEvent(raw) {
  if (raw.event_type === "multi_agent_role" || state.graphMode === "multiagent") return;
  const type = String(raw.event_type || "");
  const payload = raw.payload || {};
  const tool = String(raw.tool || payload.tool || payload.tool_name || "");
  const complete = (node, edge) => { const card = document.querySelector(`[data-agent-node="${node}"]`); card?.classList.remove("pending", "running"); card?.classList.add("complete"); if (card) card.querySelector(".node-state").textContent = "DONE"; if (edge) setEdgeState(edge, "complete"); };
  if (state.graphMode === "controlled") {
    if (type === "plan_generated") { complete("planner", "start-planner"); setGraphRunning("guard"); }
    else if (type === "experiment_rejected") { complete("guard", "planner-guard"); setEdgeState("facts-planner", "active"); }
    else if (type === "experiment_start") { complete("guard", "planner-guard"); setGraphRunning("training"); }
    else if (type === "experiment_end") { complete("training", "guard-training"); setEdgeState("training-facts", "active"); setGraphRunning("reflection"); }
    else if (["complete", "loop_complete"].includes(type)) { complete("reflection", "training-facts"); setEdgeState("facts-best", "complete"); complete("best"); }
  } else if (state.graphMode === "agent") {
    if (type.includes("plan")) { complete("planner", "start-planner"); setGraphRunning("tool_call"); }
    else if (type === "tool_start") { complete("tool_call", "planner-tool"); setGraphRunning("runtime"); }
    else if (type === "tool_end") { complete("runtime", "tool-runtime"); setEdgeState("runtime-observation", "active"); setGraphRunning("observation"); }
    else if (type.includes("reflection")) { complete("observation", "runtime-observation"); setGraphRunning("reflection"); }
    else if (["complete", "loop_complete"].includes(type)) complete("reflection", "observation-reflection");
  } else if (state.graphMode === "workflow") {
    const order = ["generate_config", "run_training", "verify_artifacts", "write_report"];
    const index = order.indexOf(tool);
    if (index >= 0 && type === "tool_start") setGraphRunning(tool);
    if (index >= 0 && type === "tool_end") {
      complete(tool, index === 0 ? "start-config" : ["config-training", "training-verify", "verify-report"][index - 1]);
      if (index + 1 < order.length) setGraphRunning(order[index + 1]); else { setEdgeState("report-result", "complete"); complete("result"); }
    }
  }
}

const REVIEW_GUIDANCE = {
  idea_plan: {
    reason: "检查实验假设、候选方案、预算和引用后再进入代码生成。 / Review hypotheses, candidates, budgets and citations before code generation.",
    risk: "批准后可能创建候选模型目录、plugin.py 与 manifest.json，并消耗后续 Coding API 额度。 / Approval may create candidate model files and consume Coding API budget.",
  },
  coding: {
    reason: "检查生成代码、改动文件、Gate 结果与修复记录后再执行。 / Review generated code scope, changed files, gate results and repairs before execution.",
    risk: "批准后候选代码会在隔离工作区运行训练；仍可能超时、占用算力或生成错误产物。 / Approval runs candidate code in an isolated worktree; it may time out, consume compute or produce invalid artifacts.",
  },
  execution: {
    reason: "确认训练配置、目标、历史最优和待执行工具。 / Confirm training config, goal, historical best and registered tools.",
    risk: "批准后会真实训练并写入 metrics、模型和 PSD，产生时间与计算成本。 / Approval starts real training and writes metrics, model and PSD artifacts with time and compute cost.",
  },
  writing: {
    reason: "检查指标归因、成本和最终报告产物。 / Review metric attribution, cost and final report artifacts.",
    risk: "批准后会发布 PDF/HTML；错误归因或未支持的性能数字会影响报告可信度。 / Approval publishes PDF/HTML; unsupported claims or wrong attribution reduce report fidelity.",
  },
};

async function pollApprovals() {
  if (!state.currentRunId || state.runConfig.approval_mode !== "review") return;
  try {
    const data = await fetch(`/approvals/${encodeURIComponent(state.currentRunId)}`).then((response) => response.json());
    const pending = (data.pending || [])[0];
    if (!pending || state.currentApproval?.approval_id === pending.approval_id) return;
    state.currentApproval = pending;
    const payload = pending.payload || {};
    const guidance = REVIEW_GUIDANCE[pending.role] || {
      reason: "检查输入、输出和继续执行的必要性。 / Review inputs, outputs and whether execution should continue.",
      risk: "确认目标、预算、权限和证据约束。 / Confirm goal, budget, permission and evidence constraints.",
    };
    $("approvalTitle").textContent = `${pending.role} · ${pending.phase}`;
    $("approvalRole").textContent = pending.role;
    $("approvalReason").textContent = `${guidance.reason}${payload.reason ? `\nAgent context: ${payload.reason}` : ""}`;
    $("approvalRisk").textContent = `${guidance.risk}${payload.risk ? `\nRun-specific risk: ${payload.risk}` : ""}`;
    $("approvalPayload").textContent = JSON.stringify(payload, null, 2);
    $("approvalFeedback").value = "";
    const node = document.querySelector(`[data-agent-node="${pending.role}"]`);
    node?.classList.remove("pending", "running", "complete", "failed", "rejected");
    node?.classList.add("review");
    if (node) node.querySelector(".node-state").textContent = "REVIEW";
    $("approvalDialog").showModal();
  } catch {}
}

async function decideApproval(approved) {
  const pending = state.currentApproval;
  if (!pending || !state.currentRunId) return;
  const reason = $("approvalFeedback").value.trim();
  if (!approved && !reason) { $("approvalFeedback").focus(); return; }
  await fetch(`/approvals/${encodeURIComponent(state.currentRunId)}/${encodeURIComponent(pending.approval_id)}/decision`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approved, reason }),
  });
  document.querySelector(`[data-agent-node="${pending.role}"]`)?.classList.remove("review");
  state.currentApproval = null;
  $("approvalDialog").close();
}

$("approvalApprove").addEventListener("click", () => decideApproval(true));
$("approvalReject").addEventListener("click", () => decideApproval(false));

function normalizeControlledResult(payload, eventType) {
  const config = payload.config || {};
  const metrics = payload.metrics || {};
  const rawStatus = eventType === "experiment_rejected" ? "rejected" : (metrics.run_status || "completed");
  return {
    experiment_id: payload.id || "unknown",
    evaluation_kind: "controlled-search",
    model_type: config.model_type || "baseline default",
    status: rawStatus === "succeeded" ? "completed" : rawStatus,
    metrics,
    config,
    error: payload.error || metrics.error || "",
  };
}

function upsertExperiment(row) {
  const key = `${row.evaluation_kind || "search"}:${row.experiment_id || "unknown"}`;
  const index = state.experiments.findIndex((item) => `${item.evaluation_kind || "search"}:${item.experiment_id || "unknown"}` === key);
  if (index >= 0) state.experiments[index] = row; else state.experiments.push(row);
}

function collectRunResult(raw) {
  const payload = raw.payload || {};
  if (raw.event_type === "multi_agent_role" && payload.role === "execution" && Array.isArray(payload.experiments)) {
    payload.experiments.forEach(upsertExperiment);
  }
  if (raw.event_type === "multi_agent_role" && payload.role === "final_evaluation" && payload.final_evaluation) state.finalEvaluation = payload.final_evaluation;
  if (raw.event_type === "multi_agent_role" && payload.role === "coding" && payload.coding_summary) {
    state.coding.candidates += Number(payload.coding_summary.candidate_count || 0);
    state.coding.passed += Number(payload.coding_summary.passed_count || 0);
    state.coding.failed += Number(payload.coding_summary.failed_count || 0);
    state.coding.attempts += Number(payload.coding_summary.repair_attempts || 0);
  }
  if (state.runMode === "controlled" && ["experiment_end", "experiment_rejected"].includes(raw.event_type)) {
    upsertExperiment(normalizeControlledResult(payload, raw.event_type));
  }
}

function renderRunSummary() {
  const rows = [...state.experiments, ...(state.finalEvaluation ? [state.finalEvaluation] : [])];
  const completed = rows.filter((item) => item.status === "completed");
  const searchCompleted = state.experiments.filter((item) => item.status === "completed");
  const rejected = rows.filter((item) => item.status === "rejected").length;
  const failed = rows.filter((item) => !["completed", "rejected"].includes(item.status)).length;
  const searchFailed = state.experiments.filter((item) => item.status !== "completed").length;
  const threshold = Number(state.runConfig.nmse_threshold_db);
  const hits = completed.filter((item) => Number.isFinite(Number(item.metrics?.nmse_db)) && Number(item.metrics.nmse_db) <= threshold).length;
  const searchHits = searchCompleted.filter((item) => Number.isFinite(Number(item.metrics?.nmse_db)) && Number(item.metrics.nmse_db) <= threshold).length;
  const cards = state.runMode === "multiagent"
    ? [["generated_candidates", state.coding.candidates], ["coding_gate_pass", `${state.coding.passed}/${state.coding.candidates}`], ["search_completed", `${searchCompleted.length}/${state.experiments.length}`], ["search_failed", searchFailed], ["search_target_hits", searchHits], ["repair_attempts", state.coding.attempts], ["final_evaluation", state.finalEvaluation?.status || "pending"]]
    : [["experiments_total", rows.length], ["completed", completed.length], ["rejected_by_guard", rejected], ["runtime_failed", failed], ["target_hits", hits], ["target_nmse_db", Number.isFinite(threshold) ? threshold : "-"]];
  $("runSummary").innerHTML = cards.map(([name, value]) => `<div><small>${esc(name)}</small><b>${esc(value)}</b></div>`).join("");
  $("runSummary").classList.remove("hidden");
}

function renderRunResults(raw) {
  const payload = raw.payload || {};
  if (!state.experiments.length && !state.finalEvaluation && raw.event_type !== "multi_agent_terminal") return;
  const rows = [...state.experiments, ...(state.finalEvaluation ? [state.finalEvaluation] : [])];
  if (rows.length) {
    $("multiExperimentTable").innerHTML = `<table class="r-table"><tr><th>Experiment</th><th>Stage</th><th>Model</th><th>Status</th><th>NMSE</th><th>Gain vs input</th><th>Params</th></tr>${rows.map((item) => `<tr><td>${esc(item.experiment_id)}</td><td>${esc(item.evaluation_kind)}</td><td>${esc(item.model_type)}</td><td>${esc(item.status)}</td><td>${item.metrics?.nmse_db == null ? "-" : `${Number(item.metrics.nmse_db).toFixed(3)} dB`}</td><td>${item.metrics?.nmse_improvement_db == null ? "-" : `${Number(item.metrics.nmse_improvement_db).toFixed(2)} dB`}</td><td>${esc(item.metrics?.parameter_count ?? "-")}</td></tr>`).join("")}</table>`;
    $("multiExperimentTable").classList.remove("hidden");
  }
  const best = bestExperiment();
  if (best) {
    $("chipNmse").textContent = `${Number(best.metrics.nmse_db).toFixed(2)} dB`;
    $("chipBase").textContent = best.metrics.baseline_nmse_db == null ? "-" : `${Number(best.metrics.baseline_nmse_db).toFixed(2)} dB`;
    $("chipGain").textContent = best.metrics.nmse_improvement_db == null ? "-" : `${Number(best.metrics.nmse_improvement_db).toFixed(2)} dB`;
    $("chipParams").textContent = best.metrics.parameter_count ?? "-";
    $("resultTitle").textContent = state.runMode === "controlled" ? "受控搜索总体结果" : (state.finalEvaluation ? "Multi-Agent 终评与总体结果" : "Multi-Agent 总体结果");
  }
  renderRunSummary();
  const paths = Object.entries(payload).filter(([key, value]) => key.endsWith("_path") && typeof value === "string");
  if (paths.length) $("resultLinks").innerHTML = paths.map(([key, path]) => `<a href="${artifactUrl(path)}" target="_blank">${esc(key)}: ${esc(path)}</a>`).join("");
  $("resultPreview").classList.remove("hidden");
}

function appendEvent(raw) {
  const event = normalizeEvent(raw, state.events.length);
  state.events.push(event);
  const payload = raw.payload || {};
  if (event.type === "multi_agent_terminal") state.terminalStatus = payload.status || raw.status || "error";
  else if (["complete", "loop_complete", "benchmark_complete", "agent_task_benchmark_complete", "compare_complete"].includes(event.type)) state.terminalStatus = "completed";
  else if (event.type === "cancelled") state.terminalStatus = "cancelled";
  else if (event.type === "error") state.terminalStatus = "error";
  renderTimelineEvent(event);
  const line = formatConsole(raw);
  const span = document.createElement("span");
  span.className = `ev-${classifyEvent(raw)}`;
  span.textContent = `${line}\n`;
  if (state.events.length === 1) $("evBox").textContent = "";
  $("evBox").appendChild(span);
  $("evBox").scrollTop = $("evBox").scrollHeight;
  $("rawBox").textContent = JSON.stringify(state.events.map((item) => item.raw), null, 2);
  $("evCount").textContent = state.events.length;
  collectRunResult(raw);
  renderRunResults(raw);
  updatePreview(raw);
  updateAgentGraph(raw);
}

function setRunning(runId, running) {
  state.currentRunId = running ? runId : null;
  $("currentRunId").textContent = running ? runId : "-";
  $("stopBtn").disabled = !running;
  $("streamStatus").textContent = running ? "SSE connected" : "SSE disconnected";
  setStatus(running ? "running" : "done", running ? "运行中" : "已完成");
}

function setRunControlsDisabled(disabled) {
  ["maBtn", "csBtn", "agBtn", "wfBtn", "bmBtn", "agentTaskBtn", "cmpBtn"].forEach((id) => { $(id).disabled = disabled; });
}

function applyTerminalStatus() {
  const terminal = state.terminalStatus;
  if (["completed", "succeeded", "stopped"].includes(terminal)) setStatus("done", "已完成");
  else if (terminal === "cancelled") setStatus("idle", "已取消");
  else if (["error", "failed", "budget_exceeded", "invalid_plan"].includes(terminal)) setStatus("error", terminal === "budget_exceeded" ? "预算耗尽" : "失败");
  else setStatus("idle", "流已结束");
}

async function streamRun(url, body, button, runId) {
  if (state.controller) return;
  clearEvents();
  state.runMode = url.startsWith("/multi-agent/") ? "multiagent" : (url.startsWith("/controlled-search/") ? "controlled" : "other");
  state.runConfig = { ...body };
  setRunControlsDisabled(true);
  const original = button.innerHTML;
  button.textContent = "运行中...";
  const controller = new AbortController();
  state.controller = controller;
  setRunning(runId, true);
  if (state.runMode === "multiagent") setGraphRunning("idea_plan");
  if (body.approval_mode === "review") state.approvalTimer = setInterval(pollApprovals, 700);
  try {
    const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const consume = (final = false) => {
      buffer = buffer.replaceAll("\r\n", "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      if (final && buffer.trim()) { blocks.push(buffer); buffer = ""; }
      blocks.forEach((block) => {
        const data = block.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
        if (!data) return;
        try { appendEvent(JSON.parse(data)); } catch { appendEvent({ event_type: "error", error: `Invalid SSE payload: ${data}` }); }
      });
    };
    while (true) {
      const { value, done } = await reader.read();
      if (done) { buffer += decoder.decode(); consume(true); break; }
      buffer += decoder.decode(value, { stream: true });
      consume();
    }
    state.currentRunId = null;
    applyTerminalStatus();
  } catch (error) {
    if (error.name !== "AbortError") { appendEvent({ event_type: "error", error: String(error) }); setStatus("error", "失败"); }
    else setStatus("idle", "已停止");
  } finally {
    if (state.approvalTimer) clearInterval(state.approvalTimer);
    state.approvalTimer = null;
    state.currentApproval = null;
    if ($("approvalDialog").open) $("approvalDialog").close();
    setRunControlsDisabled(false);
    button.innerHTML = original;
    $("stopBtn").disabled = true;
    $("streamStatus").textContent = "SSE disconnected";
    if (state.controller === controller) state.controller = null;
    state.currentRunId = null;
  }
}

$("stopBtn").addEventListener("click", async () => {
  if (!state.currentRunId) return;
  await fetch(`/cancel/${encodeURIComponent(state.currentRunId)}`, { method: "POST" }).catch(() => {});
  state.controller?.abort();
});

$("maBtn").addEventListener("click", () => {
  const runId = `ui-multi-${Date.now()}`;
  streamRun(`/multi-agent/${runId}/events`, { provider: "deepseek", approval_mode: $("approvalMode").value, goal: $("maGoal").value, idea_plan_model: $("maPlanModel").value, coding_model: $("maCodeModel").value, writing_model: $("maWriteModel").value, max_replans: number("maReplans"), nmse_threshold_db: number("maThreshold"), token_budget: number("maTokens"), cost_budget_usd: number("maCost"), rounds: number("maRounds"), experiments_per_round: number("maExperiments"), final_evaluation: $("maFinalEvaluation").checked, knowledge_context_enabled: $("knowledgeContextEnabled").checked, knowledge_top_k: number("knowledgeTopK"), domain: "nonlinear-modeling", dataset_hash: "default", model_family: "mixed" }, $("maBtn"), runId);
});
$("csBtn").addEventListener("click", () => {
  const runId = `ui-controlled-${Date.now()}`;
  const allowedModels = [...document.querySelectorAll(".cs-model:checked")].map((item) => item.value);
  const enabledFields = [...document.querySelectorAll(".cs-tune:checked")].map((item) => item.value);
  if (!allowedModels.length) { appendEvent({ event_type: "error", error: "Select at least one allowed model." }); return; }
  streamRun(`/controlled-search/${runId}/events`, { provider: $("csProv").value, goal: $("csGoal").value, max_rounds: number("csRnd"), max_experiments: number("csExp"), parameter_count_max: number("csPm"), nmse_threshold_db: number("csThr"), timeout_seconds: number("csTo"), domain: "nonlinear", allowed_models: allowedModels, enabled_fields: enabledFields }, $("csBtn"), runId);
});
$("agBtn").addEventListener("click", () => {
  const runId = `ui-agent-${Date.now()}`;
  const enabled = [...document.querySelectorAll(".tune-f:checked")].map((item) => item.value);
  streamRun(`/agent/${runId}/events`, { provider: $("agProv").value, goal: $("agGoal").value, max_rounds: number("agRnd"), max_experiments: number("agExp"), parameter_count_max: number("agPm"), nmse_threshold_db: number("agThr"), timeout_seconds: number("agTo"), artifact_dir: null, domain: $("agDom").value, enabled_fields: enabled, data_file: $("agData").value }, $("agBtn"), runId);
});
$("wfBtn").addEventListener("click", () => { const runId = $("wfSid").value.trim() || "ui-demo-001"; streamRun(`/runs/${encodeURIComponent(runId)}/events`, { goal: $("wfGoal").value, epochs: number("wfEp"), nmse_threshold_db: number("wfThr"), timeout_seconds: number("wfTo") }, $("wfBtn"), runId); });
$("bmBtn").addEventListener("click", () => streamRun("/benchmark/events", { timeout_seconds: number("bmTo"), nmse_threshold_db: number("bmThr") }, $("bmBtn"), "benchmark"));
$("agentTaskBtn").addEventListener("click", () => streamRun("/agent-benchmark/events", { attempts: 1 }, $("agentTaskBtn"), "agent-benchmark"));
$("cmpBtn").addEventListener("click", () => { const count = number("cmpSeeds"); const seeds = Array.from({ length: count }, (_, index) => [7, 17, 29, 43, 61][index] || 7 + index * 10); streamRun("/compare/events", { domain: $("cmpDom").value, workspace: ".", llm_provider: "deepseek", timeout_seconds: number("cmpTo"), parameter_count_max: number("cmpPm"), nmse_threshold_db: number("cmpThr"), seeds, trial_budget: number("cmpBudget"), methods: ["random_search", "optuna_tpe", "llm_direct", "llm_program_reflection"], plan: $("cmpPlan").value }, $("cmpBtn"), "comparison"); });

$("agProv").addEventListener("change", () => { $("noteFake").classList.toggle("hidden", $("agProv").value !== "fake"); $("noteDp").classList.toggle("hidden", $("agProv").value !== "deepseek"); });
async function loadTuneFields(domain) { try { const data = await fetch(`/domains/${encodeURIComponent(domain)}/fields`).then((response) => response.json()); $("agTune").innerHTML = (data.fields || []).map((field) => `<label title="${esc((field.values || []).join(", "))}"><input type="checkbox" class="tune-f" value="${esc(field.name)}" checked>${esc(field.name)}</label>`).join(""); } catch { $("agTune").innerHTML = '<span class="ev-failure">failed to load fields</span>'; } }
async function loadControlledFields() { try { const data = await fetch("/domains/nonlinear/fields").then((response) => response.json()); const fields = data.fields || []; const modelField = fields.find((field) => field.name === "model_type"); $("csModels").innerHTML = (modelField?.values || []).map((value) => `<label><input type="checkbox" class="cs-model" value="${esc(value)}" checked>${esc(value)}</label>`).join(""); $("csTune").innerHTML = fields.filter((field) => field.name !== "model_type").map((field) => `<label title="${esc((field.values || []).join(", "))}"><input type="checkbox" class="cs-tune" value="${esc(field.name)}" ${CONTROLLED_DEFAULT_FIELDS.has(field.name) ? "checked" : ""}>${esc(field.name)}</label>`).join(""); } catch { $("csModels").innerHTML = '<span class="ev-failure">failed to load models</span>'; $("csTune").innerHTML = '<span class="ev-failure">failed to load fields</span>'; } }
async function loadMatFiles() { try { const data = await fetch("/data/mat-files").then((response) => response.json()); $("agData").innerHTML = '<option value="">auto</option>' + (data.files || []).map((file) => `<option value="${esc(file)}">${esc(file)}</option>`).join(""); } catch {} }
$("agDom").addEventListener("change", () => loadTuneFields($("agDom").value));

function renderMemory(data) {
  const items = data.items || [];
  if (!items.length) { $("memBox").textContent = "No typed memory items yet."; return; }
  $("memBox").innerHTML = `<div class="table-wrap"><table class="r-table"><tr><th>ID</th><th>Kind</th><th>Namespace</th><th>Fact</th><th>Evidence</th><th>Run</th><th>Role</th></tr>${items.map((item) => `<tr><td>${esc(item.memory_id)}</td><td>${esc(item.kind)}</td><td>${esc((item.namespace || []).join("/"))}</td><td>${esc(item.fact)}</td><td>${esc((item.evidence_refs || []).join(", "))}</td><td>${esc(item.run_id)}</td><td>${esc(item.created_by_role)}</td></tr>`).join("")}</table></div>`;
}
async function loadMemory() { $("memBox").textContent = "loading..."; try { renderMemory(await fetch("/memory").then((response) => response.json())); } catch (error) { $("memBox").textContent = String(error); } }
$("memRefresh").addEventListener("click", loadMemory);

async function previewKnowledgeSources() {
  const box = $("knowledgeSources");
  box.classList.remove("hidden");
  box.textContent = "loading...";
  try {
    const data = await fetch("/knowledge/sources").then((response) => response.json());
    box.innerHTML = `<b>${esc(data.root)}</b><br>${(data.sources || []).map((item) => `${esc(item.name)} · ${esc(item.chunk_count)} chunks`).join("<br>") || "No sources"}`;
  } catch (error) { box.textContent = String(error); }
}
$("knowledgePreviewBtn").addEventListener("click", previewKnowledgeSources);

function metricCell(name, value) { return `<div><small>${esc(name)}</small><b>${esc(value == null ? "-" : value)}</b></div>`; }
function renderBenchmarkSummary(data) {
  const summary = data.summary || data; const results = data.results || [];
  const keys = ["case_count", "target_hit_rate", "planner_success_rate", "rejected_rate", "runtime_failure_rate", "average_experiments_used", "best_nmse_db", "estimated_cost_usd"];
  $("bmSummaryWrap").innerHTML = keys.map((key) => { let value = summary[key]; if (typeof value === "number" && key.includes("rate")) value = `${(value * 100).toFixed(1)}%`; return metricCell(key, value); }).join("");
  $("bmTableWrap").innerHTML = results.length ? `<table class="r-table"><tr><th>Case</th><th>Hit</th><th>Best NMSE</th><th>OK</th><th>Failed</th><th>Rejected</th><th>Planner OK</th></tr>${results.map((row) => `<tr><td>${esc(row.case_id)}</td><td>${row.target_hit ? "PASS" : "MISS"}</td><td>${esc(row.best_nmse_db)}</td><td>${esc(row.succeeded_count)}</td><td>${esc(row.failed_count)}</td><td>${esc(row.rejected_count)}</td><td>${row.planner_success_rate == null ? "-" : `${Math.round(row.planner_success_rate * 100)}%`}</td></tr>`).join("")}</table>` : "";
  $("bmResults").classList.remove("hidden");
}
async function loadBenchmarkSummary(showError = true) { try { const data = await fetch("/benchmark/summary").then((response) => response.json()); if (!data.error) renderBenchmarkSummary(data); } catch (error) { if (showError) appendEvent({ event_type: "error", error: String(error) }); } }
$("bmLoadBtn").addEventListener("click", () => loadBenchmarkSummary(true));

function renderCompareSummary(summary) {
  const methods = summary.per_method || {}; const metric = Object.values(methods)[0]?.metric_name || "nmse_db";
  const reference = methods.random_search?.[`best_${metric}_mean`];
  $("cmpTableWrap").innerHTML = `<table class="r-table"><tr><th>Method</th><th>Role</th><th>Best mean</th><th>delta vs random_search</th><th>95% CI</th><th>Hit Rate</th><th>Rejected</th><th>Failed</th></tr>${Object.entries(methods).map(([name, item]) => { const best = item[`best_${metric}_mean`]; const delta = Number.isFinite(Number(best)) && Number.isFinite(Number(reference)) ? Number(best) - Number(reference) : null; return `<tr><td>${esc(name)}</td><td>${name === "random_search" ? "reference" : "candidate"}</td><td>${esc(best)}</td><td>${delta == null ? "-" : delta.toPrecision(4)}</td><td>[${esc(item[`best_${metric}_ci_95_low`])}, ${esc(item[`best_${metric}_ci_95_high`])}]</td><td>${esc(item.target_hit_rate_mean)}</td><td>${esc(item.rejected_rate_mean)}</td><td>${esc(item.runtime_failure_rate_mean)}</td></tr>`; }).join("")}</table>`;
  const paired = summary.paired_comparisons || {};
  $("cmpPaired").innerHTML = Object.entries(paired).length ? `<div class="paired-grid">${Object.entries(paired).map(([name, item]) => { const deltaKey = Object.keys(item).find((key) => key.endsWith("_delta_mean")); const metricName = deltaKey?.slice(0, -11) || metric; return `<div><small>${esc(name)}</small><b>${esc(item[deltaKey])}</b><span>${esc(metricName)} treatment - control · n=${esc(item.paired_seed_count)} · ${item.significant ? "significant" : "not significant"}</span></div>`; }).join("")}</div>` : '<p class="field-note">当前结果没有可用的同 seed 配对统计。</p>';
  $("cmpResults").classList.remove("hidden");
}
async function loadCompareSummary(showError = true) { try { const data = await fetch("/compare/summary").then((response) => response.json()); if (!data.error) renderCompareSummary(data); } catch (error) { if (showError) appendEvent({ event_type: "error", error: String(error) }); } }
$("cmpLoadBtn").addEventListener("click", () => loadCompareSummary(true));

const initialView = new URLSearchParams(location.search).get("view") || new URLSearchParams(location.search).get("tab") || document.documentElement.dataset.defaultView;
setView(initialView === "compare" ? "experiments" : initialView);
loadTuneFields($("agDom").value);
loadControlledFields();
loadMatFiles();
fetch("/health").then((response) => { if (!response.ok) throw new Error(); setStatus("idle", "空闲"); }).catch(() => setStatus("error", "离线"));
