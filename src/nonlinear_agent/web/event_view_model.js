const SUCCESS_TYPES = new Set(["tool_end", "complete", "loop_complete", "experiment_end", "benchmark_complete", "agent_task_benchmark_complete"]);
const RUNNING_TYPES = new Set(["start", "agent_start", "tool_start", "experiment_start", "round_start", "benchmark_case_start", "agent_task_benchmark_start"]);
const BENCHMARK_TYPES = new Set(["benchmark_case_start", "benchmark_case_end", "benchmark_complete", "agent_task_case_end", "agent_task_benchmark_complete"]);

export function classifyEvent(raw) {
  const payload = raw?.payload || {};
  const type = raw?.event_type || raw?.type || payload.type || "event";
  const errorType = raw?.error_type || payload.error_type || "";
  if (type === "error") return errorType === "metric_threshold_error" ? "warning" : "failure";
  if (type === "experiment_rejected" || type === "cancelled") return "failure";
  if (type === "multi_agent_terminal") return payload.status === "completed" || raw.status === "completed" ? "success" : "failure";
  if (type === "multi_agent_role") return ["failed", "error", "budget_exceeded"].includes(payload.status) ? "failure" : "planner";
  if (type === "reflection") return "reflection";
  if (type === "plan_generated") return "planner";
  if (type === "metric") return "metric";
  if (BENCHMARK_TYPES.has(type)) return "benchmark";
  if (SUCCESS_TYPES.has(type)) return "success";
  if (RUNNING_TYPES.has(type)) return "running";
  return "info";
}

function timestamp(raw) {
  if (!raw?.timestamp) return new Date();
  return new Date(raw.timestamp > 1e12 ? raw.timestamp : raw.timestamp * 1000);
}

function compactValue(value) {
  if (value == null) return "";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toPrecision(5);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function eventSummary(type, raw, payload) {
  if (type === "plan_generated") return payload.summary || raw.summary || "生成下一轮实验计划";
  if (type === "reflection") {
    const facts = payload.reflection?.facts || payload.facts || [];
    const causes = payload.reflection?.failure_causes || payload.failure_causes || [];
    return `提取 ${facts.length} 条事实${causes.length ? `，发现 ${causes.length} 个失败原因` : ""}`;
  }
  if (type === "multi_agent_role") return `${payload.role || "role"}: ${payload.status || "completed"}`;
  if (type === "tool_start") return `${raw.tool || payload.tool || "tool"} 开始执行`;
  if (type === "tool_end") return `${raw.tool || payload.tool || "tool"} 执行完成`;
  if (type === "metric") return `${payload.name || "metric"} = ${compactValue(payload.value)}`;
  if (type === "error") return raw.error || payload.error || "运行失败";
  if (type === "multi_agent_terminal") return `Multi-Agent ${payload.status || raw.status || "terminal"}`;
  if (type === "experiment_start" || type === "experiment_end") return payload.id || raw.id || type;
  if (type === "benchmark_case_start" || type === "benchmark_case_end") return payload.case_id || type;
  return payload.summary || raw.summary || raw.step || payload.goal || type.replaceAll("_", " ");
}

export function normalizeEvent(raw, index = 0) {
  const payload = raw?.payload || {};
  const type = raw?.event_type || raw?.type || payload.type || "event";
  const time = timestamp(raw);
  const role = payload.role || raw.role || raw.tool || payload.tool || raw.step || "runtime";
  const inputs = payload.input_refs || raw.input_refs || payload.caused_by_event_ids || [];
  const outputs = payload.output_refs || raw.output_refs || payload.artifacts || raw.artifacts || [];
  const facts = {
    session_id: raw.session_id || payload.session_id,
    status: payload.status || raw.status,
    round: payload.round ?? raw.round,
    tool: raw.tool || payload.tool,
    latency_ms: raw.latency_ms ?? payload.latency_ms,
    model_usage: payload.model_usage,
    context_evidence: payload.context_evidence,
    experiments: payload.experiments,
    final_evaluation: payload.final_evaluation,
    previous_reflection_facts: payload.previous_reflection_facts || raw.previous_reflection_facts,
    previous_reflection_failure_causes: payload.previous_reflection_failure_causes || raw.previous_reflection_failure_causes,
  };
  Object.keys(facts).forEach((key) => facts[key] == null && delete facts[key]);
  return {
    id: raw.event_id || raw.id || `${type}-${index}`,
    type,
    tone: classifyEvent(raw),
    title: eventSummary(type, raw, payload),
    role,
    time,
    timeLabel: time.toLocaleTimeString("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    inputs: Array.isArray(inputs) ? inputs : [inputs],
    outputs: Array.isArray(outputs) ? outputs : [outputs],
    facts,
    raw,
  };
}

function metricLines(metrics, prefix) {
  if (!metrics) return [];
  return Object.entries(metrics).filter(([, value]) => value != null).map(([key, value]) => `  ${prefix}.${key} = ${compactValue(value)}`);
}

export function formatConsole(raw) {
  const payload = raw?.payload || {};
  const event = normalizeEvent(raw);
  const lines = [`[${event.timeLabel}] ${event.type} | source=${raw.session_id || payload.session_id || "runtime"} | role=${event.role}`];
  if (event.title !== event.type) lines.push(`  ${event.title}`);
  if (event.type === "tool_start" && payload.args) lines.push(`  input args: ${JSON.stringify(payload.args)}`);
  if (event.type === "plan_generated") {
    const causes = payload.previous_reflection_failure_causes || raw.previous_reflection_failure_causes || [];
    const facts = payload.previous_reflection_facts || raw.previous_reflection_facts || [];
    if (causes.length) lines.push("  previous error reasons:", ...causes.map((item) => `    - ${compactValue(item)}`));
    if (facts.length) lines.push("  previous reflection facts:", ...facts.map((item) => `    - ${compactValue(item)}`));
    lines.push(`  new plan: ${payload.summary || raw.summary || "-"}`);
  }
  if (event.type === "reflection") {
    const reflection = payload.reflection || payload;
    (reflection.facts || []).forEach((fact) => lines.push(`  fact: ${compactValue(fact)}`));
    (reflection.failure_causes || []).forEach((cause) => lines.push(`  cause: ${compactValue(cause)}`));
  }
  if (event.type === "multi_agent_role") {
    lines.push(`  input_refs: ${(payload.input_refs || []).join(", ") || "none"}`);
    lines.push(`  output_refs: ${(payload.output_refs || []).join(", ") || "none"}`);
    (payload.model_usage || []).forEach((usage) => lines.push(`  model_usage: ${usage.role || payload.role} ${usage.provider || "-"}/${usage.model || "-"} tokens=${(usage.prompt_tokens || 0) + (usage.completion_tokens || 0)} latency=${Math.round(usage.latency_ms || 0)}ms`));
    (payload.context_evidence || []).forEach((item) => lines.push(`  context: ${item.evidence_id} source=${item.citation || item.run_id || "-"} score=${item.score ?? item.confidence ?? "-"}`));
  }
  if (event.type === "multi_agent_terminal") Object.entries(payload).filter(([key]) => key.endsWith("_path")).forEach(([key, value]) => lines.push(`  ${key}: ${value}`));
  lines.push(...metricLines(payload.output?.metrics, "tool_metrics"), ...metricLines(payload.metrics, "session_metrics"));
  const artifacts = payload.output?.artifacts || payload.artifacts || [];
  artifacts.forEach((artifact) => lines.push(`  artifact: ${artifact}`));
  if (raw.error || payload.error) lines.push(`  ERROR: ${raw.error || payload.error}`);
  return lines.join("\n");
}
