from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nonlinear_agent.diagnostics import collect_diagnostics


def _load_search_summary(workspace: Path) -> dict[str, Any] | None:
    """Try to load search comparison summary if it exists."""
    candidates = [
        workspace / "benchmarks" / "nonlinear-search-v1" / "summary.json",
        workspace / "benchmarks" / "search-smoke" / "summary.json",
    ]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _render_compare_section(summary: dict[str, Any]) -> str:
    """Render a Strategy Comparison section from summary.json data."""
    per_method = summary.get("per_method", {})
    paired = summary.get("paired_comparisons", {})
    rows_html: list[str] = []

    # Per-method table
    header = "<tr><th>Method</th><th>Seeds</th><th>Effective Trials</th><th>Best NMSE (mean)</th><th>Best NMSE (95% CI)</th><th>Target Hit Rate</th><th>Rejected Rate</th><th>Runtime Failure Rate</th></tr>"
    for method, stats in sorted(per_method.items()):
        best_mean = stats.get("best_nmse_db_mean")
        best_lo = stats.get("best_nmse_db_ci_95_low")
        best_hi = stats.get("best_nmse_db_ci_95_high")
        nmse_str = f"{best_mean:.1f} dB" if isinstance(best_mean, (int, float)) else "-"
        ci_str = f"[{best_lo:.1f}, {best_hi:.1f}]" if isinstance(best_lo, (int, float)) and isinstance(best_hi, (int, float)) else "-"
        hit = stats.get("target_hit_rate_mean")
        hit_str = f"{float(hit)*100:.0f}%" if isinstance(hit, (int, float)) else "-"
        rej = stats.get("rejected_rate_mean")
        rej_str = f"{float(rej)*100:.0f}%" if isinstance(rej, (int, float)) else "-"
        fail = stats.get("runtime_failure_rate_mean")
        fail_str = f"{float(fail)*100:.0f}%" if isinstance(fail, (int, float)) else "-"
        rows_html.append(
            f"<tr><td><code>{method}</code></td>"
            f"<td>{stats.get('n_seeds', '-')}</td>"
            f"<td>{stats.get('n_effective_trials', '-')}</td>"
            f"<td class='good'>{nmse_str}</td><td>{ci_str}</td>"
            f"<td>{hit_str}</td><td>{rej_str}</td><td>{fail_str}</td></tr>"
        )

    # Paired comparisons
    paired_html = ""
    for name, delta in paired.items():
        n = delta.get("paired_seed_count", 0)
        mean_d = delta.get("nmse_delta_mean_db")
        lo_d = delta.get("nmse_delta_ci_95_low")
        hi_d = delta.get("nmse_delta_ci_95_high")
        sig = delta.get("significant", False)
        paired_html += (
            f'<div class="metric-note">'
            f"<strong>{name}:</strong> paired {n} seeds, "
            f"mean delta = {mean_d:.1f} dB "
            f"95% CI [{lo_d:.1f}, {hi_d:.1f}] — "
            f"{'&#10003; significant' if sig else '&#9888; no observed stable advantage'}"
            f"</div>"
        )

    return f"""
    <section>
      <h2>Strategy Comparison</h2>
      <p class="desc">
        4 methods x {summary.get('bootstrap_seed', '-')} bootstrap seed,
        {summary.get('bootstrap_samples', '-')} resamples,
        {summary.get('confidence_level', 0.95)*100:.0f}% confidence.
        Data from <code>benchmarks/*/summary.json</code>.
      </p>
      <table>{header}{''.join(rows_html)}</table>
      <div class="metric-notes">{paired_html}</div>
    </section>"""


def render_dashboard_html(diagnostics: dict[str, Any]) -> str:
    totals = diagnostics.get("totals", {})
    best_raw = diagnostics.get("best_candidate", {})
    best: dict[str, Any] = {}
    for k, v in best_raw.items():
        if k == "nmse_db" and isinstance(v, (int, float)):
            best[k] = f"{v:.2f} dB"
        else:
            best[k] = v
    status_counts: dict[str, Any] = diagnostics.get("status_counts", {})
    error_type_counts: dict[str, Any] = diagnostics.get("error_type_counts", {})
    benchmark_rows: list[dict[str, Any]] = diagnostics.get("benchmark_rows", [])
    run_rows: list[dict[str, Any]] = diagnostics.get("run_rows", [])
    run_t = diagnostics.get("run_totals", {})
    bench_t = diagnostics.get("benchmark_totals", {})
    recent_runs = run_rows[:10]
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total_runs = diagnostics.get("run_count", 0)
    total_bench = diagnostics.get("benchmark_count", 0)
    search_summary = _load_search_summary(Path(diagnostics.get("workspace", ".")))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Agent Runtime Dashboard</title>
<style>
:root {{
  --bg: #030712; --surface: #0a0f1c; --card: #111827; --border: #1f2937;
  --text: #e5e7eb; --muted: #6b7280; --accent: #22d3ee; --accent2: #6366f1;
  --green: #10b981; --red: #ef4444; --amber: #f59e0b; --radius: 8px;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  min-height:100vh; line-height:1.6; font-size:16px;
  -webkit-font-smoothing: antialiased;
}}
body::before {{
  content:""; position:fixed; inset:0; z-index:0; opacity:.025;
  background-image: radial-gradient(circle at 15% 40%, #22d3ee 1px, transparent 1px),
                    radial-gradient(circle at 75% 60%, #6366f1 1px, transparent 1px);
  background-size: 50px 50px, 70px 70px; pointer-events:none;
}}
header {{
  position:relative; z-index:1;
  background: linear-gradient(135deg, rgba(15,23,42,.95) 0%, rgba(30,41,59,.9) 100%);
  backdrop-filter:blur(20px); border-bottom:1px solid var(--border); padding:24px 40px;
}}
header h1 {{ font-size:24px; font-weight:700; letter-spacing:-0.5px; margin-bottom:6px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
header p  {{ color: var(--muted); font-size:14px; -webkit-text-fill-color:var(--muted); }}
main {{ position:relative; z-index:1; padding:28px 40px 44px; display:grid; gap:24px; }}

section {{
  background:linear-gradient(135deg, rgba(17,24,39,.9), rgba(15,23,42,.8));
  border:1px solid var(--border); border-radius:var(--radius); padding:24px;
  box-shadow:0 4px 16px rgba(0,0,0,.4); backdrop-filter:blur(10px);
}}
section h2 {{ font-size:17px; font-weight:650; margin-bottom:16px; letter-spacing:-0.3px; }}
section p.desc {{ color:var(--muted); font-size:12px; margin-bottom:14px; line-height:1.5; }}
section p.desc code {{ font-family:"Cascadia Code",Consolas,monospace; font-size:12px; color:var(--accent); }}
.metric-notes {{ display:grid; gap:8px; margin-top:14px; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
.metric-note {{ border:1px solid var(--border); border-radius:8px; padding:10px 12px; background:rgba(15,23,42,.72); color:var(--muted); font-size:12px; }}
.metric-note code {{ color:var(--accent); font-weight:700; }}

table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th, td {{ border:1px solid var(--border); padding:12px 14px; text-align:left; vertical-align:top; }}
th {{ background:rgba(15,23,42,.6); color:var(--muted); font-weight:650; font-size:12px; text-transform:uppercase; letter-spacing:.5px; }}
td {{ color:var(--text); }}
td .good {{ color:var(--green); font-weight:700; }} td .warn {{ color:var(--amber); }} td .bad {{ color:var(--red); font-weight:700; }}
code {{ font-family:"Cascadia Code","Fira Code",Consolas,monospace; font-size:14px; color:var(--accent); }}

.metrics {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; }}
.metric {{
  background:linear-gradient(135deg, rgba(17,24,39,.9), rgba(15,23,42,.8));
  border:1px solid var(--border); border-radius:var(--radius); padding:22px 24px;
  box-shadow:0 4px 16px rgba(0,0,0,.4); backdrop-filter:blur(10px);
  transition:border-color .2s;
}}
.metric:hover {{ border-color:var(--accent); }}
.metric .label {{ color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; margin-bottom:10px; }}
.metric .value {{ font-size:32px; font-weight:700; overflow-wrap:anywhere; color:var(--accent); }}
.metric .value.good {{ color: var(--green); }} .metric .value.warn {{ color: var(--amber); }} .metric .value.bad {{ color: var(--red); }}

.grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap:24px; }}

.run-card {{
  background:linear-gradient(135deg, rgba(10,15,28,.8), rgba(17,24,39,.6));
  border:1px solid var(--border); border-radius:var(--radius);
  padding:16px 20px; margin-bottom:12px;
  display:flex; flex-wrap:wrap; gap:14px 28px; align-items:center;
  transition:border-color .2s;
}}
.run-card:hover {{ border-color:var(--accent); }}
.run-card .dir {{ font-size:13px; color:var(--muted); min-width:180px; font-family:"Cascadia Code",Consolas,monospace; }}
.run-card .stat {{ font-size:15px; font-weight:650; }}
.run-card .stat.good {{ color:var(--green); }} .run-card .stat.bad {{ color:var(--red); }} .run-card .stat.warn {{ color:var(--amber); }}
.run-card .tag {{ display:inline-block; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:700; }}
.tag-ok {{ background:rgba(16,185,129,.12); color:var(--green); }}
.tag-err {{ background:rgba(239,68,68,.12); color:var(--red); }}
.tag-run {{ background:rgba(34,211,238,.12); color:var(--accent); }}

::-webkit-scrollbar {{ width:7px; height:7px; }} ::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:#1e293b; border-radius:4px; }} ::-webkit-scrollbar-thumb:hover {{ background:#334155; }}

footer {{ position:relative; z-index:1; padding:0 40px 32px; font-size:13px; color:var(--muted); }}
footer strong {{ color:var(--accent); }}
</style>
</head>
<body>

<header>
  <h1>Agent Runtime Diagnostics</h1>
  <p>{total_runs} planner runs, {total_bench} benchmark runs &mdash; <strong>Last updated:</strong> {updated}</p>
</header>

<main>

  <section>
    <h2>Recent Runs (newest first)</h2>
    {_render_recent_runs(recent_runs)}
    {f'<p style="color:var(--muted);margin-top:12px;font-size:14px;">Showing {len(recent_runs)} of {total_runs} total runs. Scroll down for full history.</p>' if total_runs > 10 else ''}
  </section>

  <section>
    <h2>Agent Loop Metrics ({total_runs} runs)</h2>
    <p class="desc">
      数据来自 <code>runs/*/result.json</code>（目前 {total_runs} 个文件）。每次 Agent Loop 结束时自动写入。
      计算方法：扫描全部 runs 目录 → 解析每条实验记录的 run_status 和 nmse_db → 汇总统计。
    </p>
    <div class="metrics">
      {_render_metric_cards([
        ("Total Runs", total_runs), ("Total Experiments", run_t.get("case_count", 0)),
        ("Target Hit Rate", _pct(run_t.get("target_hit_rate"))),
        ("Rejected Rate", _pct(run_t.get("rejected_rate"))),
        ("Runtime Failures", _pct(run_t.get("runtime_failure_rate"))),
        ("Best NMSE (dB)", _fmt_nmse(run_t.get("best_nmse_db"))),
    ])}
    </div>
  </section>

  <section>
    <h2>Benchmark Metrics ({total_bench} runs)</h2>
    <p class="desc">
      数据来自 <code>benchmarks/*/results.json</code>（目前 {total_bench} 个文件）。
      Benchmark 用 FakeLLM（固定 plan）+ 真 Runtime 执行，评估系统应对非法计划、失败处理等场景的能力。
    </p>
    <div class="metrics">
      {_render_metric_cards([
        ("Benchmark Cases", bench_t.get("case_count", 0)),
        ("Target Hit Rate", _pct(bench_t.get("target_hit_rate"))),
        ("Rejected Rate", _pct(bench_t.get("rejected_rate"))),
        ("Runtime Failures", _pct(bench_t.get("runtime_failure_rate"))),
        ("Best NMSE (dB)", _fmt_nmse(bench_t.get("best_nmse_db"))),
    ])}
    </div>
    <div class="metric-notes">
      <div class="metric-note">target_hit_rate = hit cases / total cases.</div>
      <div class="metric-note">rejected_rate = rejected records / all experiment records.</div>
      <div class="metric-note">runtime_failure_rate = failed records / all experiment records.</div>
      <div class="metric-note">average_experiments_used = experiments used / case count.</div>
      <div class="metric-note">best_nmse_db = best NMSE across all benchmark cases; lower is better.</div>
    </div>
  </section>

  <section>
    <h2>Best Candidate</h2>
    <p class="desc">来源：遍历全部 runs + benchmarks 中所有实验记录，选 NMSE 最低的一条。</p>
    {_render_key_value_table(best)}
  </section>

  {"<!-- No search comparison data -->" if not search_summary else _render_compare_section(search_summary)}

  <div class="grid">
    <section>
      <h2>Status Distribution</h2>
      <p class="desc">来源：全部 runs 中每条实验记录的 run_status 字段计数。</p>
      {_render_count_table("status", status_counts)}
    </section>
    <section>
      <h2>Error Types</h2>
      <p class="desc">来源：全部 runs 中每条实验记录的 error_type 字段 + reflection 中的 error_type_counts 汇总。</p>
      {_render_count_table("error_type", error_type_counts)}
    </section>
  </div>

  <section>
    <h2>Full Run History</h2>
    <p class="desc">来源：遍历 <code>runs/*/result.json</code>，按文件修改时间倒序排列（最新的在最上面）。</p>
    {_render_rows_table(["source","status","rounds","best_nmse_db","succeeded","failed","rejected"], run_rows)}
  </section>

</main>

<footer>
  <strong>Last updated:</strong> {updated} &mdash; Dashboard auto-refreshes after each Agent Loop. Ctrl+Shift+R if stale.
</footer>
</body>
</html>
"""


def write_dashboard_html(workspace: Path | str, output_path: Path | str | None = None) -> Path:
    root = Path(workspace)
    target = Path(output_path) if output_path else root / "docs" / "diagnostics" / "agent-runtime-dashboard.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_dashboard_html(collect_diagnostics(root)), encoding="utf-8")
    return target


def _fmt_nmse(value: Any) -> str:
    if isinstance(value, (int, float)): return f"{value:.2f} dB"
    return str(value) if value is not None else "-"

def _pct(value: Any) -> str:
    try: return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError): return str(value)

def _render_recent_runs(runs: list[dict[str, Any]]) -> str:
    if not runs: return '<p style="color:var(--muted)">No runs yet. Start an Agent Loop to see results here.</p>'
    parts: list[str] = []
    for r in runs:
        source = str(r.get("source", "")); status = str(r.get("status", ""))
        best_nmse = r.get("best_nmse_db")
        nmse_str = f"{best_nmse:.2f} dB" if isinstance(best_nmse, (int, float)) else "N/A"
        succ, fail, rej = r.get("succeeded", 0), r.get("failed", 0), r.get("rejected", 0)
        sc = "good" if status == "stopped" else ("warn" if "max_round" in status else "bad")
        tc = "tag-ok" if status == "stopped" else ("tag-run" if "max_round" in status else "tag-err")
        parts.append(
            f'<div class="run-card"><div class="dir">{_esc(source)}</div>'
            f'<div class="stat {sc}">NMSE {_esc(nmse_str)}</div><div>Round {_esc(r.get("rounds",0))}</div>'
            f'<div><span class="tag tag-ok">{_esc(succ)} OK</span> <span class="tag tag-err">{_esc(fail)} Fail</span> '
            f'<span class="tag tag-run">{_esc(rej)} Rej</span></div><span class="tag {tc}">{_esc(status)}</span></div>'
        )
    return "\n".join(parts)

def _render_metric_cards(metrics: list[tuple[str, Any]]) -> str:
    parts: list[str] = []
    for label, value in metrics:
        css = ""; ll = label.lower()
        if "target_hit" in ll or "best" in ll: css = "good"
        elif "failure" in ll or "rejected" in ll: css = "bad" if _is_high(value, label) else "good"
        parts.append(f'<div class="metric"><div class="label">{_esc(label)}</div><div class="value {css}">{_esc(value)}</div></div>')
    return "\n".join(parts)

def _is_high(value: Any, label: str) -> bool:
    try:
        v = float(str(value).rstrip("%"))
        return v > 10 if "rate" in label.lower() else v > 5
    except (TypeError, ValueError): return False

def _render_key_value_table(values: dict[str, Any]) -> str:
    rows = "\n".join(f"<tr><th>{_esc(key)}</th><td><code>{_esc(value)}</code></td></tr>" for key, value in values.items())
    return f"<table>{rows}</table>" if rows else '<p style="color:var(--muted)">No data &mdash; run some experiments first.</p>'

def _render_count_table(label: str, counts: dict[str, Any]) -> str:
    rows = "\n".join(f"<tr><td>{_esc(key)}</td><td>{_esc(value)}</td></tr>" for key, value in sorted(counts.items()))
    return f"<table><tr><th>{_esc(label)}</th><th>count</th></tr>{rows}</table>" if rows else '<p style="color:var(--muted)">No records.</p>'

def _render_rows_table(columns: list[str], rows: list[dict[str, Any]]) -> str:
    header = "".join(f"<th>{_esc(col)}</th>" for col in columns)
    body = "\n".join("<tr>" + "".join(f"<td><code>{_esc(row.get(col, ''))}</code></td>" for col in columns) + "</tr>" for row in rows)
    return f"<table><tr>{header}</tr>{body}</table>" if rows else '<p style="color:var(--muted)">No records.</p>'

def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)
