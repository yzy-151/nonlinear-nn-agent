"""Print-ready evidence-backed HTML report renderer."""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

from nonlinear_agent.reporting.task_report_spec import TaskReportSpec


def _esc(value: Any) -> str:
    return _html.escape(str(value))


def _fmt(value: float | None, digits: int = 4) -> str:
    return f"{value:.{digits}f}" if value is not None else "—"


def _image(path: str | None, alt: str) -> str:
    if not path:
        return '<div class="missing">No verified figure was supplied.</div>'
    uri = Path(path).resolve().as_uri()
    return f'<img src="{_esc(uri)}" alt="{_esc(alt)}">'


def _narrative_block(narrative: Any, name: str, fallback: str = "") -> str:
    section = narrative.sections.get(name) if narrative is not None else None
    text = section.text if section is not None else fallback
    refs = section.evidence_refs if section is not None else ()
    ref_html = " ".join(f'<span class="ref">{_esc(ref)}</span>' for ref in refs)
    return (
        f'<div class="narrative"><p>{_esc(text) or "—"}</p>'
        f'<div class="refs"><b>Evidence</b> {ref_html or "—"}</div></div>'
    )


def render_task_html(
    spec: TaskReportSpec,
    figures: dict[str, str],
    analysis: dict[str, str] | None = None,
    architecture: Any | None = None,
    narrative: Any | None = None,
) -> str:
    """Render one professional HTML source shared by browser and PDF."""
    analysis = analysis or {}
    executions = list(spec.executions)
    best = spec.best()
    selected = spec.selected()
    hit_count = sum(1 for run in executions if run.target_hit)
    hit_rate = hit_count / len(executions) if executions else 0.0
    nmse_values = [run.nmse_db for run in executions if run.nmse_db is not None]
    average_nmse = sum(nmse_values) / len(nmse_values) if nmse_values else None
    gain = (
        selected.baseline_nmse_db - selected.nmse_db
        if selected and selected.baseline_nmse_db is not None and selected.nmse_db is not None
        else None
    )
    constraint_text = " / ".join(
        f"{_esc(key)}: <b>{_esc(value)}</b>" for key, value in spec.constraints.items()
    ) or "No explicit constraints"

    execution_rows = []
    for run in executions:
        is_best = best is not None and run.run_id == best.run_id
        execution_rows.append(
            f'<tr class="{"best" if is_best else ""}">'
            f'<td><b>{_esc(run.run_id)}</b></td><td>{_esc(run.model_type)}</td>'
            f'<td class="num">{_fmt(run.baseline_nmse_db)}</td>'
            f'<td class="num">{_fmt(run.nmse_db)}</td>'
            f'<td class="num">{run.parameter_count if run.parameter_count is not None else "—"}</td>'
            f'<td>{"PASS" if run.target_hit else "MISS"}</td>'
            f'<td>{"BEST" if is_best else ""}</td></tr>'
        )
    if spec.final_evaluation is not None:
        final = spec.final_evaluation
        execution_rows.append(
            '<tr class="final">'
            f'<td><b>{_esc(final.run_id)}</b></td><td>{_esc(final.model_type)}</td>'
            f'<td class="num">{_fmt(final.baseline_nmse_db)}</td>'
            f'<td class="num">{_fmt(final.nmse_db)}</td>'
            f'<td class="num">{final.parameter_count if final.parameter_count is not None else "—"}</td>'
            f'<td>{"PASS" if final.target_hit else "MISS"}</td><td>FINAL</td></tr>'
        )

    round_cards = []
    for record in spec.round_records:
        round_index = record.get("round_index", "—")
        outcome_rows = []
        for outcome in record.get("outcomes", []):
            metrics = dict(outcome.get("metrics") or {})
            outcome_rows.append(
                f"<tr><td>{_esc(outcome.get('experiment_id', ''))}</td>"
                f"<td>{_esc(outcome.get('candidate_name', ''))}</td>"
                f"<td>{_esc(outcome.get('status', ''))}</td>"
                f"<td class=\"num\">{_fmt(metrics.get('nmse_db'))}</td></tr>"
            )
        incoming = " ".join(
            f'<span class="ref">{_esc(ref)}</span>'
            for ref in record.get("incoming_fact_refs", [])
        ) or "首轮无前序事实"
        extracted = " ".join(
            f'<span class="ref">{_esc(ref)}</span>'
            for ref in record.get("extracted_facts", [])
        ) or "—"
        round_cards.append(
            '<article class="round-card">'
            f'<div class="round-index">ROUND {_esc(round_index)}</div>'
            f'<h3>{_esc(record.get("hypothesis", "未提供假设"))}</h3>'
            f'<p><b>输入事实：</b>{incoming}</p>'
            f'<p><b>Planner 判断：</b>{_esc(record.get("decision_rationale", ""))}</p>'
            '<table><thead><tr><th>Experiment</th><th>Candidate</th><th>Status</th><th>NMSE / dB</th></tr></thead>'
            f'<tbody>{"".join(outcome_rows)}</tbody></table>'
            f'<p><b>Reflection 提取事实：</b>{extracted}</p>'
            f'<p><b>下一步：</b>{_esc(record.get("next_round_intent", ""))}</p>'
            '</article>'
        )

    architecture_rows = []
    if architecture is not None:
        for node in architecture.nodes:
            details = json.dumps(node.details, ensure_ascii=False, sort_keys=True)
            architecture_rows.append(
                f"<tr><td><b>{_esc(node.label)}</b><br><small>{_esc(node.node_id)}</small></td>"
                f"<td>{_esc(node.operation)}</td><td><code>{_esc(details)}</code></td></tr>"
            )
    descriptor_line = (
        f"{architecture.name} / v{architecture.version} / {architecture.training_mode} / "
        f"{len(architecture.nodes)} nodes / {len(architecture.edges)} edges"
        if architecture is not None
        else "ModelDescriptor unavailable"
    )

    ablation_rows = "".join(
        f"<tr><td>{_esc(item.get('名称', item.get('name', '')))}</td>"
        f"<td class=\"num\">{_fmt(item.get('best_nmse_db'))}</td></tr>"
        for item in spec.ablations
    )
    failure_rows = "".join(
        f"<tr><td>{_esc(item.get('id', ''))}</td>"
        f"<td>{_esc(item.get('状态', item.get('status', '')))}</td>"
        f"<td>{_esc(item.get('错误', item.get('error', '')))}</td></tr>"
        for item in spec.failure_cases
    )
    trace_rows = "".join(
        f"<li><code>{_esc(ref)}</code></li>" for ref in spec.trace_refs
    ) or "<li>—</li>"
    code_rows = "".join(
        f"<tr><td><code>{_esc(item.get('file', ''))}</code></td>"
        f"<td>{_esc(item.get('change', ''))}</td></tr>"
        for item in spec.code_changes
    )

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Experiment Evidence Report - {_esc(spec.task_id)}</title>
<style>
  @page {{ size:A4; margin:12mm 13mm 14mm; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; color:#252a2f; background:#e8ecef; font-family:"Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC",Arial,sans-serif; letter-spacing:0; line-height:1.55; }}
  .report {{ width:min(1040px,100%); margin:0 auto; padding:34px 42px 56px; background:#fff; }}
  header {{ border-top:6px solid #168579; border-bottom:1px solid #bdc6cc; padding:20px 0 18px; }}
  .eyebrow {{ color:#168579; font:700 11px/1.2 Arial,sans-serif; text-transform:uppercase; }}
  h1 {{ margin:7px 0 4px; font-size:27px; line-height:1.22; color:#20252a; }}
  .goal {{ margin:0; font-size:14px; color:#505960; }}
  .constraints {{ margin-top:13px; padding-top:10px; border-top:1px solid #e1e5e8; color:#5b646b; font-size:12px; }}
  section {{ margin-top:28px; break-inside:auto; }}
  h2 {{ margin:0 0 12px; padding-bottom:7px; border-bottom:2px solid #20252a; font-size:17px; line-height:1.3; }}
  h3 {{ margin:16px 0 8px; font-size:13px; color:#3d464d; }}
  .narrative {{ border-left:4px solid #e26d4f; padding:8px 0 8px 14px; margin:10px 0 14px; }}
  .narrative p {{ margin:0; font-size:13px; }}
  .refs {{ margin-top:7px; color:#6b747b; font-size:10px; }}
  .ref {{ display:inline-block; border:1px solid #b9c4c8; padding:1px 5px; margin:2px 2px 0 0; border-radius:3px; font-family:Consolas,monospace; }}
  .metrics {{ display:grid; grid-template-columns:repeat(6,1fr); border:1px solid #aeb8bd; margin:20px 0 4px; }}
  .metric {{ min-width:0; padding:10px 8px; border-right:1px solid #d3d9dc; text-align:center; }}
  .metric:last-child {{ border-right:0; }}
  .metric b {{ display:block; color:#168579; font:700 18px/1.2 Arial,sans-serif; overflow-wrap:anywhere; }}
  .metric span {{ display:block; margin-top:4px; color:#687178; font-size:10px; }}
  .figure {{ margin:12px 0 16px; break-inside:avoid; }}
  .figure img {{ display:block; width:100%; max-height:460px; object-fit:contain; border:1px solid #ccd3d7; }}
  .caption {{ margin:5px 0 0; color:#667078; font-size:10px; }}
  .figure-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; align-items:start; }}
  table {{ width:100%; border-collapse:collapse; margin:9px 0 14px; font-size:11px; break-inside:auto; }}
  thead {{ display:table-header-group; }}
  th {{ padding:7px 8px; color:#fff; background:#353d43; text-align:left; font-weight:600; }}
  td {{ padding:7px 8px; border-bottom:1px solid #d8dde0; vertical-align:top; overflow-wrap:anywhere; }}
  tr:nth-child(even) td {{ background:#f4f6f7; }}
  tr.best td {{ background:#e6f4ef; border-bottom-color:#9bcbbd; }}
  tr.final td {{ background:#fff1e8; border-bottom-color:#e6a387; font-weight:600; }}
  .num {{ text-align:right; font-family:Consolas,"Courier New",monospace; font-variant-numeric:tabular-nums; }}
  code {{ font-family:Consolas,"Courier New",monospace; font-size:10px; white-space:pre-wrap; overflow-wrap:anywhere; }}
  small {{ color:#768087; }}
  .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .provenance {{ border-top:1px solid #bdc6cc; padding-top:12px; font-size:11px; }}
  .provenance ul {{ margin:5px 0; padding-left:18px; }}
  .verified {{ display:inline-block; margin-top:16px; padding:4px 7px; border:1px solid #168579; color:#126d64; font:700 10px/1.2 Arial,sans-serif; }}
  .missing {{ padding:25px; border:1px dashed #9fa9af; color:#727c82; text-align:center; }}
  .round-card {{ margin:12px 0 16px; padding:14px 16px; border:1px solid #b9c4c8; border-left:5px solid #168579; break-inside:avoid; }}
  .round-card h3 {{ margin:4px 0 9px; font-size:14px; color:#20252a; }}
  .round-card p {{ margin:7px 0; font-size:11px; }}
  .round-card table {{ margin:9px 0; }}
  .round-index {{ color:#168579; font:700 11px/1.2 Arial,sans-serif; }}
  @media print {{
    body {{ background:#fff; }} .report {{ width:auto; margin:0; padding:0; }}
    .metrics {{ grid-template-columns:repeat(3,1fr); }}
    .metric:nth-child(3n) {{ border-right:0; }}
    h2,h3 {{ break-after:avoid; }}
    .figure, .narrative {{ break-inside:avoid; }}
    a {{ color:inherit; text-decoration:none; }}
  }}
  @media screen and (max-width:760px) {{
    .report {{ padding:22px 18px 40px; }} .metrics {{ grid-template-columns:repeat(2,1fr); }}
    .metric:nth-child(2n) {{ border-right:0; }} .figure-grid,.two-col {{ grid-template-columns:1fr; }}
  }}
</style></head><body><main class="report">
  <header>
    <div class="eyebrow">Evidence-backed experiment report</div>
    <h1>实验任务报告 / {_esc(spec.task_id)}</h1>
    <p class="goal">{_esc(spec.goal)}</p>
    <div class="constraints">{constraint_text}</div>
  </header>

  <div class="metrics">
    <div class="metric"><b>{_fmt(selected.nmse_db) if selected else '—'}</b><span>FINAL NMSE / dB</span></div>
    <div class="metric"><b>{_fmt(gain, 2)}</b><span>GAIN / dB</span></div>
    <div class="metric"><b>{hit_rate * 100:.0f}%</b><span>TARGET HIT RATE</span></div>
    <div class="metric"><b>{selected.parameter_count if selected else '—'}</b><span>FINAL PARAMETERS</span></div>
    <div class="metric"><b>{len(executions)}</b><span>EXECUTIONS</span></div>
    <div class="metric"><b>${_fmt(spec.cost_usd, 4)}</b><span>TOTAL LLM COST</span></div>
  </div>

  <section>
    <h2>01 / 执行摘要</h2>
    {_narrative_block(narrative, 'executive_summary')}
  </section>

  <section>
    <h2>02 / 实际模型架构</h2>
    <div class="caption">ModelDescriptor: {_esc(descriptor_line)}</div>
    <div class="figure">{_image(figures.get('architecture'), 'ModelDescriptor architecture graph')}</div>
    {_narrative_block(narrative, 'architecture_analysis', analysis.get('why_effective', ''))}
    <h3>节点清单</h3>
    <table><thead><tr><th>节点</th><th>操作</th><th>结构参数</th></tr></thead><tbody>
      {''.join(architecture_rows) or '<tr><td colspan="3">Descriptor unavailable</td></tr>'}
    </tbody></table>
  </section>

  <section>
    <h2>03 / 性能证据</h2>
    {_narrative_block(narrative, 'performance_analysis', analysis.get('improvement', ''))}
    <div class="figure-grid">
      <div class="figure">{_image(figures.get('psd'), 'Measured PSD')}<p class="caption">{_esc(figures.get('psd_note', 'Measured experiment PSD'))}</p></div>
      <div class="figure">{_image(figures.get('improvement'), 'Baseline versus current NMSE')}<p class="caption">Baseline and current NMSE are read from execution evidence.</p></div>
    </div>
    <table><thead><tr><th>Run</th><th>Model</th><th>Baseline</th><th>NMSE</th><th>Params</th><th>Target</th><th>Rank</th></tr></thead>
      <tbody>{''.join(execution_rows)}</tbody></table>
    <p class="caption">Average NMSE: {_fmt(average_nmse)} dB / Best gain: {_fmt(gain, 2)} dB / Hit: {hit_count} of {len(executions)}</p>
  </section>

  <section>
    <h2>04 / 模型迭代与决策轨迹</h2>
    {_narrative_block(narrative, 'round_journey')}
    {''.join(round_cards) or '<div class="missing">No round decision evidence was supplied.</div>'}
  </section>

  <section>
    <h2>05 / 失败、反思与经验</h2>
    <div class="two-col">
      <div><h3>Failure analysis</h3>{_narrative_block(narrative, 'failure_analysis')}</div>
      <div><h3>Lessons</h3>{_narrative_block(narrative, 'lessons', analysis.get('experience', ''))}</div>
    </div>
    <table><thead><tr><th>ID</th><th>Status</th><th>Observed fact</th></tr></thead><tbody>
      {failure_rows or '<tr><td colspan="3">No recorded failure.</td></tr>'}
    </tbody></table>
    <h3>Ablation</h3>
    <table><thead><tr><th>Method</th><th>Best NMSE / dB</th></tr></thead><tbody>
      {ablation_rows or '<tr><td colspan="2">No ablation evidence.</td></tr>'}
    </tbody></table>
  </section>

  <section>
    <h2>06 / 代码、Trace 与复现</h2>
    <table><thead><tr><th>File</th><th>Change</th></tr></thead><tbody>
      {code_rows or '<tr><td colspan="2">No code change evidence.</td></tr>'}
    </tbody></table>
    <div class="provenance"><b>Trace references</b><ul>{trace_rows}</ul>
      <b>Reproduce</b><pre><code>{_esc(spec.reproduce_command)}</code></pre></div>
  </section>

  <section>
    <h2>07 / 适用边界</h2>
    {_narrative_block(narrative, 'limitations', spec.limits)}
    <span class="verified">FIDELITY VERIFIED / SOURCE-BOUND NUMBERS</span>
  </section>
</main></body></html>"""
