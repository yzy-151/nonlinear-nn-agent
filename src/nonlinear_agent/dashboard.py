from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nonlinear_agent.diagnostics import collect_diagnostics


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
    best_nmse = totals.get("best_nmse_db")
    best_nmse_fmt = f"{best_nmse:.2f} dB" if isinstance(best_nmse, (int, float)) else "-"

    recent_runs = run_rows[:10]
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total_runs = diagnostics.get("run_count", 0)

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
  --radius: 14px;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  min-height:100vh; line-height:1.6; font-size:16px;
  -webkit-font-smoothing: antialiased;
}}
header {{
  background: linear-gradient(135deg, #070e1a 0%, #0f172a 60%, #151e33 100%);
  border-bottom:1px solid var(--border); padding:28px 40px;
}}
header h1 {{ font-size:26px; font-weight:700; letter-spacing:-0.5px; margin-bottom:6px; }}
header p  {{ color: var(--muted); font-size:15px; }}
main {{ padding:28px 40px 44px; display:grid; gap:24px; }}

section {{
  background:var(--card); border:1px solid var(--border);
  border-radius:var(--radius); padding:24px;
  box-shadow:0 2px 8px rgba(0,0,0,.3);
}}
section h2 {{ font-size:18px; font-weight:650; margin-bottom:18px; letter-spacing:-0.3px; }}

table {{ width:100%; border-collapse:collapse; font-size:15px; }}
th, td {{
  border:1px solid var(--border); padding:12px 14px;
  text-align:left; vertical-align:top;
}}
th {{
  background:#0f1a2a; color:var(--muted); font-weight:650;
  font-size:13px; text-transform:uppercase; letter-spacing:.5px;
}}
td {{ color:var(--text); }}
td .good {{ color:var(--green); font-weight:700; }}
td .warn {{ color:var(--amber); }}
td .bad  {{ color:var(--red); font-weight:700; }}
code {{
  font-family:"Cascadia Code","Fira Code",Consolas,monospace;
  font-size:14px; color:var(--accent);
}}

.metrics {{
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap:16px;
}}
.metric {{
  background: var(--card); border:1px solid var(--border);
  border-radius: var(--radius); padding:22px 24px;
  box-shadow:0 2px 8px rgba(0,0,0,.3);
}}
.metric .label {{
  color:var(--muted); font-size:13px; font-weight:700;
  text-transform:uppercase; letter-spacing:.7px; margin-bottom:10px;
}}
.metric .value {{
  font-size:34px; font-weight:700; overflow-wrap:anywhere; color:var(--accent);
}}
.metric .value.good {{ color: var(--green); }}
.metric .value.warn {{ color: var(--amber); }}
.metric .value.bad  {{ color: var(--red); }}

.grid {{
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap:24px;
}}

.run-card {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:16px 20px; margin-bottom:12px;
  display:flex; flex-wrap:wrap; gap:14px 28px; align-items:center;
}}
.run-card .dir {{ font-size:13px; color:var(--muted); min-width:180px; font-family:"Cascadia Code",Consolas,monospace; }}
.run-card .stat {{ font-size:15px; font-weight:650; }}
.run-card .stat.good {{ color:var(--green); }}
.run-card .stat.bad  {{ color:var(--red); }}
.run-card .stat.warn {{ color:var(--amber); }}
.run-card .tag {{
  display:inline-block; padding:3px 10px; border-radius:12px;
  font-size:12px; font-weight:700;
}}
.tag-ok  {{ background:rgba(52,211,153,.15); color:var(--green); }}
.tag-err {{ background:rgba(248,113,113,.15); color:var(--red); }}
.tag-run {{ background:rgba(56,189,248,.15); color:var(--accent); }}

::-webkit-scrollbar {{ width:8px; height:8px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:#2d3b52; border-radius:4px; }}

footer {{
  padding:0 40px 32px; font-size:14px; color:var(--muted);
}}
footer strong {{ color:var(--accent); }}
</style>
</head>
<body>

<header>
  <h1>Agent Runtime Diagnostics</h1>
  <p>{total_runs} planner runs, {diagnostics.get("benchmark_count", 0)} benchmark runs &mdash; <strong>Last updated:</strong> {updated}</p>
</header>

<main>

  <section>
    <h2>Recent Runs (newest first)</h2>
    {_render_recent_runs(recent_runs)}
    {f'<p style="color:var(--muted);margin-top:12px;font-size:14px;">Showing {len(recent_runs)} of {total_runs} total runs. Scroll down for full history.</p>' if total_runs > 10 else ''}
  </section>

  <section>
    <h2>Aggregate Metrics</h2>
    <div class="metrics">
      {_render_metric_cards([
        ("Total Runs", total_runs),
        ("Total Experiments", totals.get("case_count", 0)),
        ("Target Hit Rate", _pct(totals.get("target_hit_rate"))),
        ("Rejected Rate", _pct(totals.get("rejected_rate"))),
        ("Runtime Failures", _pct(totals.get("runtime_failure_rate"))),
        ("Best NMSE (dB)", best_nmse_fmt),
    ])}
    </div>
  </section>

  <section>
    <h2>Best Candidate</h2>
    {_render_key_value_table(best)}
  </section>

  <div class="grid">
    <section>
      <h2>Status Distribution</h2>
      {_render_count_table("status", status_counts)}
    </section>
    <section>
      <h2>Error Types</h2>
      {_render_count_table("error_type", error_type_counts)}
    </section>
  </div>

  <section>
    <h2>Full Run History</h2>
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


# ── helpers ──

def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _render_recent_runs(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return '<p style="color:var(--muted)">No runs yet. Start an Agent Loop to see results here.</p>'
    parts: list[str] = []
    for r in runs:
        source = str(r.get("source", ""))
        status = str(r.get("status", ""))
        best_nmse = r.get("best_nmse_db")
        nmse_str = f"{best_nmse:.2f} dB" if isinstance(best_nmse, (int, float)) else "N/A"
        succ = r.get("succeeded", 0)
        fail = r.get("failed", 0)
        rej = r.get("rejected", 0)
        rounds = r.get("rounds", 0)
        sc = "good" if status == "stopped" else ("warn" if "max_round" in status else "bad")
        tag_cls = "tag-ok" if status == "stopped" else ("tag-run" if "max_round" in status else "tag-err")
        parts.append(
            f'<div class="run-card">'
            f'<div class="dir">{_esc(source)}</div>'
            f'<div class="stat {sc}">NMSE {_esc(nmse_str)}</div>'
            f'<div>Round {_esc(rounds)}</div>'
            f'<div><span class="tag tag-ok">{_esc(succ)} OK</span> '
            f'<span class="tag tag-err">{_esc(fail)} Fail</span> '
            f'<span class="tag tag-run">{_esc(rej)} Rej</span></div>'
            f'<span class="tag {tag_cls}">{_esc(status)}</span>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_metric_cards(metrics: list[tuple[str, Any]]) -> str:
    parts: list[str] = []
    for label, value in metrics:
        css = ""
        ll = label.lower()
        if "target_hit" in ll or "best" in ll:
            css = "good"
        elif "failure" in ll or "rejected" in ll:
            css = "bad" if _is_high(value, label) else "good"
        parts.append(
            f'<div class="metric"><div class="label">{_esc(label)}</div>'
            f'<div class="value {css}">{_esc(value)}</div></div>'
        )
    return "\n".join(parts)


def _is_high(value: Any, label: str) -> bool:
    try:
        v = float(str(value).rstrip("%"))
        return v > 10 if "rate" in label.lower() else v > 5
    except (TypeError, ValueError):
        return False


def _render_key_value_table(values: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><th>{_esc(key)}</th><td><code>{_esc(value)}</code></td></tr>"
        for key, value in values.items()
    )
    return f"<table>{rows}</table>" if rows else '<p style="color:var(--muted)">No data &mdash; run some experiments first.</p>'


def _render_count_table(label: str, counts: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><td>{_esc(key)}</td><td>{_esc(value)}</td></tr>"
        for key, value in sorted(counts.items())
    )
    return (
        f"<table><tr><th>{_esc(label)}</th><th>count</th></tr>{rows}</table>"
        if rows
        else '<p style="color:var(--muted)">No records.</p>'
    )


def _render_rows_table(columns: list[str], rows: list[dict[str, Any]]) -> str:
    header = "".join(f"<th>{_esc(col)}</th>" for col in columns)
    body = "\n".join(
        "<tr>" + "".join(f"<td><code>{_esc(row.get(col, ''))}</code></td>" for col in columns) + "</tr>"
        for row in rows
    )
    return f"<table><tr>{header}</tr>{body}</table>" if rows else '<p style="color:var(--muted)">No records.</p>'


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)
