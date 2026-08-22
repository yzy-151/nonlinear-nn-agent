import { classifyEvent, formatConsole, normalizeEvent } from "/ui/event_view_model.js";

const $ = (id) => document.getElementById(id);
const state = { events: [], selected: null, currentRunId: null, controller: null, approvalTimer: null, currentApproval: null, experiments: [], finalEvaluation: null, terminalStatus: null, runMode: null, runConfig: {}, graphMode: "multiagent", graphSnapshots: {}, coding: { candidates: 0, passed: 0, failed: 0, attempts: 0 } };
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
      ["start", "Multi-Agent Run", "目标、预算与审核策略", 390, 12, 220, 70, "start", { output: "run_request.json" }],
      ["idea_plan", "Idea / Plan", "先验 · 假设 · 候选计划", 35, 140, 155, 118, "agent", { input: "run_request.json", output: "plan.json", artifact: "plan.json", feedback: "failure_facts.json" }],
      ["plan_gate", "PlanGate", "Schema · 引用 · 预算", 235, 158, 105, 82, "gate", { input: "plan.json", output: "validated_plan.json", feedback: "gate_errors.json" }],
      ["coding", "Coding", "候选代码 · AST · Smoke", 385, 140, 160, 118, "agent", { input: "validated_plan.json", output: "candidate_manifest.json", artifact: "plugin.py", feedback: "coding_errors.json" }],
      ["execution", "Execution", "Tool call · 训练 · Metrics", 615, 140, 160, 118, "agent", { input: "candidate_manifest.json", output: "execution_state.json", artifact: "metrics.json", feedback: "failure_facts.json" }],
      ["writing", "Writing", "证据归因 · PDF / HTML", 820, 140, 150, 118, "agent", { input: "metrics.json + psd.png", output: "report.pdf", artifact: "report.pdf", feedback: "fidelity_errors.json" }],
      ["result", "Result", "报告与可下载产物", 820, 315, 150, 78, "result", { input: "report.pdf", artifact: "report.pdf" }],
    ],
    edges: [
      ["start-idea", "control", "M500 82 C500 112 112 104 112 140", "run_request.json", 294, 103],
      ["idea-gate", "control", "M190 199 C208 199 217 199 235 199", "plan.json", 202, 188],
      ["idea-plan-artifact", "artifact", "M112 258 C112 292 465 292 465 258", "plan.json", 276, 305],
      ["gate-coding", "control", "M340 199 C357 199 368 199 385 199", "validated.json", 347, 188],
      ["coding-execution", "control", "M545 199 C572 167 588 167 615 199", "manifest.json", 564, 161],
      ["coding-model-artifact", "artifact", "M465 258 C465 302 695 302 695 258", "plugin.py", 565, 315],
      ["execution-writing", "control", "M775 199 C792 199 803 199 820 199", "state.json", 787, 188],
      ["execution-evidence-artifact", "artifact", "M695 258 C695 292 895 292 895 258", "metrics.json + psd.png", 742, 305],
      ["writing-result", "artifact", "M895 258 C895 282 895 291 895 315", "report.pdf", 902, 288],
      ["coding-plan", "feedback", "M465 140 C465 88 112 88 112 140", "coding_errors", 295, 77],
      ["execution-plan", "feedback", "M695 140 C695 62 112 62 112 140", "failure_facts", 420, 51],
      ["gate-plan", "feedback", "M287 158 C287 108 112 108 112 140", "gate_errors", 193, 98],
      ["writing-plan", "feedback", "M895 140 C895 35 112 35 112 140", "fidelity_errors", 760, 18],
    ],
  },
  controlled: {
    nodes: [["start","Controlled Search","白名单模型与可调字段",410,12,180,70,"start",{output:"search_request.json"}],["planner","Planner","受控候选配置",35,150,155,112,"agent",{input:"search_request.json",output:"candidate_config.yaml"}],["guard","Whitelist Guard","字段 · 值域 · 参数量",235,150,155,112,"gate",{input:"candidate_config.yaml",output:"resolved_config.yaml",feedback:"guard_rejection.json"}],["training","Train / Evaluate","固定训练与 NMSE",455,150,155,112,"agent",{input:"resolved_config.yaml",output:"training_result.json",artifact:"metrics.json + psd.png"}],["reflection","Facts","结果事实与去重",675,150,135,112,"agent",{input:"training_result.json",output:"reflection_facts.json",feedback:"reflection_facts.json"}],["best","Best Result","对照与最优产物",840,150,130,112,"result",{input:"metrics.json",artifact:"best_result.json"}]],
    edges: [["start-planner","control","M500 82 C500 112 112 112 112 150","search_request.json",285,103],["planner-guard","control","M190 206 C208 206 217 206 235 206","candidate_config.yaml",190,195],["guard-training","control","M390 206 C415 206 430 206 455 206","resolved_config.yaml",390,195],["training-facts","artifact","M532 262 C532 296 742 296 742 262","metrics.json + psd.png",574,309],["facts-planner","feedback","M742 150 C742 80 112 80 112 150","reflection_facts.json",370,69],["facts-best","control","M810 206 C822 206 828 206 840 206","best_result.json",803,195]],
  },
  agent: {
    nodes: [["start","Agent Planner Run","目标与动作预算",410,12,180,70,"start",{output:"agent_request.json"}],["planner","Planner","选择一个工具动作",35,150,145,112,"agent",{input:"agent_request.json",output:"tool_call.json",feedback:"reflection_facts.json"}],["tool_call","Tool Call","Schema 与参数检查",225,150,145,112,"gate",{input:"tool_call.json",output:"validated_call.json"}],["runtime","Runtime","执行注册工具",415,150,145,112,"agent",{input:"validated_call.json",output:"tool_result.json",artifact:"artifacts.json"}],["observation","Observation","指标 · 错误 · 产物",605,150,145,112,"agent",{input:"tool_result.json",output:"observation.json"}],["reflection","Reflection","仅提取事实",795,150,145,112,"agent",{input:"observation.json",output:"reflection_facts.json",feedback:"reflection_facts.json"}]],
    edges: [["start-planner","control","M500 82 C500 112 107 112 107 150","agent_request.json",285,103],["planner-tool","control","M180 206 C198 206 207 206 225 206","tool_call.json",177,195],["tool-runtime","control","M370 206 C388 206 397 206 415 206","validated_call.json",365,195],["runtime-observation","artifact","M487 262 C487 296 677 296 677 262","tool_result.json",530,309],["observation-reflection","control","M750 206 C768 206 777 206 795 206","observation.json",746,195],["reflection-planner","feedback","M867 150 C867 70 107 70 107 150","reflection_facts.json",400,59]],
  },
  workflow: {
    nodes: [["start","Fixed Workflow Run","确定性请求与固定工具链",410,12,180,70,"start",{output:"workflow_request.json"}],["generate_config","Generate Config","解析并冻结配置",35,150,155,112,"agent",{input:"workflow_request.json",output:"config.yaml"}],["run_training","Run Training","固定训练入口",245,150,155,112,"agent",{input:"config.yaml",output:"checkpoint.pt",artifact:"metrics.json"}],["verify_artifacts","Verify Artifacts","指标与文件复核",455,150,155,112,"gate",{input:"metrics.json",output:"verified_artifacts.json"}],["write_report","Write Report","摘要与证据报告",665,150,155,112,"agent",{input:"verified_artifacts.json",output:"summary.md",artifact:"report.pdf"}],["result","Result","产物下载",855,150,115,112,"result",{input:"report.pdf",artifact:"report.pdf"}]],
    edges: [["start-config","control","M500 82 C500 112 112 112 112 150","workflow_request.json",285,103],["config-training","artifact","M190 206 C210 206 225 206 245 206","config.yaml",190,195],["training-verify","artifact","M400 206 C420 206 435 206 455 206","metrics.json",400,195],["verify-report","control","M610 206 C630 206 645 206 665 206","verified_artifacts.json",598,195],["report-result","artifact","M820 206 C835 206 840 206 855 206","report.pdf",815,195]],
  },
};

function ensureGraphSnapshot(mode) {
  const graph = WORKFLOW_GRAPHS[mode] || WORKFLOW_GRAPHS.multiagent;
  if (!state.graphSnapshots[mode]) {
    state.graphSnapshots[mode] = {
      nodes: Object.fromEntries(graph.nodes.map(([id]) => [id, { status: "pending", runtime: "waiting", cost: id === "execution" || id === "runtime" || id === "run_training" ? "runtime" : "$0.0000" }])),
      edges: Object.fromEntries(graph.edges.map(([id]) => [id, null])),
      previousRole: null,
      artifacts: [],
    };
  }
  return state.graphSnapshots[mode];
}

function graphPort(kind, label) {
  if (!label) return "";
  return `<span class="node-port ${kind} port-${kind === "artifact" ? "artifact" : kind === "feedback" ? "feedback" : "control"}"><i></i><em class="port-label">${esc(label)}</em></span>`;
}

function renderWorkflowGraph(mode) {
  const graph = WORKFLOW_GRAPHS[mode] || WORKFLOW_GRAPHS.multiagent;
  state.graphMode = mode;
  const edges = graph.edges.map(([id, type, d, label, labelX, labelY]) => `<path class="edge-${type}" data-wire="${id}" data-edge-type="${type}" d="${d}"/><text class="artifact-label edge-${type}-label" x="${labelX}" y="${labelY}" text-anchor="middle">${esc(label)}</text>`).join("");
  const nodes = graph.nodes.map(([id, label, detail, x, y, width, height, kind = "agent", ports = {}]) => {
    const runner = '<svg class="node-outline-runner" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><rect class="node-outline-path" x="1" y="1" width="98" height="98" pathLength="100"/></svg>';
    if (kind === "start") return `<button class="agent-node workflow-node pending start" data-agent-node="${id}" style="left:${x}px;top:${y}px;width:${width}px;height:${height}px">${runner}${graphPort("output", ports.output)}<svg class="start-node-mark" aria-hidden="true"><use href="#i-play"/></svg><span class="start-node-copy"><small>RUN ENTRY</small><b>${esc(label)}</b><em>${esc(detail)}</em></span><span class="node-state">PENDING</span><small class="node-runtime">waiting</small><span class="node-cost hidden">$0.0000</span></button>`;
    return `<button class="agent-node workflow-node pending ${kind}" data-agent-node="${id}" style="left:${x}px;top:${y}px;width:${width}px;height:${height}px">${runner}${graphPort("input", ports.input)}${graphPort("output", ports.output)}${graphPort("artifact", ports.artifact)}${graphPort("feedback", ports.feedback)}<small class="node-runtime">waiting</small><b>${esc(label)}</b><p>${esc(detail)}</p><footer><span class="node-state">PENDING</span><span class="node-cost">${id === "execution" || id === "runtime" || id === "run_training" ? "runtime" : "$0.0000"}</span></footer></button>`;
  }).join("");
  $("graphStage").innerHTML = `<svg class="graph-wires" viewBox="0 0 1000 410" aria-hidden="true">${edges}</svg>${nodes}`;
  $("nodeArtifactPanel").classList.add("hidden");
  bindGraphNodeClicks();
  applyGraphSnapshot(mode);
}

function applyGraphSnapshot(mode = state.graphMode) {
  const snapshot = ensureGraphSnapshot(mode);
  if (mode !== state.graphMode) return;
  Object.entries(snapshot.nodes).forEach(([id, item]) => {
    const node = document.querySelector(`[data-agent-node="${id}"]`);
    if (!node) return;
    node.classList.remove("pending", "running", "complete", "failed", "rejected", "review");
    node.classList.add(item.status || "pending");
    node.querySelector(".node-state").textContent = String(item.label || item.status || "pending").toUpperCase();
    node.querySelector(".node-runtime").textContent = item.runtime || "waiting";
    node.querySelector(".node-cost").textContent = item.cost || "$0.0000";
  });
  Object.entries(snapshot.edges).forEach(([id, edgeState]) => {
    const edge = document.querySelector(`[data-wire="${id}"]`);
    if (!edge) return;
    edge.classList.remove("active", "complete", "failed");
    if (edgeState) edge.classList.add(edgeState);
  });
  renderGraphArtifacts(snapshot.artifacts);
}

function updateGraphNode(id, status, telemetry = {}, mode = state.graphMode) {
  const snapshot = ensureGraphSnapshot(mode);
  const current = snapshot.nodes[id];
  if (!current) return;
  snapshot.nodes[id] = { ...current, ...telemetry, status };
  applyGraphSnapshot(mode);
}

function completeGraphNode(id, edge, mode = state.graphMode, status = "complete") {
  updateGraphNode(id, status, { label: status === "complete" ? "DONE" : status }, mode);
  if (edge) setEdgeState(edge, status === "complete" ? "complete" : "failed", mode);
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
  state.graphSnapshots = {};
  $("writingArtifacts").innerHTML = "";
  $("nodeArtifactPanel").classList.add("hidden");
  renderWorkflowGraph(state.graphMode);
}

function setGraphRunning(role, mode = state.graphMode) {
  const snapshot = ensureGraphSnapshot(mode);
  Object.entries(snapshot.nodes).forEach(([id, item]) => {
    if (item.status === "running" && id !== role) snapshot.nodes[id] = { ...item, status: "complete", label: "DONE" };
  });
  updateGraphNode(role, "running", { label: "RUNNING" }, mode);
}

function setEdgeState(id, value, mode = state.graphMode) {
  const snapshot = ensureGraphSnapshot(mode);
  if (!(id in snapshot.edges)) return;
  snapshot.edges[id] = value;
  applyGraphSnapshot(mode);
}

function routeGraphEvent(payload, mode = "multiagent") {
  const role = payload.role;
  const status = payload.status;
  const failed = ["failed", "error", "budget_exceeded", "rejected", "invalid_plan"].includes(status);
  const snapshot = ensureGraphSnapshot(mode);
  if (role === "idea_plan") {
    if (snapshot.previousRole === "execution" || snapshot.previousRole === "final_evaluation") {
      setEdgeState("execution-writing", null, mode);
      setEdgeState("execution-evidence-artifact", "complete", mode);
      setEdgeState("execution-plan", "active", mode);
    }
    else setEdgeState("start-idea", "complete", mode);
    setEdgeState("idea-gate", failed ? "failed" : "active", mode);
    setEdgeState("idea-plan-artifact", failed ? "failed" : "active", mode);
    if (!failed) setGraphRunning("plan_gate", mode);
  } else if (role === "plan_gate") {
    setEdgeState("idea-gate", failed ? "failed" : "complete", mode);
    setEdgeState("idea-plan-artifact", failed ? "failed" : "complete", mode);
    if (failed) { setEdgeState("gate-plan", "active", mode); setGraphRunning("idea_plan", mode); }
    else { setEdgeState("gate-coding", "active", mode); setGraphRunning("coding", mode); }
  } else if (role === "coding") {
    setEdgeState("gate-coding", failed ? "failed" : "complete", mode);
    if (failed) { setEdgeState("coding-plan", "active", mode); setGraphRunning("idea_plan", mode); }
    else { setEdgeState("coding-execution", "active", mode); setEdgeState("coding-model-artifact", "active", mode); setGraphRunning("execution", mode); }
  } else if (role === "execution" || role === "final_evaluation") {
    setEdgeState("coding-execution", failed ? "failed" : "complete", mode);
    setEdgeState("coding-model-artifact", failed ? "failed" : "complete", mode);
    if (failed || payload.next_node === "idea_plan") {
      setEdgeState("execution-writing", null, mode);
      setEdgeState("execution-evidence-artifact", failed ? "failed" : "complete", mode);
      setEdgeState("execution-plan", "active", mode);
      setGraphRunning("idea_plan", mode);
    } else {
      setEdgeState("execution-writing", "active", mode);
      setEdgeState("execution-evidence-artifact", "active", mode);
      if (payload.next_node === "final_evaluation") setGraphRunning("execution", mode);
      else setGraphRunning("writing", mode);
    }
  } else if (role === "writing") {
    setEdgeState("execution-writing", failed ? "failed" : "complete", mode);
    setEdgeState("execution-evidence-artifact", failed ? "failed" : "complete", mode);
    setEdgeState("writing-result", failed ? "failed" : "active", mode);
    if (payload.next_node === "idea_plan") {
      setEdgeState("writing-plan", "active", mode);
      setGraphRunning("idea_plan", mode);
    }
  }
  snapshot.previousRole = role;
}

function updateAgentGraph(raw) {
  const payload = raw.payload || {};
  const mode = raw.event_type === "multi_agent_role" || raw.event_type === "multi_agent_terminal" ? "multiagent" : (state.runMode || state.graphMode);
  routeOperationalEvent(raw, mode);
  if (raw.event_type === "multi_agent_terminal") {
    const snapshot = ensureGraphSnapshot("multiagent");
    Object.entries(snapshot.edges).forEach(([id, value]) => { if (value === "active") setEdgeState(id, "complete", "multiagent"); });
    if (["completed", "succeeded"].includes(raw.status || payload.status)) updateGraphNode("result", "complete", { label: "READY" }, "multiagent");
    return;
  }
  if (raw.event_type !== "multi_agent_role") return;
  routeGraphEvent(payload, "multiagent");
  const usage = payload.model_usage || [];
  const latency_ms = Number(payload.latency_ms || usage.reduce((sum, item) => sum + Number(item.latency_ms || 0), 0));
  const cost_usd = Number(payload.cost_usd || usage.reduce((sum, item) => sum + Number(item.cost_usd || 0), 0));
  const failed = ["failed", "error", "budget_exceeded", "rejected", "invalid_plan"].includes(payload.status);
  updateGraphNode(payload.role === "final_evaluation" ? "execution" : payload.role, failed ? payload.status : "complete", { label: payload.status || "complete", runtime: latency_ms ? `${(latency_ms / 1000).toFixed(2)}s` : "local runtime", cost: cost_usd ? `$${cost_usd.toFixed(4)}` : (payload.role === "execution" ? "tool runtime" : "$0.0000") }, "multiagent");
  const outputs = payload.output_refs || [];
  if (payload.role === "writing") {
    const reports = outputs.filter((item) => String(item).startsWith("report:"));
    ensureGraphSnapshot("multiagent").artifacts = reports.map((ref) => String(ref).slice(7));
    renderGraphArtifacts(ensureGraphSnapshot("multiagent").artifacts);
    $("nodeArtifactPanel").classList.toggle("hidden", reports.length === 0);
  }
}

function renderGraphArtifacts(paths = []) {
  $("writingArtifacts").innerHTML = paths.map((path) => `<a href="${artifactUrl(path)}" target="_blank"><b>${esc(path.toLowerCase().endsWith(".pdf") ? "PDF" : "REPORT")}</b><span>PDF path: ${esc(path)}</span></a>`).join("");
}

function routeOperationalEvent(raw, mode = state.runMode || state.graphMode) {
  if (raw.event_type === "multi_agent_role" || mode === "multiagent") return;
  const type = String(raw.event_type || "");
  const payload = raw.payload || {};
  const tool = String(raw.tool || payload.tool || payload.tool_name || "");
  if (mode === "controlled") {
    if (type === "plan_generated") { completeGraphNode("planner", "start-planner", mode); setEdgeState("planner-guard", "active", mode); setGraphRunning("guard", mode); }
    else if (type === "experiment_rejected") { completeGraphNode("guard", "planner-guard", mode, "rejected"); setEdgeState("facts-planner", "active", mode); setGraphRunning("planner", mode); }
    else if (type === "experiment_start") { completeGraphNode("guard", "planner-guard", mode); setEdgeState("guard-training", "active", mode); setGraphRunning("training", mode); }
    else if (type === "experiment_end") { completeGraphNode("training", "guard-training", mode); setEdgeState("training-facts", "active", mode); setGraphRunning("reflection", mode); }
    else if (type.includes("reflection") && !["complete", "loop_complete"].includes(type)) { completeGraphNode("reflection", "training-facts", mode); setEdgeState("facts-planner", "active", mode); setGraphRunning("planner", mode); }
    else if (["complete", "loop_complete"].includes(type)) { completeGraphNode("reflection", "training-facts", mode); setEdgeState("facts-best", "complete", mode); completeGraphNode("best", null, mode); }
  } else if (mode === "agent") {
    if (type.includes("plan")) { completeGraphNode("planner", "start-planner", mode); setEdgeState("planner-tool", "active", mode); setGraphRunning("tool_call", mode); }
    else if (type === "tool_start") { completeGraphNode("tool_call", "planner-tool", mode); setEdgeState("tool-runtime", "active", mode); setGraphRunning("runtime", mode); }
    else if (type === "tool_end") { completeGraphNode("runtime", "tool-runtime", mode); setEdgeState("runtime-observation", "active", mode); setGraphRunning("observation", mode); }
    else if (type.includes("reflection")) { completeGraphNode("observation", "runtime-observation", mode); setEdgeState("observation-reflection", "active", mode); setGraphRunning("reflection", mode); }
    else if (["complete", "loop_complete"].includes(type)) completeGraphNode("reflection", "observation-reflection", mode);
  } else if (mode === "workflow") {
    const order = ["generate_config", "run_training", "verify_artifacts", "write_report"];
    const index = order.indexOf(tool);
    if (index >= 0 && type === "tool_start") {
      const edge = index === 0 ? "start-config" : ["config-training", "training-verify", "verify-report"][index - 1];
      setEdgeState(edge, "active", mode); setGraphRunning(tool, mode);
    }
    if (index >= 0 && type === "tool_end") {
      completeGraphNode(tool, index === 0 ? "start-config" : ["config-training", "training-verify", "verify-report"][index - 1], mode);
      if (index + 1 < order.length) { setEdgeState(["config-training", "training-verify", "verify-report"][index], "active", mode); setGraphRunning(order[index + 1], mode); }
      else { setEdgeState("report-result", "complete", mode); completeGraphNode("result", null, mode); }
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
  state.runMode = url.startsWith("/multi-agent/") ? "multiagent" : url.startsWith("/controlled-search/") ? "controlled" : url.startsWith("/agent/") ? "agent" : url.startsWith("/runs/") ? "workflow" : "other";
  state.runConfig = { ...body };
  setRunControlsDisabled(true);
  const original = button.innerHTML;
  button.textContent = "运行中...";
  const controller = new AbortController();
  state.controller = controller;
  setRunning(runId, true);
  const graphEntry = { multiagent: ["idea_plan", "start-idea"], controlled: ["planner", "start-planner"], agent: ["planner", "start-planner"], workflow: ["generate_config", "start-config"] }[state.runMode];
  if (graphEntry) {
    updateGraphNode("start", "complete", { label: "STARTED", runtime: "0.00s" }, state.runMode);
    setEdgeState(graphEntry[1], "active", state.runMode);
    setGraphRunning(graphEntry[0], state.runMode);
  }
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
