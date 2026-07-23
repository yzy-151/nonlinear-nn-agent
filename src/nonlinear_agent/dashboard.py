from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from nonlinear_agent.diagnostics import collect_diagnostics


def render_dashboard_html(diagnostics: dict[str, Any]) -> str:
    totals = diagnostics.get("totals", {})
    best = diagnostics.get("best_candidate", {})
    metric_cards = [
        ("case_count", totals.get("case_count", 0)),
        ("target_hit_rate", totals.get("target_hit_rate", 0.0)),
        ("rejected_rate", totals.get("rejected_rate", 0.0)),
        ("runtime_failure_rate", totals.get("runtime_failure_rate", 0.0)),
        ("average_experiments_used", totals.get("average_experiments_used", 0.0)),
        ("best_nmse_db", totals.get("best_nmse_db", "")),
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Runtime Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #667085;
      --line: #c8d0dc;
      --accent: #0f766e;
      --accent-2: #7c3aed;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 28px 36px 18px;
      border-bottom: 2px solid var(--line);
      background: var(--panel);
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.55; }}
    main {{ padding: 24px 36px 40px; display: grid; gap: 20px; }}
    section {{
      background: var(--panel);
      border: 2px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .metric {{
      border: 2px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 86px;
      background: #fbfcfe;
    }}
    .metric .label {{ color: var(--muted); font-size: 13px; }}
    .metric .value {{ margin-top: 8px; font-size: 24px; font-weight: 700; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border: 2px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    code {{ font-family: "Cascadia Mono", Consolas, monospace; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }}
  </style>
</head>
<body>
  <header>
    <h1>Agent Runtime Dashboard</h1>
    <p>Aggregated benchmark and planner-loop diagnostics for evaluating Agent Harness behavior.</p>
  </header>
  <main>
    <section>
      <h2>Aggregate Metrics</h2>
      <div class="metrics">
        {_render_metric_cards(metric_cards)}
      </div>
    </section>
    <section>
      <h2>Best Candidate</h2>
      {_render_key_value_table(best)}
    </section>
    <div class="grid">
      <section>
        <h2>Run Status Distribution</h2>
        {_render_count_table("status", diagnostics.get("status_counts", {}))}
      </section>
      <section>
        <h2>Error Type Distribution</h2>
        {_render_count_table("error_type", diagnostics.get("error_type_counts", {}))}
      </section>
    </div>
    <section>
      <h2>Benchmark Runs</h2>
      {_render_rows_table(["source", "case_count", "target_hit_rate", "best_nmse_db"], diagnostics.get("benchmark_rows", []))}
    </section>
    <section>
      <h2>Planner Loop Runs</h2>
      {_render_rows_table(["source", "status", "rounds", "history_count"], diagnostics.get("run_rows", []))}
    </section>
  </main>
</body>
</html>
"""


def write_dashboard_html(workspace: Path | str, output_path: Path | str | None = None) -> Path:
    root = Path(workspace)
    target = Path(output_path) if output_path else root / "docs" / "diagnostics" / "agent-runtime-dashboard.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_dashboard_html(collect_diagnostics(root)), encoding="utf-8")
    return target


def _render_metric_cards(metrics: list[tuple[str, Any]]) -> str:
    return "\n".join(
        f'<div class="metric"><div class="label">{_escape(label)}</div><div class="value">{_escape(value)}</div></div>'
        for label, value in metrics
    )


def _render_key_value_table(values: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><th>{_escape(key)}</th><td><code>{_escape(value)}</code></td></tr>"
        for key, value in values.items()
    )
    return f"<table>{rows}</table>" if rows else "<p>No candidate data.</p>"


def _render_count_table(label: str, counts: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><td>{_escape(key)}</td><td>{_escape(value)}</td></tr>"
        for key, value in sorted(counts.items())
    )
    return f"<table><tr><th>{_escape(label)}</th><th>count</th></tr>{rows}</table>" if rows else "<p>No records.</p>"


def _render_rows_table(columns: list[str], rows: list[dict[str, Any]]) -> str:
    header = "".join(f"<th>{_escape(column)}</th>" for column in columns)
    body = "\n".join(
        "<tr>" + "".join(f"<td><code>{_escape(row.get(column, ''))}</code></td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<table><tr>{header}</tr>{body}</table>" if rows else "<p>No records.</p>"


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)
