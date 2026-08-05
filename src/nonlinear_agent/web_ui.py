from __future__ import annotations


def render_home_page() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Nonlinear Agent Harness</title>
<style>
:root {
  --bg:#030712;--surface:#0f172a;--panel:#111827;--border:#253044;
  --text:#e5e7eb;--muted:#94a3b8;
  --blue:#38bdf8;--teal:#2dd4bf;--green:#34d399;--red:#f87171;--amber:#fbbf24;--ink:#f8fafc;
  --radius:8px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  font-family:"Segoe UI",system-ui,-apple-system,sans-serif;
  background:var(--bg);color:var(--text);min-height:100vh;line-height:1.55;font-size:15px;
  -webkit-font-smoothing:antialiased;
}

body::before{
  content:"";position:fixed;inset:0;z-index:0;
  background:linear-gradient(180deg,rgba(14,165,233,.14) 0%,rgba(15,23,42,0) 320px);
  pointer-events:none;
}

/* ── HEADER ── */
header{
  position:relative;z-index:1;
  background:rgba(15,23,42,.92);border-bottom:1px solid var(--border);
  padding:18px 36px;display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:14px;backdrop-filter:blur(16px);
}
.logo{display:flex;align-items:center;gap:14px}
.logo-icon{
  width:40px;height:40px;border-radius:12px;
  background:linear-gradient(135deg,var(--blue),var(--teal));
  display:flex;align-items:center;justify-content:center;font-size:20px;
  box-shadow:0 8px 24px rgba(37,99,235,.18);
}
.logo h1{font-size:19px;font-weight:750;letter-spacing:0}
.logo span{font-size:11px;color:var(--muted)}

.status-dot{
  display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;
  padding:7px 18px;border-radius:22px;background:var(--panel);border:1px solid var(--border);
}
.dot{width:11px;height:11px;border-radius:50%;transition:all .3s}
.dot.idle{background:#475569}
.dot.running{background:var(--blue);animation:pls 1s infinite;box-shadow:0 0 14px rgba(37,99,235,.35)}
.dot.done{background:var(--green);box-shadow:0 0 12px rgba(34,197,94,.4)}
.dot.error{background:var(--red);box-shadow:0 0 12px rgba(239,68,68,.4)}
@keyframes pls{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.25;transform:scale(1.5)}}

/* ── TABS ── */
nav.tabs{
  position:relative;z-index:1;
  display:flex;gap:0;padding:0 36px;
  background:rgba(3,7,18,.78);border-bottom:1px solid var(--border);
}
nav.tabs .tab{
  padding:16px 32px;cursor:pointer;font-weight:650;font-size:14px;
  color:var(--muted);border-bottom:3px solid transparent;user-select:none;
  transition:all .15s;
}
nav.tabs .tab:hover{color:var(--text)}
nav.tabs .tab.active{color:var(--blue);border-bottom-color:var(--blue)}

/* ── RESULT TABLES / METRIC CHIPS ── */
.r-table{width:100%;border-collapse:collapse;font-size:12px;background:#020617}
.r-table th{color:var(--muted);font-weight:700;text-align:left;padding:7px 8px;border-bottom:1px solid rgba(148,163,184,.28);white-space:nowrap}
.r-table td{padding:7px 8px;border-bottom:1px solid rgba(148,163,184,.12);white-space:nowrap;vertical-align:top}
.r-table tr:last-child td{border-bottom:none}
.r-table td.mname{white-space:normal;max-width:230px;line-height:1.3}
.chip{display:inline-flex;flex-direction:column;gap:2px;min-width:104px;padding:8px 12px;
  border:1px solid var(--border);border-radius:10px;background:#0b1120;font-size:11px;color:var(--muted)}
.chip b{font-size:14px;color:var(--text);font-weight:700}

/* ── MAIN ── */
main{
  position:relative;z-index:1;
  padding:26px 36px 40px;
  display:grid;grid-template-columns:minmax(380px,500px) 1fr;
  gap:26px;align-items:start;
}
@media(max-width:900px){main{grid-template-columns:1fr}header,nav.tabs,main{padding-left:14px;padding-right:14px}}

.card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:22px;margin-bottom:18px;box-shadow:0 10px 26px rgba(0,0,0,.25);
}
.card h2{font-size:16px;font-weight:650;margin-bottom:14px}
.card-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}

label{
  display:block;margin:12px 0 5px;font-size:10px;font-weight:700;
  color:var(--muted);text-transform:uppercase;letter-spacing:.5px;
}
input,select,textarea{
  width:100%;border:1px solid var(--border);border-radius:10px;
  padding:11px 14px;font:inherit;font-size:14px;
  background:#020617;color:var(--text);transition:border-color .15s,box-shadow .15s;
}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
textarea{min-height:72px;resize:vertical}
select{cursor:pointer}

.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  min-height:46px;padding:11px 24px;margin-top:18px;width:100%;
  border:none;border-radius:10px;font:inherit;font-size:14px;font-weight:650;
  cursor:pointer;transition:all .15s;letter-spacing:-0.2px;
}
.btn-go{
  background:linear-gradient(135deg,var(--blue),var(--teal));
  color:#fff;box-shadow:0 2px 16px rgba(37,99,235,.14);
}
.btn-go:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 6px 24px rgba(37,99,235,.22)}
.btn-go:disabled{opacity:.4;cursor:not-allowed;transform:none;filter:none;box-shadow:none}
.btn-stop{background:linear-gradient(135deg,var(--red),#dc2626);color:#fff;box-shadow:0 2px 12px rgba(239,68,68,.18);display:none}
.btn-stop:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(239,68,68,.3)}
.btn-ghost{
  background:var(--panel);color:var(--text);border:1px solid var(--border);
}
.btn-ghost:hover{border-color:var(--blue);color:var(--blue)}

.lnk{
  display:inline-flex;align-items:center;gap:6px;padding:8px 16px;
  border-radius:10px;border:1px solid var(--border);
  background:var(--panel);color:var(--text);text-decoration:none;
  font-size:13px;font-weight:600;transition:all .15s;
}
.lnk:hover{border-color:var(--blue);color:var(--blue)}

/* ── EVENT VIEWER ── */
pre.ev{
  min-height:540px;max-height:76vh;overflow:auto;margin:0;
  padding:20px;border:1px solid var(--border);border-radius:var(--radius);
  background:#0f172a;color:#dbeafe;
  font:13.5px/1.7 "Cascadia Code","Fira Code",Consolas,monospace;
  white-space:pre-wrap;word-break:break-word;
}
.ev-running{color:#60a5fa}
.ev-success{color:#86efac}
.ev-failure{color:#fca5a5;font-weight:700}
.ev-warning{color:#fb923c;font-weight:700}
.ev-metric{color:#fbbf24}
.ev-planner{color:#c4b5fd}
.ev-reflection{color:#f9a8d4}
.ev-benchmark{color:#67e8f9}
.ev-info{color:#94a3b8}

.note{
  margin-top:8px;padding:9px 13px;border-radius:10px;
  font-size:12px;background:rgba(251,191,36,.08);color:var(--amber);border:1px solid rgba(251,191,36,.28);
  display:none;line-height:1.45;
}
.note.on{display:block}
.note code{color:var(--blue);font-family:"Cascadia Code",monospace;font-size:11px}
.hint{font-size:12px;color:var(--muted);margin-bottom:14px}
.hint strong{color:var(--ink)}
.metric-list{display:grid;gap:8px;margin:12px 0 4px}
.metric{padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--panel);font-size:12px}
.metric code{color:var(--blue);font-weight:700}
.preview{
  display:none;margin-bottom:16px;border:1px solid var(--border);border-radius:var(--radius);
  overflow:hidden;background:#020617;
}
.preview.on{display:block}
.preview-head{
  display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  padding:12px 14px;border-bottom:1px solid var(--border);background:#111827;
}
.preview-head h3{font-size:14px;margin:0}
.preview-meta{font-size:12px;color:var(--muted)}
.preview img{display:block;width:100%;height:auto;background:#f8fafc}
.result-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:12px 14px}
@media(max-width:900px){.result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.result-chip{border:1px solid var(--border);border-radius:8px;background:var(--panel);padding:8px 10px}
.result-chip span{display:block;font-size:10px;text-transform:uppercase;color:var(--muted);font-weight:700;letter-spacing:.4px}
.result-chip b{display:block;margin-top:2px;font-size:14px;color:var(--ink);font-weight:750}

::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#1e293b;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#334155}
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">&#9883;</div>
    <div><h1>Nonlinear Agent Harness</h1><span>Experiment runtime &amp; streaming diagnostics</span></div>
  </div>
  <div class="status-dot"><span class="dot idle" id="statusDot"></span><span id="statusLabel">Idle</span></div>
</header>

<nav class="tabs">
  <div class="tab active" data-tab="workflow">&#9881; Workflow</div>
  <div class="tab" data-tab="agent">&#10027; Agent Planner</div>
  <div class="tab" data-tab="benchmark">&#9733; Benchmark</div>
  <div class="tab" data-tab="compare">&#9733; Strategy Comparison</div>
</nav>

<main>
<div>

  <div class="card" style="padding:14px 22px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
      <span style="font-size:14px;font-weight:650">Quick Links</span>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        <a class="lnk" href="/diagnostics/agent-runtime-dashboard.html" target="_blank">Dashboard</a>
        <a class="lnk" href="/diagnostics/agent-runtime-dashboard.md" target="_blank">MD Report</a>
        <a class="lnk" href="/health" target="_blank">Health</a>
      </div>
    </div>
  </div>

  <!-- WORKFLOW -->
  <div class="card" id="panel-workflow">
    <h2>&#9881; Fixed Workflow Harness</h2>
    <p class="hint">
      <strong>功能注释：</strong>固定工具链直接执行一次实验，不调用 LLM。
      顺序是 <code>generate_config</code> &rarr; <code>run_training</code> &rarr;
      <code>verify_artifacts</code> &rarr; <code>write_report</code>。
      适合展示 Runtime、ToolRegistry、Trace 和 artifact 验证。
    </p>
    <label for="wfSid">Session ID</label><input id="wfSid" value="ui-demo-001">
    <label for="wfGoal">Goal</label>
    <textarea id="wfGoal">Run nonlinear NN experiment through the Agent Harness streaming runtime.</textarea>
    <div class="card-grid">
      <div><label for="wfEp">Epochs</label><input id="wfEp" type="number" min="0" value="0"></div>
      <div><label for="wfThr">Threshold (dB)</label><input id="wfThr" type="number" step="0.1" value="-35"></div>
    </div>
    <label for="wfTo">Timeout (seconds)</label><input id="wfTo" type="number" min="1" value="120">
    <button type="button" class="btn btn-go" id="wfBtn">&#9654; Start Workflow Run</button>
  </div>

  <!-- AGENT -->
  <div class="card" id="panel-agent" style="display:none">
    <h2>&#10027; LLM Agent Planner Loop</h2>
    <p class="hint">
      <strong>功能注释：</strong>Planner 每轮读取 goal、history 和 constraints 后设计实验；
      Guard 校验字段、类型和参数预算；Runtime 执行工具链；history 与 reflection 进入下一轮决策。
      <strong>Training usually takes time per experiment.</strong>
    </p>
    <label for="agProv">Provider</label>
    <select id="agProv">
      <option value="fake">Fake LLM — offline demo</option>
      <option value="deepseek">DeepSeek API — real LLM</option>
    </select>
    <div class="note on" id="noteFake">Preset demo plans. No API key needed.</div>
    <div class="note" id="noteDp">Reads <code>DEEPSEEK_API_KEY</code> from <code>.env.local</code></div>
    <label for="agDom">Domain</label>
      <select id="agDom">
        <option value="nonlinear">Nonlinear Modeling</option>
        <option value="synthetic">Synthetic Regression</option>
      </select>
      <label for="agTune">Optimizable Directions <span style="color:var(--muted);font-weight:400;text-transform:none">(取消勾选 = 固定该超参，不进白名单)</span></label>
      <div id="agTune" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:#0b1120">
        <span style="color:var(--muted);font-size:12px">loading…</span>
      </div>
      <label for="agGoal">Goal</label>
    <textarea id="agGoal">Find a low-NMSE nonlinear model under 4000 parameters.</textarea>
    <div class="card-grid">
      <div><label for="agRnd">Max Rounds</label><input id="agRnd" type="number" min="1" max="20" value="2"></div>
      <div><label for="agExp">Max Experiments</label><input id="agExp" type="number" min="1" max="50" value="3"></div>
    </div>
    <div class="card-grid">
      <div><label for="agPm">Param Budget</label><input id="agPm" type="number" value="4000"></div>
      <div><label for="agThr">Threshold (dB)</label><input id="agThr" type="number" step="0.1" value="-35"></div>
    </div>
    <label for="agTo">Timeout (seconds)</label><input id="agTo" type="number" min="1" value="300">
    <button type="button" class="btn btn-go" id="agBtn">&#10027; Start Agent Loop</button>
  </div>

  <!-- COMPARE -->
  <div class="card" id="panel-compare" style="display:none">
    <h2>&#9878; Strategy Comparison</h2>
    <p class="hint">
      <strong>真实执行 4 种搜索策略对照。</strong>
      调参后点 Run 跑真实训练，点 Load Saved 加载已有结果。
    </p>
    <div class="card-grid" style="grid-template-columns:1fr 1fr 1fr 1fr 1fr 1fr">
      <div><label>Domain</label><select id="cmpDom">
        <option value="synthetic">Synthetic</option>
        <option value="nonlinear" selected>Nonlinear</option>
      </select></div>
      <div><label>Param Max</label><input id="cmpPm" type="number" value="15000"></div>
      <div><label>Target (dB)</label><input id="cmpThr" type="number" step="0.5" value="-39"></div>
      <div><label>Seeds</label><input id="cmpSeeds" type="number" min="1" max="10" value="3"></div>
      <div><label>Trials/Seed</label><input id="cmpBudget" type="number" min="1" max="20" value="5"></div>
      <div><label>Timeout (s)</label><input id="cmpTo" type="number" min="1" value="600"></div>
    </div>
    <label for="cmpPlan" style="margin-top:12px">LLM Plan <span style="color:var(--muted);font-weight:400">(仅 llm_* 策略使用，可自定义搜索策略)</span></label>
    <textarea id="cmpPlan" style="min-height:72px">Find the best nonlinear model under the given parameter budget and target. Use complex_lstsq with high memory_depth and mp_order_count for fast closed-form fitting. Avoid mp=1 or mp=2 with large memory which gives poor NMSE. Prefer mp>=4.</textarea>
    <div style="display:flex;gap:10px;margin-top:14px">
      <button type="button" class="btn btn-go" id="cmpBtn" style="margin-top:0;flex:1">&#9878; Run Comparison</button>
      <button type="button" class="btn btn-ghost" id="cmpLoadBtn" style="margin-top:0;flex:1;min-height:46px">&#128194; Load Saved Results</button>
    </div>
    <div id="cmpResults" style="margin-top:18px;display:none">
      <h3 style="font-size:14px;margin-bottom:10px">&#9878; Comparison Results</h3>
      <div id="cmpTableWrap" style="overflow-x:auto"></div>
      <div id="cmpPaired" style="margin-top:12px;font-size:13px;color:var(--muted)"></div>
    </div>
  </div>

  <!-- BENCHMARK -->
  <div class="card" id="panel-benchmark" style="display:none">
    <h2>&#9733; Agent Benchmark Evaluation</h2>
    <p class="hint">
      <strong>功能注释：</strong>Benchmark 使用固定 case 评估 Harness 行为质量，
      重点看系统是否能达标、拦截非法计划、处理失败、利用 reflection 恢复并遵守实验预算。
    </p>
    <div class="metric-list">
      <div class="metric"><code>target_hit_rate</code> = 达标 case 数 / 总 case 数，衡量目标完成率。</div>
      <div class="metric"><code>planner_success_rate</code> = 计划通过 Guard 的比例，衡量 LLM 与 schema 的契合度。</div>
      <div class="metric"><code>rejected_rate</code> = rejected 记录数 / 全部实验记录，衡量 Guard 拦截强度。</div>
      <div class="metric"><code>runtime_failure_rate</code> = failed 记录数 / 全部实验记录，衡量工具链失败比例。</div>
      <div class="metric"><code>self_correction_count</code> = rejected/failed 后修正成功的次数，衡量自我修正能力。</div>
      <div class="metric"><code>average_experiments_used</code> = 消耗实验数 / case 数，衡量探索效率。</div>
      <div class="metric"><code>average_rounds</code> = 平均轮次；<code>total_prompt_tokens / estimated_cost_usd</code> = LLM 用量与估算成本。</div>
      <div class="metric"><code>best_nmse_db</code> = 全部 case 中最优 NMSE，数值越小越好。</div>
    </div>
    <label for="bmTo">Timeout (seconds)</label><input id="bmTo" type="number" min="1" value="300">
    <label for="bmThr">Threshold (dB)</label><input id="bmThr" type="number" step="0.1" value="-35">
    <div style="display:flex;gap:10px;margin-top:14px">
      <button type="button" class="btn btn-go" id="bmBtn" style="margin-top:0;flex:1">&#9733; Run Benchmark</button>
      <button type="button" class="btn btn-ghost" id="bmLoadBtn" style="margin-top:0;flex:1;min-height:46px">&#128194; Load Saved Results</button>
    </div>
    <div id="bmResults" style="margin-top:18px;display:none">
      <h3 style="font-size:14px;margin-bottom:10px">&#9733; Benchmark Results</h3>
      <div id="bmSummaryWrap"></div>
      <div id="bmTableWrap" style="overflow-x:auto;margin-top:12px"></div>
    </div>
  </div>

</div>

<!-- EVENT VIEWER -->
<div class="card">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:8px">
    <h2 style="margin-bottom:0">Runtime Events</h2>
    <div style="display:flex;align-items:center;gap:12px">
      <button type="button" class="btn btn-stop" id="stopBtn" style="min-height:36px;padding:6px 16px;margin-top:0;width:auto;font-size:13px">&#9724; Stop</button>
      <span style="font-size:13px;color:var(--muted)">Events: <b style="color:var(--blue);font-size:20px" id="evCount">0</b></span>
    </div>
  </div>
  <div class="preview" id="resultPreview">
    <div class="preview-head">
      <h3>Result Preview</h3>
      <a class="lnk" id="psdLink" href="#" target="_blank">Open PSD</a>
    </div>
    <img id="psdPreview" alt="PSD result preview">
    <div class="result-grid">
      <div class="result-chip"><span>current_nmse_db</span><b id="chipNmse">-</b></div>
      <div class="result-chip"><span>baseline_nmse_db</span><b id="chipBase">-</b></div>
      <div class="result-chip"><span>nmse_improvement_db</span><b id="chipGain">-</b></div>
      <div class="result-chip"><span>parameter_count</span><b id="chipParams">-</b></div>
    </div>
    <div class="preview-meta" id="previewMeta" style="padding:0 14px 14px">Waiting for a run that returns psd.png.</div>
  </div>
  <pre class="ev" id="evBox">Ready &mdash; pick a tab, fill the form, press Start.</pre>
  <button type="button" class="btn btn-ghost" id="clearBtn" style="margin-top:14px;width:auto;min-height:38px;padding:8px 18px">Clear Log</button>
</div>
</main>

<script>
(function(){"use strict";
console.log("UI ready");

// Domain display config — updated from agent_start event, defaults to nonlinear
var _domainConfig = {
    metricUnit: "dB",
    metricLowerIsBetter: true,
    artifactPatterns: ["psd.png"],
    displayMetricNames: ["nmse_db","baseline_nmse_db","nmse_improvement_db","parameter_count","final_train_loss"],
    primaryMetric: "nmse_db"
};

var sd=document.getElementById("statusDot"),sl=document.getElementById("statusLabel"),
eb=document.getElementById("evBox"),ec=document.getElementById("evCount"),c=0,
rp=document.getElementById("resultPreview"),pi=document.getElementById("psdPreview"),
pl=document.getElementById("psdLink"),pm=document.getElementById("previewMeta"),
chipNmse=document.getElementById("chipNmse"),chipBase=document.getElementById("chipBase"),
chipGain=document.getElementById("chipGain"),chipParams=document.getElementById("chipParams");
function ss(s){sd.className="dot "+s;sl.textContent=s.charAt(0).toUpperCase()+s.slice(1)}
function al(txt,cls){if(c===0)eb.innerHTML="";eb.innerHTML+='<span class="'+cls+'">'+txt.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")+'</span>\n';c++;ec.textContent=c;eb.scrollTop=eb.scrollHeight}
function ecs(t,obj){if(t==="tool_start"||t==="start"||t==="agent_start"||t==="experiment_start"||t==="round_start")return"ev-running";if(t==="tool_end"||t==="complete"||t==="loop_complete"||t==="experiment_end")return"ev-success";if(t==="error"){var et=(obj||{}).error_type||((obj||{}).payload||{}).error_type||"";if(et==="metric_threshold_error")return"ev-warning";return"ev-failure"}if(t==="experiment_rejected"||t==="cancelled")return"ev-failure";if(t==="metric")return"ev-metric";if(t==="plan_generated")return"ev-planner";if(t==="reflection")return"ev-reflection";if(t==="benchmark_case_start"||t==="benchmark_case_end"||t==="benchmark_complete")return"ev-benchmark";return"ev-info"}

document.querySelectorAll(".tab").forEach(function(t){t.addEventListener("click",function(){
  document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active")});
  t.classList.add("active");var m=t.dataset.tab;
  document.getElementById("panel-workflow").style.display=(m==="workflow")?"":"none";
  document.getElementById("panel-agent").style.display=(m==="agent")?"":"none";
  document.getElementById("panel-benchmark").style.display=(m==="benchmark")?"":"none";
  document.getElementById("panel-compare").style.display=(m==="compare")?"":"none";
  try{history.replaceState(null,"","?tab="+m)}catch(_){}
})});

document.getElementById("agProv").addEventListener("change",function(){
  document.getElementById("noteFake").classList.toggle("on",this.value==="fake");
  document.getElementById("noteDp").classList.toggle("on",this.value==="deepseek");
});
function loadTuneFields(domain){
  var wrap=document.getElementById("agTune");
  wrap.innerHTML="<span style='color:var(--muted);font-size:12px'>loading…</span>";
  fetch("/domains/"+encodeURIComponent(domain)+"/fields").then(function(r){return r.json()}).then(function(data){
    var html="";
    (data.fields||[]).forEach(function(f){
      var vals=(f.values||[]).map(String).slice(0,5).join(", ")+(f.values.length>5?"…":"");
      html+="<label style='display:inline-flex;align-items:center;gap:6px;font-size:12px;margin:0;text-transform:none;letter-spacing:0;color:var(--text);cursor:pointer' title='["+vals+"]'><input type='checkbox' class='tune-f' value='"+f.name+"' checked style='width:auto;margin:0'>"+f.name+"</label>";
    });
    wrap.innerHTML=html;
  }).catch(function(){wrap.innerHTML="<span style='color:var(--red);font-size:12px'>failed to load fields</span>"});
}
document.getElementById("agDom").addEventListener("change",function(){loadTuneFields(this.value)});
document.getElementById("clearBtn").addEventListener("click",function(){eb.textContent="Ready.\n";c=0;ec.textContent="0"});

function ts(s){return new Date(s*1000).toLocaleTimeString("en-GB",{hour:"2-digit",minute:"2-digit",second:"2-digit"})}
function fmtNum(v,d){return typeof v==="number"?v.toFixed(d):"-"}
function artifactUrl(p){return "/artifacts/"+String(p).replace(/\\/g,"/").split("/").map(encodeURIComponent).join("/")}
function maybeShowPreview(metrics,artifacts,source){
  metrics=metrics||{};artifacts=artifacts||[];
  var psd=artifacts.find(function(a){return String(a).replace(/\\/g,"/").toLowerCase().endsWith("psd.png")});
  if(!psd)return;
  var url=artifactUrl(psd)+"?t="+Date.now();
  pi.src=url;pl.href=url;rp.classList.add("on");
  chipNmse.textContent=metrics.nmse_db!=null?fmtNum(Number(metrics.nmse_db),2)+" dB":"-";
  chipBase.textContent=metrics.baseline_nmse_db!=null?fmtNum(Number(metrics.baseline_nmse_db),2)+" dB":"-";
  chipGain.textContent=metrics.nmse_improvement_db!=null?fmtNum(Number(metrics.nmse_improvement_db),2)+" dB":"-";
  chipParams.textContent=metrics.parameter_count!=null?String(metrics.parameter_count):"-";
  pm.textContent="source="+source+" | artifact="+psd;
}
function appendMetrics(out,m,prefix){
  if(!m)return;
  var keys=["nmse_db","baseline_nmse_db","nmse_improvement_db","parameter_count","final_train_loss","model_type","feature_mode","target_mode","mp_order_count","samples","train_samples","epochs"];
  var shown=[];
  keys.forEach(function(k){if(m[k]!=null)shown.push(k+"="+(typeof m[k]==="number"?(k.indexOf("nmse")>=0||k==="final_train_loss"?Number(m[k]).toPrecision(5):m[k]):m[k]))});
  Object.keys(m).sort().forEach(function(k){if(keys.indexOf(k)<0&&m[k]!=null)shown.push(k+"="+m[k])});
  if(shown.length)out.push("  "+prefix+": "+shown.join(" | "));
}
function appendArtifacts(out,arts){
  if(!arts||!arts.length)return;
  out.push("  artifacts:");
  arts.forEach(function(a){out.push("    - "+a)});
}
function fm(obj){
  var root=obj||{},p=root.payload||{},t=root.event_type||root.type||p.type||"",h=root.timestamp?"["+ts(root.timestamp)+"] ":"";
  h+=t+" | source="+(root.session_id||p.session_id||"unknown");if(root.step)h+=" | "+root.step;if(root.tool)h+=" | tool="+root.tool;
  if(root.status&&t!=="metric")h+=" | "+root.status;
  if(root.latency_ms!=null)h+=" | "+Math.round(root.latency_ms)+"ms";
  var out=[h];
  // Update domain config from agent_start event
  if(t==="agent_start"||(t==="start"&&p.display_metric_unit!==undefined)){
    if(p.display_metric_unit!==undefined){
      _domainConfig = {
        metricUnit: p.display_metric_unit || "dB",
        metricLowerIsBetter: p.display_metric_lower_is_better !== false,
        artifactPatterns: p.artifact_preview_patterns || ["psd.png"],
        displayMetricNames: p.display_metric_names || ["nmse_db","baseline_nmse_db","nmse_improvement_db","parameter_count","final_train_loss"],
        primaryMetric: p.primary_metric || "nmse_db"
      };
    }
  }
  if(t==="start"&&p.goal){out.push("  goal: "+p.goal);out.push("  steps: "+p.step_count+" | resume_from_step="+p.resume_from_step)}
  if(t==="tool_start"&&p.args){out.push("  input args: "+JSON.stringify(p.args))}
  if(t==="plan_generated"){
    var causes=p.previous_reflection_failure_causes||root.previous_reflection_failure_causes||[];
    if(causes.length){
      out.push("  previous error reasons:");
      causes.forEach(function(cause){out.push("    - "+cause)})
    }
  }
  if(t==="plan_generated"){
    var facts=p.previous_reflection_facts||root.previous_reflection_facts||[];
    if(facts.length){
    out.push("  previous reflection facts:");
    facts.forEach(function(f){
      var row=[f.id||"unknown",f.status||f.run_status||""];
      if(f.error)row.push("error="+f.error);
      if(f.error_type)row.push("error_type="+f.error_type);
      if(f.nmse_db!=null)row.push("nmse="+Number(f.nmse_db).toFixed(2)+" dB");
      if(f.parameter_count!=null)row.push("params="+f.parameter_count);
      out.push("    - "+row.filter(Boolean).join(" | "))
    })
    }
  }
  if(p.summary||root.summary)out.push((t==="plan_generated"?"  new plan: ":"  plan: ")+(p.summary||root.summary));
  var experiments=p.experiments||root.experiments||[];
  if(experiments.length){experiments.forEach(function(e){out.push("  + "+e.id+(e.reason?" - "+e.reason:""));if(e.overrides){var o=e.overrides,os=[];if(o.model_type)os.push(o.model_type);if(o.memory_depth)os.push("mem="+o.memory_depth);if(o.mp_order_count)os.push("mp="+o.mp_order_count);if(o.hidden_units)os.push("h="+o.hidden_units);if(o.epochs!=null)os.push("ep="+o.epochs);if(os.length)out.push("    "+os.join(" "))}})}
  if(p.id||root.id)out.push("  id: "+(p.id||root.id));
  if(p.round!=null||root.round!=null)out.push("  round: "+(p.round!=null?p.round:root.round));
  if(p.history_count!=null||root.history_count!=null)out.push("  history: "+(p.history_count!=null?p.history_count:root.history_count));
  if(p.reflection){var r=p.reflection,sc=r.status_counts||{};out.push("  facts extracted from round "+r.round+" | OK:"+(sc.succeeded||0)+" FAIL:"+(sc.failed||0)+" REJ:"+(sc.rejected||0));if(r.best_nmse_db!=null)out.push("  best: "+Number(r.best_nmse_db).toFixed(2)+" dB");if(r.failure_causes)r.failure_causes.forEach(function(c){out.push("  cause: "+c)});if(r.facts)r.facts.forEach(function(f){out.push("  fact: "+JSON.stringify(f))})}
  if(p.output){if(p.output.context_summary)out.push("  summary: "+p.output.context_summary);if(p.output.elapsed_seconds)out.push("  elapsed: "+Number(p.output.elapsed_seconds).toFixed(1)+"s");appendMetrics(out,p.output.metrics,"tool metrics");appendArtifacts(out,p.output.artifacts);maybeShowPreview(p.output.metrics,p.output.artifacts,root.tool||t)}
  if(p.metrics){appendMetrics(out,p.metrics,"session metrics");appendArtifacts(out,p.artifacts);maybeShowPreview(p.metrics,p.artifacts,"complete")}
  if(t==="metric"&&p.name&&p.value!=null){var v=p.value,nm=p.name;if(typeof v==="number"){if(nm==="nmse_db")v=Number(v).toFixed(2);else if(nm==="final_train_loss")v=Number(v).toExponential(3);else v=Number(v).toFixed(4)}out.push("  "+nm+" = "+v)}
  if(t==="benchmark_case_start")out.push("  case "+p.case_index+"/"+p.total_cases+": "+p.case_id+" | "+p.goal);
  if(t==="benchmark_case_end")out.push("  case: "+p.case_id+" | hit="+p.target_hit+" | best_nmse="+p.best_nmse_db+" | ok="+p.succeeded+" fail="+p.failed+" rejected="+p.rejected+" | planner_ok="+(p.planner_success_rate!=null?Math.round(p.planner_success_rate*100)+"%":"-")+" corr="+p.self_correction_count);
  if(t==="benchmark_complete"&&p.summary)appendMetrics(out,p.summary,"benchmark summary");
  if(t==="compare_start"){out.push("  protocol: "+p.payload.methods.join(", ")+" | "+p.payload.seeds.length+" seeds x "+p.payload.trial_budget+" trials = "+p.payload.estimated_total_trials)}
  if(t==="strategy_start")out.push("  strategy: "+p.method+" | seed="+p.seed+" | budget="+p.trial_budget+" trials");
  if(t==="trial_done"){out.push("  trial "+p.trial_index+" | "+p.method+" | metric="+(p.metric_value!=null?Number(p.metric_value).toPrecision(4):"n/a")+(p.runtime_failed?" | FAILED":"")+(p.rejected?" | rejected":""))}
  if(t==="trial_rejected")out.push("  trial "+p.trial_index+" | "+p.method+" | REJECTED: "+p.error);
  if(t==="compare_complete"&&p.summary){out.push("  comparison complete: "+p.n_trials+" trials");try{renderCompareSummary(p.summary)}catch(_){}}
  if(root.error)out.push("  ERR: "+root.error.substring(0,200));
  return out.join("\n")
}

var currentSid=null,stopBtn=document.getElementById("stopBtn");
stopBtn.addEventListener("click",function(){
  if(!currentSid)return;
  fetch("/cancel/"+encodeURIComponent(currentSid),{method:"POST"}).catch(function(){});
  stopBtn.style.display="none"
});

async function go(url,body,btn){
  btn.disabled=true;var orig=btn.textContent;btn.textContent="Running...";ss("running");eb.textContent="";c=0;ec.textContent="0";
  // Extract session_id from URL for cancel
  var m=url.match(/\/agent\/([^/]+)\/events|\/runs\/([^/]+)\/events/);
  currentSid=m?(m[1]||m[2]):"benchmark";
  stopBtn.style.display="inline-flex";
  try{
    var resp=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(!resp.ok)throw new Error("HTTP "+resp.status);
    var reader=resp.body.getReader(),decoder=new TextDecoder(),buf="";
    while(true){var part=await reader.read();if(part.done)break;buf+=decoder.decode(part.value,{stream:true});var lines=buf.split("\n");buf=lines.pop()||"";for(var i=0;i<lines.length;i++){var line=lines[i];if(!line.trim()||line.indexOf("event:")===0)continue;if(line.indexOf("data:")===0)try{var parsed=JSON.parse(line.slice(5).trim());al(fm(parsed),ecs(parsed.event_type||parsed.type||"",parsed))}catch(_){al(line.slice(5).trim(),"ev-info")}}}
    ss("done")
  }catch(e){console.error(e);al("ERROR: "+String(e),"ev-failure");ss("error")}
  finally{btn.disabled=false;btn.textContent=orig;stopBtn.style.display="none";currentSid=null}
}

document.getElementById("wfBtn").addEventListener("click",function(){
  var body={goal:document.getElementById("wfGoal").value,epochs:Number(document.getElementById("wfEp").value),nmse_threshold_db:Number(document.getElementById("wfThr").value),timeout_seconds:Number(document.getElementById("wfTo").value)};
  var sid=document.getElementById("wfSid").value.trim()||"ui-demo-001";
  go("/runs/"+encodeURIComponent(sid)+"/events",body,document.getElementById("wfBtn"))
});
document.getElementById("agBtn").addEventListener("click",function(){
  var enabled=[].slice.call(document.querySelectorAll(".tune-f:checked")).map(function(x){return x.value});
  var body={provider:document.getElementById("agProv").value,goal:document.getElementById("agGoal").value,max_rounds:Number(document.getElementById("agRnd").value),max_experiments:Number(document.getElementById("agExp").value),parameter_count_max:Number(document.getElementById("agPm").value),nmse_threshold_db:Number(document.getElementById("agThr").value),timeout_seconds:Number(document.getElementById("agTo").value),artifact_dir:null,domain:document.getElementById("agDom").value,enabled_fields:enabled};
  go("/agent/ui-agent-"+Date.now()+"/events",body,document.getElementById("agBtn"))
});
document.getElementById("bmBtn").addEventListener("click",function(){
  var body={timeout_seconds:Number(document.getElementById("bmTo").value),nmse_threshold_db:Number(document.getElementById("bmThr").value)};
  go("/benchmark/events",body,document.getElementById("bmBtn"))
});
document.getElementById("bmLoadBtn").addEventListener("click",function(){
  document.getElementById("bmResults").style.display="none";
  fetch("/benchmark/summary").then(function(r){return r.json()}).then(function(data){
    if(data.error){al("ERROR: "+data.error,"ev-failure");return}
    renderBenchmarkSummary(data);
    al("Loaded saved benchmark results","ev-success");
  }).catch(function(e){al("ERROR: "+String(e),"ev-failure")});
});
// Load saved comparison results
document.getElementById("cmpLoadBtn").addEventListener("click",function(){
  document.getElementById("cmpResults").style.display="none";
  fetch("/compare/summary").then(function(r){return r.json()}).then(function(data){
    if(data.error){al("ERROR: "+data.error,"ev-failure");return}
    renderCompareSummary(data);
    al("Loaded saved results — "+Object.keys(data.per_method||{}).length+" methods","ev-success");
  }).catch(function(e){al("ERROR: "+String(e),"ev-failure")});
});

document.getElementById("cmpBtn").addEventListener("click",function(){
  document.getElementById("cmpResults").style.display="none";
  var seeds_count=Number(document.getElementById("cmpSeeds").value);
  var body={
    domain:document.getElementById("cmpDom").value,
    workspace:".",
    timeout_seconds:Number(document.getElementById("cmpTo").value),
    parameter_count_max:Number(document.getElementById("cmpPm").value),
    nmse_threshold_db:Number(document.getElementById("cmpThr").value),
    seeds: Array.from({length:seeds_count},function(_,i){return [7,17,29,43,61][i]||(7+i*10)}),
    trial_budget:Number(document.getElementById("cmpBudget").value),
    methods:["random_search","optuna_tpe","llm_direct","llm_program_reflection"],
    plan:document.getElementById("cmpPlan").value
  };
  go("/compare/events",body,document.getElementById("cmpBtn"))
});

// Render strategy comparison summary into the compare panel
function renderCompareSummary(summary){
  var wrap=document.getElementById("cmpTableWrap"),pairedEl=document.getElementById("cmpPaired");
  var pm=summary.per_method||{}, rows=[];
  rows.push("<table class='r-table'><tr><th>Method</th><th>Best Metric (mean)</th><th>95% CI</th><th>Hit Rate</th><th>Planner OK</th><th>Rejected</th><th>Failed</th><th>Effective</th></tr>");
  var metric=""; var m=Object.keys(pm); if(m.length)metric=(pm[m[0]].metric_name||"metric");
  var sorted=Object.keys(pm).sort(function(a,b){
    var va=pm[a]["best_"+metric+"_mean"],vb=pm[b]["best_"+metric+"_mean"];
    return (va==null?1e9:va)-(vb==null?1e9:vb);
  });
  sorted.forEach(function(name){
    var s=pm[name],best=s["best_"+metric+"_mean"],lo=s["best_"+metric+"_ci_95_low"],hi=s["best_"+metric+"_ci_95_high"];
    var hit=s.target_hit_rate_mean!=null?(Number(s.target_hit_rate_mean)*100).toFixed(0)+"%":"-";
    var pso=s.planner_success_rate!=null?(Number(s.planner_success_rate)*100).toFixed(0)+"%":"-";
    var rej=s.rejected_rate_mean!=null?(Number(s.rejected_rate_mean)*100).toFixed(0)+"%":"-";
    var fail=s.runtime_failure_rate_mean!=null?(Number(s.runtime_failure_rate_mean)*100).toFixed(0)+"%":"-";
    var eff=s.n_effective_trials!=null?s.n_effective_trials:"-";
    var bStr=best!=null?Number(best).toPrecision(4):"-";
    var ciStr=(lo!=null&&hi!=null)?"["+Number(lo).toPrecision(3)+", "+Number(hi).toPrecision(3)+"]":"-";
    var css=name==="llm_program_reflection"?"style='color:#34d399;font-weight:700'":"";
    var label=name;
    if(name==="llm_program_reflection")label="llm_program_reflection (程序确定性反思)";
    if(name==="llm_direct")label="llm_direct (LLM 直接决策)";
    rows.push("<tr><td class='mname' "+css+">"+label+"</td><td>"+bStr+"</td><td>"+ciStr+"</td><td>"+hit+"</td><td>"+pso+"</td><td>"+rej+"</td><td>"+fail+"</td><td>"+eff+"</td></tr>");
  });
  rows.push("</table>");
  wrap.innerHTML=rows.join("");
  var paired="";
  var pc=summary.paired_comparisons||{};
  Object.keys(pc).forEach(function(k){
    var d=pc[k];
    if(d.paired_seed_count>0){
      var dm=d[metric+"_delta_mean"];var dl=d[metric+"_delta_ci_95_low"],dh=d[metric+"_delta_ci_95_high"];
      var pname=k.replace(/_/g," ").replace(/program reflection vs direct/,"program reflection vs direct");
      paired+=pname+": paired "+d.paired_seed_count+" seeds, delta="+(dm!=null?Number(dm).toPrecision(3):"-")+
        (dl!=null?" 95%CI ["+Number(dl).toPrecision(3)+", "+Number(dh).toPrecision(3)+"]":"")+
        " — "+(d.significant?"<b style='color:#34d399'>significant</b>":"<span style='color:#fbbf24'>no stable advantage</span>")+"<br>";
    }
  });
  pairedEl.innerHTML=paired;
  document.getElementById("cmpResults").style.display="block";
}

// Render saved benchmark results (10-case) into the benchmark panel
function renderBenchmarkSummary(data){
  var s=data.summary||data, results=data.results||[];
  var wrap=document.getElementById("bmSummaryWrap"),tbl=document.getElementById("bmTableWrap");
  var keys=["case_count","target_hit_rate","planner_success_rate","rejected_rate","runtime_failure_rate","self_correction_count","average_rounds","average_experiments_used","best_nmse_db","total_prompt_tokens","total_completion_tokens","estimated_cost_usd"];
  var html="<div style='display:flex;flex-wrap:wrap;gap:8px'>";
  keys.forEach(function(k){
    var v=s[k];
    if(typeof v==="number"){
      if(k.indexOf("rate")>=0)v=(v*100).toFixed(1)+"%";
      else if(k==="best_nmse_db")v=Number(v).toFixed(2)+" dB";
      else if(k==="estimated_cost_usd")v="$"+Number(v).toFixed(4);
      else v=Number(v).toFixed(2);
    }
    html+="<div class='chip'><span>"+k+"</span><b>"+(v==null?"-":v)+"</b></div>";
  });
  html+="</div>";
  wrap.innerHTML=html;
  if(results.length){
    var t="<table class='r-table'><tr><th>Case</th><th>Hit</th><th>Best NMSE</th><th>OK</th><th>Fail</th><th>Rejected</th><th>Planner OK</th><th>Self-corr</th><th>Tokens</th><th>Cost</th></tr>";
    results.forEach(function(r){
      t+="<tr><td>"+r.case_id+"</td><td>"+(r.target_hit?"&#10003;":"&#10007;")+"</td><td>"+(r.best_nmse_db!=null?Number(r.best_nmse_db).toFixed(2):"-")+"</td><td>"+r.succeeded_count+"</td><td>"+r.failed_count+"</td><td>"+r.rejected_count+"</td><td>"+(r.planner_success_rate!=null?Math.round(r.planner_success_rate*100)+"%":"-")+"</td><td>"+r.self_correction_count+"</td><td>"+((r.total_prompt_tokens||0)+(r.total_completion_tokens||0))+"</td><td>$"+(r.estimated_cost_usd!=null?Number(r.estimated_cost_usd).toFixed(4):"0")+"</td></tr>";
    });
    t+="</table>";
    tbl.innerHTML=t;
  }
  document.getElementById("bmResults").style.display="block";
}
// URL tab support: open a tab via ?tab=workflow|agent|benchmark|compare.
// benchmark/compare auto-load saved results so shared links show data.
(function(){
  var m=(location.search.match(/[?&]tab=([a-z]+)/)||[])[1]||"workflow";
  var t=document.querySelector('.tab[data-tab="'+m+'"]');
  if(t)t.click();
  loadTuneFields(document.getElementById("agDom").value);
  if(m==="compare"&&document.getElementById("cmpLoadBtn"))document.getElementById("cmpLoadBtn").click();
  if(m==="benchmark"&&document.getElementById("bmLoadBtn"))document.getElementById("bmLoadBtn").click();
})();
console.log("UI ready")
})();
</script>
</body>
</html>
"""
