from __future__ import annotations


def render_home_page() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nonlinear Agent Harness</title>
<style>
:root {
  --bg: #060b14;
  --surface: #0c1222;
  --card: #111827;
  --border: #1e2d3d;
  --text: #e8ecf2;
  --muted: #8896a9;
  --accent: #38bdf8;
  --accent2: #818cf8;
  --green: #34d399;
  --red: #f87171;
  --amber: #fbbf24;
  --radius: 12px;
}
* { box-sizing:border-box; margin:0; padding:0; }
body {
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  min-height:100vh; line-height:1.55;
  -webkit-font-smoothing: antialiased;
}
header {
  background: linear-gradient(135deg, #070e1a 0%, #0f172a 60%, #151e33 100%);
  border-bottom:1px solid var(--border); padding:22px 32px;
  display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:14px;
}
.logo { display:flex; align-items:center; gap:14px; }
.logo-icon {
  width:48px; height:48px; border-radius:12px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  display:flex; align-items:center; justify-content:center; font-size:24px;
  box-shadow: 0 0 20px rgba(56,189,248,.25);
}
.logo h1 { font-size:22px; font-weight:700; letter-spacing:-0.4px; }
.logo span { font-size:12px; color:var(--muted); }

.status-badge {
  display:flex; align-items:center; gap:10px; font-size:14px; font-weight:600;
  padding:10px 22px; border-radius:24px; background:var(--card); border:1px solid var(--border);
}
.status-badge .dot { width:13px; height:13px; border-radius:50%; }
.dot.idle    { background:#4b5563; }
.dot.running { background:var(--accent); animation:pulse 1s infinite; box-shadow:0 0 10px rgba(56,189,248,.5); }
.dot.done    { background:var(--green); box-shadow:0 0 10px rgba(52,211,153,.4); }
.dot.error   { background:var(--red); box-shadow:0 0 10px rgba(248,113,113,.4); }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.3;transform:scale(1.25)} }

.tabs {
  display:flex; gap:0; padding:0 32px;
  background:var(--surface); border-bottom:1px solid var(--border);
}
.tab {
  padding:15px 28px; cursor:pointer; font-weight:650; font-size:14px;
  color:var(--muted); border-bottom:2px solid transparent; user-select:none;
}
.tab:hover { color:var(--text); }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); }

main { padding:24px 32px 40px; display:grid; grid-template-columns: minmax(360px,460px) 1fr; gap:22px; align-items:start; }
@media (max-width:860px) { main { grid-template-columns:1fr; } header,.tabs,main { padding-left:14px; padding-right:14px; } }

.card {
  background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
  padding:22px; box-shadow:0 2px 8px rgba(0,0,0,.3); margin-bottom:18px;
}
.card h2 { font-size:16px; font-weight:650; margin-bottom:14px; }
.card-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }

label { display:block; margin:12px 0 5px; font-size:11px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.6px; }
input, select, textarea {
  width:100%; border:1px solid var(--border); border-radius:8px;
  padding:10px 12px; font:inherit; font-size:14px;
  background:var(--surface); color:var(--text);
}
input:focus, select:focus, textarea:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px rgba(56,189,248,.12); }
textarea { min-height:72px; resize:vertical; }
select { cursor:pointer; }

.btn {
  display:inline-flex; align-items:center; justify-content:center; gap:8px;
  min-height:44px; padding:10px 20px; margin-top:16px; width:100%;
  border:none; border-radius:9px; font:inherit; font-size:14px; font-weight:650;
  cursor:pointer; letter-spacing:-0.2px;
}
.btn-primary { background:linear-gradient(135deg, var(--accent), var(--accent2)); color:#fff; }
.btn-primary:hover { filter:brightness(1.1); transform:translateY(-1px); box-shadow:0 6px 20px rgba(56,189,248,.35); }
.btn-primary:disabled { opacity:.5; cursor:not-allowed; transform:none; filter:none; box-shadow:none; }
.btn-secondary { background:var(--surface); color:var(--text); border:1px solid var(--border); }
.btn-secondary:hover { border-color:var(--accent); }

.btn-link {
  display:inline-flex; align-items:center; gap:5px; padding:9px 16px;
  border-radius:8px; border:1px solid var(--border); background:var(--card);
  color:var(--text); text-decoration:none; font-size:13px; font-weight:600;
}
.btn-link:hover { border-color:var(--accent); color:var(--accent); }
.link-row { display:flex; flex-wrap:wrap; gap:8px; }

.event-toolbar {
  display:flex; align-items:center; justify-content:space-between;
  margin-bottom:12px; flex-wrap:wrap; gap:8px;
}
.event-toolbar span { font-size:12px; color:var(--muted); }
.event-count { font-weight:700; color:var(--accent); font-size:18px; }

pre.event-log {
  min-height:540px; max-height:72vh; overflow:auto; margin:0;
  padding:18px; border:1px solid var(--border); border-radius:var(--radius);
  background:#060b15; color:#cdd6e0;
  font:14px/1.65 "Cascadia Code","Fira Code",Consolas,monospace;
  white-space:pre-wrap; word-break:break-word;
}
.ev-start   { color:var(--accent); }
.ev-end     { color:var(--green); }
.ev-error   { color:var(--red); }
.ev-metric  { color:var(--amber); }
.ev-plan    { color:#c084fc; }
.ev-reflect { color:#f472b6; }
.ev-round   { color:#67e8f9; }
.ev-info    { color:var(--muted); }

.provider-note {
  margin-top:8px; padding:9px 13px; border-radius:7px;
  font-size:12px; background:#1a2440; color:var(--amber); border:1px solid #2d3b5a;
  display:none; line-height:1.45;
}
.provider-note.show { display:block; }
.provider-note code { color:var(--accent); font-family:"Cascadia Code",monospace; font-size:12px; }

::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:#2d3b52; border-radius:4px; }
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">&#9883;</div>
    <div><h1>Nonlinear Agent Harness</h1><span>LLM-driven experiment runtime & streaming dashboard</span></div>
  </div>
  <div class="status-badge"><span class="dot idle" id="statusDot"></span><span id="statusLabel">Idle</span></div>
</header>

<div class="tabs">
  <div class="tab active" data-tab="workflow">&#9881; &nbsp;Workflow</div>
  <div class="tab" data-tab="agent">&#10027; &nbsp;Agent Planner</div>
  <div class="tab" data-tab="benchmark">&#9733; &nbsp;Benchmark</div>
</div>

<main>
<div>

  <div class="card" style="padding:14px 20px;">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
      <span style="font-size:13px;font-weight:650;">Quick Links</span>
      <div class="link-row">
        <a class="btn-link" href="/diagnostics/agent-runtime-dashboard.html" target="_blank">HTML Dashboard</a>
        <a class="btn-link" href="/diagnostics/agent-runtime-dashboard.md" target="_blank">Markdown Report</a>
        <a class="btn-link" href="/health" target="_blank">Health Check</a>
      </div>
    </div>
  </div>

  <!-- WORKFLOW -->
  <div class="card" id="panel-workflow">
    <h2>&#9881; &nbsp;Fixed Workflow Harness</h2>
    <p style="font-size:12px;color:var(--muted);margin-bottom:12px;">
      Preset tool chain: generate_config &rarr; run_training &rarr; verify_artifacts &rarr; write_report. No LLM.
    </p>
    <label for="wfSid">Session ID</label>
    <input id="wfSid" value="ui-demo-001">
    <label for="wfGoal">Goal</label>
    <textarea id="wfGoal">Run nonlinear NN experiment through the Agent Harness streaming runtime.</textarea>
    <div class="card-grid">
      <div><label for="wfEp">Epochs</label><input id="wfEp" type="number" min="0" value="0"></div>
      <div><label for="wfThr">NMSE Threshold (dB)</label><input id="wfThr" type="number" step="0.1" value="-35"></div>
    </div>
    <label for="wfTo">Timeout (seconds)</label>
    <input id="wfTo" type="number" min="1" value="120">
    <button type="button" class="btn btn-primary" id="wfBtn">&#9654; &nbsp;Start Workflow Run</button>
  </div>

  <!-- AGENT -->
  <div class="card" id="panel-agent" style="display:none;">
    <h2>&#10027; &nbsp;LLM Agent Planner Loop</h2>
    <p style="font-size:12px;color:var(--muted);margin-bottom:12px;">
      LLM plans experiments. Schema guard validates. Multi-round self-correction.
      <strong style="color:var(--amber)">Training takes ~30s per experiment.</strong>
    </p>
    <label for="agProv">Planner Provider</label>
    <select id="agProv">
      <option value="fake">Fake LLM (offline demo, no API key)</option>
      <option value="deepseek">DeepSeek API (real LLM)</option>
    </select>
    <div class="provider-note show" id="noteFake">Uses hardcoded demo plans. Great for testing the agent loop.</div>
    <div class="provider-note" id="noteDp">Uses DEEPSEEK_API_KEY from environment or .env.local.</div>

    <label for="agGoal">Goal</label>
    <textarea id="agGoal">Find a low-NMSE nonlinear model under 4000 parameters.</textarea>
    <div class="card-grid">
      <div><label for="agRnd">Max Rounds</label><input id="agRnd" type="number" min="1" max="20" value="2"></div>
      <div><label for="agExp">Max Experiments</label><input id="agExp" type="number" min="1" max="50" value="3"></div>
    </div>
    <div class="card-grid">
      <div><label for="agPm">Param Budget</label><input id="agPm" type="number" value="4000"></div>
      <div><label for="agThr">NMSE Threshold (dB)</label><input id="agThr" type="number" step="0.1" value="-35"></div>
    </div>
    <label for="agTo">Timeout (seconds)</label>
    <input id="agTo" type="number" min="1" value="300">
    <button type="button" class="btn btn-primary" id="agBtn">&#10027; &nbsp;Start Agent Loop</button>
  </div>

  <!-- BENCHMARK -->
  <div class="card" id="panel-benchmark" style="display:none;">
    <h2>&#9733; &nbsp;Agent Benchmark Evaluation</h2>
    <p style="font-size:12px;color:var(--muted);margin-bottom:12px;">
      Runs 3 fixed test cases (target hit, invalid plan recovery, runtime failure) using Fake LLM. Evaluates Agent Loop quality &mdash; target hit rate, rejection handling, error recovery. Writes results to <code>benchmarks/</code>.
    </p>
    <label for="bmTo">Timeout (seconds)</label>
    <input id="bmTo" type="number" min="1" value="300">
    <label for="bmThr">NMSE Threshold (dB)</label>
    <input id="bmThr" type="number" step="0.1" value="-35">
    <button type="button" class="btn btn-primary" id="bmBtn">&#9733; &nbsp;Run Benchmark</button>
  </div>

</div>

<!-- EVENT VIEWER -->
<div class="card">
  <div class="event-toolbar">
    <h2 style="margin-bottom:0;">Runtime Events</h2>
    <span>Events: <span class="event-count" id="evCount">0</span></span>
  </div>
  <pre class="event-log" id="evBox">Ready. Pick a mode, fill the form, press Start.</pre>
  <button type="button" class="btn btn-secondary" id="clearBtn" style="margin-top:12px;">Clear Log</button>
</div>
</main>

<script>
(function(){
  "use strict";
  console.log("Agent Harness UI initializing...");

  // --- references ---
  var statusDot = document.getElementById("statusDot");
  var statusLabel = document.getElementById("statusLabel");
  var evBox = document.getElementById("evBox");
  var evCount = document.getElementById("evCount");
  var count = 0;

  function setStatus(s) {
    statusDot.className = "dot " + s;
    statusLabel.textContent = s.charAt(0).toUpperCase() + s.slice(1);
  }
  function appendLine(text, cls) {
    if (count === 0) evBox.textContent = "";
    evBox.textContent += text + "\n";
    count++;
    evCount.textContent = count;
    evBox.scrollTop = evBox.scrollHeight;
  }
  function evClass(type) {
    if (type === "tool_start" || type === "start" || type === "agent_start") return "ev-start";
    if (type === "tool_end" || type === "complete" || type === "loop_complete" || type === "experiment_end") return "ev-end";
    if (type === "error" || type === "experiment_rejected") return "ev-error";
    if (type === "metric") return "ev-metric";
    if (type === "plan_generated") return "ev-plan";
    if (type === "reflection") return "ev-reflect";
    if (type === "round_start") return "ev-round";
    return "ev-info";
  }

  // --- tabs ---
  document.querySelectorAll(".tab").forEach(function(t) {
    t.addEventListener("click", function() {
      document.querySelectorAll(".tab").forEach(function(x) { x.classList.remove("active"); });
      t.classList.add("active");
      var m = t.dataset.tab;
      document.getElementById("panel-workflow").style.display = (m === "workflow") ? "" : "none";
      document.getElementById("panel-agent").style.display = (m === "agent") ? "" : "none";
      document.getElementById("panel-benchmark").style.display = (m === "benchmark") ? "" : "none";
    });
  });

  // --- provider note ---
  document.getElementById("agProv").addEventListener("change", function() {
    document.getElementById("noteFake").classList.toggle("show", this.value === "fake");
    document.getElementById("noteDp").classList.toggle("show", this.value === "deepseek");
  });

  // --- clear ---
  document.getElementById("clearBtn").addEventListener("click", function() {
    evBox.textContent = "Ready.\n";
    count = 0;
    evCount.textContent = "0";
  });

  // --- format helpers ---
  function _ts(sec) {
    var d = new Date(sec * 1000);
    return d.toLocaleTimeString("en-GB", {hour:"2-digit",minute:"2-digit",second:"2-digit"});
  }
  function _fmt(obj) {
    var ts = obj.timestamp ? _ts(obj.timestamp) : "";
    var t = obj.event_type || obj.type || "";
    var st = obj.status || "";
    var tool = obj.tool || "";
    var step = obj.step || "";
    var lat = obj.latency_ms != null ? Math.round(obj.latency_ms) + "ms" : "";
    var sid = obj.session_id || "";
    var p = obj.payload || {};
    var out = [];

    // ── header line ──
    var h = ts ? "[" + ts + "] " : "";
    h += t;
    if (sid) h += " | " + sid;
    if (tool) h += " | " + tool;
    if (step) h += " | " + step;
    if (st && t !== "metric") h += " | " + st;
    if (lat) h += " | " + lat;
    out.push(h);

    // ── payload details ──

    // start / agent_start
    if (p.goal) out.push("  goal: " + p.goal);
    if (p.step_count) out.push("  steps: " + p.step_count);
    if (p.resume_from_step && p.resume_from_step > 1) out.push("  resume_from: " + p.resume_from_step);
    if (p.max_rounds) out.push("  max_rounds: " + p.max_rounds);
    if (p.max_experiments && p.max_experiments !== "unlimited") out.push("  max_exps: " + p.max_experiments);

    // tool args
    if (p.args) {
      var ak = Object.keys(p.args);
      if (ak.length) out.push("  args: " + JSON.stringify(p.args));
    }

    // plan
    if (p.summary) out.push("  plan: " + p.summary);
    if (p.stop !== undefined) out.push("  stop: " + p.stop);
    if (p.experiment_count != null) out.push("  exps=" + p.experiment_count);
    if (p.experiments && p.experiments.length) {
      p.experiments.forEach(function(e){
        out.push("  + " + e.id + (e.reason ? " — " + e.reason : ""));
        if (e.overrides) {
          var ov = e.overrides;
          var ovs = [];
          if (ov.model_type) ovs.push("model=" + ov.model_type);
          if (ov.feature_mode) ovs.push("feat=" + ov.feature_mode);
          if (ov.memory_depth) ovs.push("mem=" + ov.memory_depth);
          if (ov.mp_order_count) ovs.push("mp=" + ov.mp_order_count);
          if (ov.hidden_units) ovs.push("hidden=" + ov.hidden_units);
          if (ov.epochs != null) ovs.push("epochs=" + ov.epochs);
          if (ov.learning_rate) ovs.push("lr=" + ov.learning_rate);
          if (ovs.length) out.push("    overrides: " + ovs.join(", "));
        }
      });
    }

    // experiment start
    if (p.id) out.push("  id: " + p.id);
    if (p.reason && t === "experiment_start") out.push("  reason: " + p.reason);

    // experiment end
    if (p.round) out.push("  round: " + p.round);
    if (p.rounds) out.push("  total_rounds: " + p.rounds);
    if (p.history_count != null) out.push("  history: " + p.history_count);

    // reflection
    if (p.reflection) {
      var r = p.reflection;
      var sc = r.status_counts || {};
      out.push("  round: " + r.round);
      out.push("  records: " + r.record_count);
      out.push("  status: OK=" + (sc.succeeded||0) + " FAIL=" + (sc.failed||0) + " REJ=" + (sc.rejected||0));
      if (r.best_experiment_id) out.push("  best_id: " + r.best_experiment_id);
      if (r.best_nmse_db != null) out.push("  best_nmse: " + Number(r.best_nmse_db).toFixed(2) + " dB");
      if (r.error_type_counts) out.push("  error_types: " + JSON.stringify(r.error_type_counts));
      if (r.failure_causes && r.failure_causes.length) {
        r.failure_causes.forEach(function(c){ out.push("  cause: " + c); });
      }
      if (r.recovery_actions && r.recovery_actions.length) {
        r.recovery_actions.forEach(function(a){ out.push("  fix: " + a); });
      }
      if (r.avoid_next && r.avoid_next.length) {
        r.avoid_next.forEach(function(a){ out.push("  avoid: " + a); });
      }
    }

    // runtime metrics from output
    if (p.output) {
      if (p.output.context_summary) out.push("  summary: " + p.output.context_summary);
      if (p.output.elapsed_seconds) out.push("  elapsed: " + Number(p.output.elapsed_seconds).toFixed(1) + "s");
      if (p.output.returncode != null) out.push("  returncode: " + p.output.returncode);
      if (p.output.stdout_tail) out.push("  stdout: " + p.output.stdout_tail.trim().substring(0, 200));
      if (p.output.stderr_tail) out.push("  stderr: " + p.output.stderr_tail.trim().substring(0, 200));
      if (p.artifacts) out.push("  artifacts: " + JSON.stringify(p.artifacts));
      if (p.output.artifacts) out.push("  artifacts: " + JSON.stringify(p.output.artifacts));
      if (p.attempts != null) out.push("  attempts: " + p.attempts);

      // metrics from output
      if (p.output.metrics) {
        var om = p.output.metrics;
        if (om.nmse_db != null) out.push("  NMSE: " + Number(om.nmse_db).toFixed(2) + " dB");
        if (om.parameter_count != null) out.push("  params: " + om.parameter_count);
        if (om.model_type) {
          var mdl = "  model: " + om.model_type;
          if (om.feature_mode) mdl += "/" + om.feature_mode;
          if (om.memory_depth) mdl += " mem=" + om.memory_depth;
          if (om.mp_order_count) mdl += " mp=" + om.mp_order_count;
          if (om.epochs != null) mdl += " epochs=" + om.epochs;
          out.push(mdl);
        }
        if (om.final_train_loss != null) out.push("  loss: " + Number(om.final_train_loss).toExponential(3));
      }
    }

    // experiment_end metrics
    if (p.metrics) {
      var m = p.metrics;
      if (m.run_status) out.push("  run: " + m.run_status);
      if (m.nmse_db != null) out.push("  NMSE: " + Number(m.nmse_db).toFixed(2) + " dB");
      if (m.parameter_count) out.push("  params: " + m.parameter_count);
      if (m.model_type) out.push("  model: " + m.model_type);
    }

    // direct NMSE / params on payload
    if (p.nmse_db != null && !p.metrics && !p.output) out.push("  NMSE: " + Number(p.nmse_db).toFixed(2) + " dB");
    if (p.parameter_count && !p.metrics && !p.output) out.push("  params: " + p.parameter_count);

    // metric events
    if (t === "metric" && p.name && p.value != null) {
      var v = p.value, label = p.name;
      if (typeof v === "number") {
        if (label === "nmse_db") v = Number(v).toFixed(2);
        else if (label === "final_train_loss") v = Number(v).toExponential(3);
        else if (Math.abs(v) < 0.001) v = Number(v).toExponential(2);
        else v = Number(v).toFixed(4);
      }
      out.push("  " + label + " = " + v);
    }

    // errors
    if (obj.error) out.push("  ERR: " + obj.error.substring(0, 200));
    if (obj.error_type) out.push("  err_type: " + obj.error_type);
    if (p.error && p.error !== obj.error) out.push("  err: " + String(p.error).substring(0, 200));
    if (p.error_type && p.error_type !== obj.error_type) out.push("  err_type: " + p.error_type);
    if (p.run_status && p.run_status === "rejected") out.push("  REJECTED: " + (p.error || p.run_status));
    if (p.run_status && p.run_status === "failed") out.push("  FAILED: " + (p.error || p.run_status));

    return out.join("\n");
  }

  // --- SSE runner ---
  async function runSSE(url, body, btn) {
    btn.disabled = true;
    var orig = btn.textContent;
    btn.textContent = "Running...";
    setStatus("running");
    evBox.textContent = "";
    count = 0;
    evCount.textContent = "0";
    console.log("runSSE: fetching", url, body);
    try {
      var resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      console.log("runSSE: response", resp.status, resp.statusText);
      if (!resp.ok) throw new Error("HTTP " + resp.status + " " + resp.statusText);
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buf = "";
      while (true) {
        var part = await reader.read();
        if (part.done) break;
        buf += decoder.decode(part.value, {stream: true});
        var lines = buf.split("\n");
        buf = lines.pop() || "";
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          if (!line.trim()) continue;
          if (line.indexOf("event:") === 0) {
            var et = line.slice(6).trim();
            appendLine("\n[" + et + "]", evClass(et));
          } else if (line.indexOf("data:") === 0) {
            try {
              var obj = JSON.parse(line.slice(5).trim());
              appendLine(_fmt(obj), evClass(obj.event_type || obj.type || ""));
            } catch(_) {
              appendLine(line.slice(5).trim(), "ev-info");
            }
          }
        }
      }
      setStatus("done");
    } catch(e) {
      console.error("runSSE error:", e);
      appendLine("ERROR: " + String(e), "ev-error");
      setStatus("error");
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  }

  // --- WORKFLOW button ---
  var wfBtn = document.getElementById("wfBtn");
  wfBtn.addEventListener("click", function() {
    console.log("Workflow button clicked");
    var body = {
      goal: document.getElementById("wfGoal").value,
      epochs: Number(document.getElementById("wfEp").value),
      nmse_threshold_db: Number(document.getElementById("wfThr").value),
      timeout_seconds: Number(document.getElementById("wfTo").value)
    };
    var sid = document.getElementById("wfSid").value.trim() || "ui-demo-001";
    runSSE("/runs/" + encodeURIComponent(sid) + "/events", body, wfBtn);
  });

  // --- AGENT button ---
  var agBtn = document.getElementById("agBtn");
  agBtn.addEventListener("click", function() {
    console.log("Agent button clicked");
    var provider = document.getElementById("agProv").value;
    var body = {
      provider: provider,
      goal: document.getElementById("agGoal").value,
      max_rounds: Number(document.getElementById("agRnd").value),
      max_experiments: Number(document.getElementById("agExp").value),
      parameter_count_max: Number(document.getElementById("agPm").value),
      nmse_threshold_db: Number(document.getElementById("agThr").value),
      timeout_seconds: Number(document.getElementById("agTo").value),
      artifact_dir: null
    };
    runSSE("/agent/ui-agent-" + Date.now() + "/events", body, agBtn);
  });

  // --- BENCHMARK button ---
  var bmBtn = document.getElementById("bmBtn");
  bmBtn.addEventListener("click", function() {
    console.log("Benchmark button clicked");
    var body = {
      timeout_seconds: Number(document.getElementById("bmTo").value),
      nmse_threshold_db: Number(document.getElementById("bmThr").value)
    };
    runSSE("/benchmark/events", body, bmBtn);
  });

  console.log("Agent Harness UI ready.");
})();
</script>
</body>
</html>
"""
