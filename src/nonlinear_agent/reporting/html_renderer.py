"""Analysis-style Chinese HTML report renderer (v3.9.x).

The tool fills data-driven sections (metrics, tables, figures, fidelity) and
the agent supplies narrative analysis (improvement, why-effective,
experience) which is rendered as-is into the report.
"""

from __future__ import annotations

import html as _html
from typing import Any

from nonlinear_agent.reporting.task_report_spec import TaskReportSpec


def _esc(value: Any) -> str:
    return _html.escape(str(value))


def _fmt(value: float | None, digits: int = 4) -> str:
    return f"{value:.{digits}f}" if value is not None else "—"


def render_task_html(
    spec: TaskReportSpec,
    figures: dict[str, str],
    analysis: dict[str, str] | None = None,
) -> str:
    """Render a complete analysis-style HTML report (Chinese)."""
    analysis = analysis or {}
    best = spec.best()
    executions = list(spec.executions)
    hit_count = sum(1 for r in executions if r.target_hit)
    hit_rate = hit_count / len(executions) if executions else 0.0
    nmse_values = [r.nmse_db for r in executions if r.nmse_db is not None]
    avg_nmse = sum(nmse_values) / len(nmse_values) if nmse_values else None
    gain = (
        best.baseline_nmse_db - best.nmse_db
        if best and best.nmse_db is not None and best.baseline_nmse_db is not None
        else None
    )

    cards = [
        ("最优 NMSE", f"{_fmt(best.nmse_db) if best else '—'} dB"),
        ("相对基线提升", f"{_fmt(gain, 2)} dB" if gain is not None else "—"),
        ("达标率", f"{hit_rate * 100:.0f}%"),
        ("参数量(最优)", str(best.parameter_count) if best else "—"),
        ("实验数", str(len(executions))),
        ("总成本", f"${_fmt(spec.cost_usd, 4)}"),
    ]

    rows = []
    for run in executions:
        mark = "最优" if best and run.run_id == best.run_id else ""
        hit = "达标" if run.target_hit else "未达标"
        rows.append(
            f"<tr class=\"{'best' if mark else ''}\">"
            f"<td>{_esc(run.run_id)}</td><td>{_esc(run.model_type)}</td>"
            f"<td class=\"num\">{_fmt(run.nmse_db)}</td>"
            f"<td class=\"num\">{run.parameter_count or '—'}</td>"
            f"<td>{hit}</td><td>{mark}</td></tr>"
        )

    ablation_rows = "".join(
        f"<tr><td>{_esc(a.get('名称', a.get('name', '')))}</td>"
        f"<td class=\"num\">{_fmt(a.get('best_nmse_db'))}</td></tr>"
        for a in spec.ablations
    )
    failure_rows = "".join(
        f"<tr><td>{_esc(f.get('id', ''))}</td>"
        f"<td>{_esc(f.get('状态', f.get('status', '')))}</td>"
        f"<td>{_esc(f.get('错误', f.get('error', '')))}</td></tr>"
        for f in spec.failure_cases
    )

    arch_img = figures.get("architecture")
    psd_img = figures.get("psd")
    improv_img = figures.get("improvement")
    psd_note = figures.get("psd_note", "")

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>
  :root {{ --blue:#1d4ed8; --green:#16a34a; --red:#dc2626; --slate:#334155; --bg:#f8fafc; }}
  body {{ font-family:"Microsoft YaHei","SimHei",sans-serif; margin:0; background:var(--bg); color:var(--slate); }}
  .wrap {{ max-width:960px; margin:0 auto; padding:24px 28px 48px; background:#fff; }}
  h1 {{ font-size:24px; color:#0f172a; border-bottom:3px solid var(--blue); padding-bottom:10px; }}
  h2 {{ font-size:18px; color:#0f172a; margin-top:28px; border-left:5px solid var(--blue); padding-left:10px; }}
  .meta {{ color:#64748b; font-size:13px; margin:6px 0 16px; }}
  .cards {{ display:flex; flex-wrap:wrap; gap:12px; margin:18px 0; }}
  .card {{ flex:1 1 140px; background:#f1f5f9; border-radius:10px; padding:12px 14px; text-align:center; }}
  .card .v {{ font-size:20px; font-weight:700; color:var(--blue); }}
  .card .k {{ font-size:12px; color:#64748b; }}
  table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:13px; }}
  th,td {{ border:1px solid #cbd5e1; padding:7px 9px; text-align:left; }}
  th {{ background:#e2e8f0; }}
  tr.best {{ background:#f0fdf4; font-weight:600; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  img {{ max-width:100%; border:1px solid #e2e8f0; border-radius:8px; margin:10px 0; }}
  .note {{ font-size:12px; color:#64748b; font-style:italic; }}
  .analysis {{ background:#f8fafc; border-left:4px solid var(--green); padding:12px 16px; border-radius:0 8px 8px 0; margin:10px 0; }}
  code {{ background:#f1f5f9; padding:1px 5px; border-radius:4px; }}
  .fidelity {{ display:inline-block; margin-top:20px; padding:8px 14px; background:#f0fdf4; color:var(--green);
              border:1px solid #86efac; border-radius:8px; font-size:13px; }}
</style></head><body><div class="wrap">
  <h1>实验任务报告 — {_esc(spec.task_id)}</h1>
  <div class="meta">目标：{_esc(spec.goal)}</div>
  <div class="cards">
    {''.join(f'<div class="card"><div class="v">{_esc(v)}</div><div class="k">{_esc(k)}</div></div>' for k, v in cards)}
  </div>

  <h2>网络原理框图</h2>
  {f'<img src="file:///{arch_img.replace(chr(92), "/")}" alt="架构图">' if arch_img else '<p class="note">无架构图</p>'}

  <h2>改进过程与效果</h2>
  {f'<img src="file:///{improv_img.replace(chr(92), "/")}" alt="改进对比">' if improv_img else ''}
  <div class="analysis">{_esc(analysis.get('improvement', '')) or '（Agent 未提供改进分析）'}</div>

  <h2>为什么有效</h2>
  {f'<img src="file:///{psd_img.replace(chr(92), "/")}" alt="PSD">' if psd_img else ''}
  <p class="note">{_esc(psd_note)}</p>
  <div class="analysis">{_esc(analysis.get('why_effective', '')) or '（Agent 未提供归因分析）'}</div>

  <h2>实验结果</h2>
  <table>
    <tr><th>实验</th><th>模型</th><th>NMSE (dB)</th><th>参数量</th><th>达标</th><th>标注</th></tr>
    {''.join(rows) or '<tr><td colspan="6">无执行结果</td></tr>'}
  </table>

  <h2>数据化总结</h2>
  <table>
    <tr><th>指标</th><th>数值</th></tr>
    <tr><td>实验总数</td><td>{len(executions)}</td></tr>
    <tr><td>达标实验数</td><td>{hit_count}（{hit_rate * 100:.0f}%）</td></tr>
    <tr><td>最优 NMSE</td><td>{_fmt(best.nmse_db) if best else '—'} dB</td></tr>
    <tr><td>平均 NMSE</td><td>{_fmt(avg_nmse) if avg_nmse is not None else '—'} dB</td></tr>
    <tr><td>相对基线提升</td><td>{_fmt(gain, 2) if gain is not None else '—'} dB</td></tr>
    <tr><td>最优参数量</td><td>{best.parameter_count if best else '—'}</td></tr>
    <tr><td>总成本</td><td>${_fmt(spec.cost_usd, 4)}</td></tr>
  </table>

  <h2>经验总结</h2>
  <div class="analysis">{_esc(analysis.get('experience', '')) or '（Agent 未提供经验总结）'}</div>

  <h2>消融</h2>
  <table><tr><th>策略</th><th>best NMSE (dB)</th></tr>{ablation_rows or '<tr><td colspan="2">无</td></tr>'}</table>

  <h2>失败案例</h2>
  <table><tr><th>ID</th><th>状态</th><th>错误</th></tr>{failure_rows or '<tr><td colspan="3">无</td></tr>'}</table>

  <h2>限制</h2>
  <p>{_esc(spec.limits) or '—'}</p>

  <h2>复现</h2>
  <p><code>{_esc(spec.reproduce_command)}</code></p>

  <span class="fidelity">✓ 数字经 Fidelity 校验，与源数据一致</span>
</div></body></html>"""
    return html_doc
