"""Static, offline SVG/HTML presentation of source-grounded report findings."""
from __future__ import annotations

import html

from .learning_report import SCHEMA, S_NAMES

def _h(value):
    return html.escape(str(value), quote=True)


COLORS = ("#3978D5", "#8862C4", "#DB8B37", "#247F78", "#C15C79", "#6B78B6")


def _short(value):
    return str(value)[:9] if value else "unknown"


def _status_tone(value):
    return ("bad" if str(value).startswith("OBSERVED") else
            "unknown" if value in ("NOT_MEASURED", "NOT_APPLICABLE") else "good")


def _chart(history, target, *, width=1050, height=225, max_points=240,
           legend=True):
    """Offline SVG with cohort-separated lines, evidenced score bands and tooltips."""
    pts = [exam for exam in history if target in exam.totals][-max_points:]
    if not pts:
        return '<p class="muted">No compatible examination data.</p>'
    top, bottom, left, right = 22, 42 if legend else 28, 54, 16
    dw, dh = width-left-right, height-top-bottom
    start, end = min(p.step for p in pts), max(p.step for p in pts)
    span = max(1, end-start)
    def x(p):
        return left + (p.step-start)/span*dw
    def y(pct):
        return top + (1-pct)*dh
    cohorts = list(dict.fromkeys(p.cohort for p in pts))
    palette = {cohort: COLORS[i % len(COLORS)] for i, cohort in enumerate(cohorts)}
    data = [f'<svg viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="{_h(target)} examination percentage by optimizer step; '
            'each cohort has separate line segments">']
    # Pale visual score bands are explicitly descriptive, not statistical tests.
    data.append(f'<rect x="{left}" y="{top}" width="{dw}" height="{dh*.1:.2f}" fill="#e1f5e9"/>')
    data.append(f'<rect x="{left}" y="{y(.65):.2f}" width="{dw}" '
                f'height="{y(0)-y(.65):.2f}" fill="#fff0ed"/>')
    for pct in (0, .25, .5, .65, .75, .9, 1):
        yy = y(pct)
        data.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{left+dw}" y2="{yy:.2f}" '
                    'stroke="#dbe3eb" stroke-width=".8"/>')
        if pct in (0, .5, 1):
            data.append(f'<text x="{left-8}" y="{yy+4:.2f}" text-anchor="end" '
                        f'class="tick">{pct*100:.0f}%</text>')
    if end == start:
        ticks = (start,)
    else:
        ticks = tuple(round(start+i*(end-start)/4) for i in range(5))
    for step in dict.fromkeys(ticks):
        xx = left+(step-start)/span*dw
        data.append(f'<text x="{xx:.2f}" y="{top+dh+17:.2f}" text-anchor="middle" '
                    f'class="tick">{step:,}</text>')
    # End one line at every cohort boundary: do not depict two different
    # questions as one continuous measured trajectory.
    segments = []
    segment = []
    previous = None
    for exam in pts:
        if previous and exam.cohort != previous.cohort:
            segments.append(segment)
            segment = []
            xx = x(exam)
            data.append(f'<line x1="{xx:.2f}" y1="{top}" x2="{xx:.2f}" '
                        f'y2="{top+dh}" stroke="#b95e49" stroke-dasharray="3 5" '
                        'stroke-width="1.5" opacity=".7"/>')
        segment.append(exam)
        previous = exam
    if segment:
        segments.append(segment)
    for segment in segments:
        cohort = segment[0].cohort
        path = " ".join(f'{x(p):.2f},{y(p.totals[target][0]/p.totals[target][1]):.2f}'
                        for p in segment)
        if len(segment) > 1:
            data.append(f'<polyline points="{path}" fill="none" '
                        f'stroke="{palette[cohort]}" stroke-width="2.2" '
                        'stroke-linecap="round" stroke-linejoin="round" opacity=".85"/>')
    for p in pts:
        correct, total = p.totals[target]
        pct = correct/total
        color = "#24936C" if pct >= .9 else "#C74C47" if pct <= .65 else palette[p.cohort]
        title = (f'{target}: {correct}/{total} ({100*pct:.1f}%) · step {p.step} '
                 f'· cohort {_short(p.cohort)} · event line {p.line} · student {_short(p.student)}')
        data.append(f'<circle cx="{x(p):.2f}" cy="{y(pct):.2f}" r="3.3" '
                    f'fill="{color}" stroke="#fff" stroke-width=".8"><title>{_h(title)}</title></circle>')
    if legend:
        text = ", ".join(_short(c) for c in cohorts[-4:])
        data.append(f'<text x="{left}" y="{height-3}" class="legend">'
                    f'cohorts (separate lines): {_h(text)} · green ≥90%, red ≤65% (visual bands)</text>')
    data.append('</svg>')
    return "".join(data)


def _metric_table(report):
    rows = []
    for record in report["scope_contrasts"]:
        target = record["target"]
        if target == "ALL":
            continue
        difference = record["difference"]
        old_score = f'{record["best_correct"]}/{record["best_total"]}'
        new_score = f'{record["last_correct"]}/{record["last_total"]}'
        relation = ("SAME COHORT" if record["evidence_class"] == "SAME_SOURCE_COHORT" else
                    "CHANGED COHORT · NOT PAIRED")
        rows.append(f'<tr><td><strong>{_h(target)}</strong></td>'
                    f'<td>{old_score} at {record["best_step"]:,}</td>'
                    f'<td>{new_score} at {record["last_step"]:,}</td>'
                    f'<td class="{ "negative" if difference>0 else "positive" }">'
                    f'{-difference:+.1f} pp</td><td>{_h(relation)}</td>'
                    f'<td class="mono">{record["best_line"]} → {record["last_line"]}</td></tr>')
    return "".join(rows)


def _alert_table(alerts):
    rows = []
    for record in alerts[:40]:
        kind = "Paired regression" if record["paired"] else "Cohort discontinuity"
        tag = "bad" if record["paired"] else "unknown"
        old = f'{record["before"]}/{record["total"]}'
        new = f'{record["after"]}/{record["after_total"]}'
        data = (f'{_short(record["cohort_before"])} → {_short(record["cohort_after"])}')
        hint = ("SAME STUDENT: examination questions changed" if record["same_student"] else
                f'{record["accepted_visits"]} accepted, {record["rejected_visits"]} rejected visits in interval')
        rows.append(f'<tr><td><span class="pill {tag}">{kind}</span></td>'
                    f'<td><strong>{_h(record["target"])}</strong></td>'
                    f'<td>{old} → {new} <b class="negative">'
                    f'(−{record["percentage_points"]:.1f} pp)</b></td>'
                    f'<td>{record["start_step"]:,} → {record["end_step"]:,}</td>'
                    f'<td class="mono">{_h(data)}<span class="muted"> · events '
                    f'{record["start_line"]}–{record["end_line"]}</span></td>'
                    f'<td>{_h(hint)}</td></tr>')
    return "".join(rows)


def _signals_table(report):
    rows = []
    latest = report["signals"]["latest"]
    for kind in S_NAMES:
        found = [v for v in latest if v["signal"] == kind]
        observed = [v for v in found if str(v["status"]).startswith("OBSERVED")]
        not_measured = [v for v in found if v["status"] == "NOT_MEASURED"]
        summary = ", ".join(_h(v["target"]) for v in observed[-7:]) or "No active observation"
        rows.append(f'<tr><td><strong>{_h(S_NAMES[kind])}</strong></td>'
                    f'<td>{len(observed)}</td><td>{len(not_measured)}</td>'
                    f'<td>{summary}</td></tr>')
    return "".join(rows)


def _teacher_table(teacher):
    return "".join(
        f'<tr><td><strong>{_h(t["target"])}</strong></td>'
        f'<td>{t["attempts"]}</td><td>{t["accepted"]}</td>'
        f'<td>{t["rejected"]}</td><td>{t["retained_optimizer_updates"]}</td>'
        f'<td>{t["no_old_delivery_receipt"]}</td>'
        f'<td>{_h(t["top_rejection"] or "—")}</td>'
        f'<td>{"STALLED" if t["zero_acceptance_stall"] else "—"}</td></tr>'
        for t in teacher[:24])


def _clue_table(clues):
    return "".join(
        '<tr><td><strong>' + _h(clue["kind"].replace("_", " ")) + '</strong></td>'
        '<td>' + _h(clue["target"]) + '</td>'
        '<td>' + _h(clue["evidence"]) + '</td>'
        '<td>' + _h(clue["interpretation"]) + '</td>'
        f'<td class="mono">{clue["line"]}</td></tr>' for clue in clues)


def render_html(report, *, max_points=240):
    history = report["_exam_history"]
    title = "Bilqis · Learning diagnostics"
    latest = report["latest_scores"]
    badges = []
    grades = sorted(k for k in latest if "." not in k and k != "ALL")
    for grade in grades:
        if grade in latest:
            badges.append(f'<div class="stat"><span>Grade {grade}</span>'
                          f'<strong>{latest[grade]["correct"]}/{latest[grade]["total"]}</strong>'
                          f'<small>{100*latest[grade]["correct"]/latest[grade]["total"]:.1f}% latest</small></div>')
    if "ALL" in latest:
        badges.append(f'<div class="stat"><span>Whole student</span>'
                      f'<strong>{latest["ALL"]["correct"]}/{latest["ALL"]["total"]}</strong>'
                      '<small>One current examination</small></div>')
    charts = []
    for grade in (*grades, "ALL"):
        if grade in latest:
            charts.append(f'<section class="chart-card"><h3>{_h(grade if grade != "ALL" else "All admitted grades")}'
                          '</h3><p class="muted">Correct / applicable total, normalized to percentage. '
                          'Cohort changes interrupt the line.</p>'
                          +_chart(history, grade, max_points=max_points)+ '</section>')
    capability_charts = []
    for target in sorted((x for x in latest if "." in x)):
        score = latest[target]
        s = f'{score["correct"]}/{score["total"]}'
        capability_charts.append(f'<div class="mini"><div class="mini-title"><strong>{_h(target)}</strong>'
                                 f'<span>{s}</span></div>'
                                 + _chart(history, target, width=475, height=145,
                                          max_points=max_points, legend=False) + '</div>')
    src = report["source"]
    warnings = "".join(f'<li>{_h(w)}</li>' for w in src["warnings"]) or "<li>No parser/custody warnings observed.</li>"
    severe = [f for f in report["alerts"] if f["target"] in ("A", "B", "C", "ALL")]
    lead = severe[0] if severe else None
    spotlight = (f'<div class="spotlight"><span class="eyebrow">AUTOMATICALLY DETECTED</span>'
                 f'<h2>{_h(lead["target"])}: {lead["before"]}/{lead["total"]} → '
                 f'{lead["after"]}/{lead["after_total"]}</h2>'
                 f'<p>{_h(lead["classification"].replace("_", " "))} · '
                 f'optimizer steps {lead["start_step"]:,} → {lead["end_step"]:,}. '
                 f'{_h(lead["note"])}</p></div>' if lead else
                 '<div class="spotlight"><h2>No score-gap episode exceeded the reporting threshold.</h2></div>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_h(title)}</title><style>
:root{{--ink:#1a3042;--muted:#60778a;--paper:#f5f8fa;--card:#fff;--line:#dce5eb;--red:#af3b35;--teal:#247968;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.48 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.page{{max-width:1260px;margin:auto;padding:44px 34px 90px}} h1{{margin:4px 0 9px;font-size:clamp(31px,4vw,49px);letter-spacing:-.045em;line-height:1.07}} h2{{font-size:24px;letter-spacing:-.025em;margin:0 0 10px}} h3{{margin:0;font-size:19px}}
p{{margin:8px 0 13px}} .eyebrow{{font-size:12px;font-weight:750;letter-spacing:.16em;color:#3978a2}}.muted{{color:var(--muted)}}.lede{{font-size:17px;max-width:850px;color:#455f70}}
.top{{border-top:4px solid #316f91;padding-top:27px}}.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:27px 0}}.stat{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px 19px;display:flex;flex-direction:column}}.stat span{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:650}}.stat strong{{font-size:32px;letter-spacing:-.04em}}.stat small{{color:var(--muted)}}
.spotlight{{border-left:5px solid #c95e4e;background:#fff1ea;padding:19px 24px;border-radius:0 14px 14px 0;margin:18px 0 33px}}.spotlight h2{{font-size:28px}}.spotlight p{{color:#6f514b}}
section{{margin:34px 0}}.section-lead{{max-width:980px;color:var(--muted)}}.chart-grid{{display:grid;grid-template-columns:1fr;gap:14px}}.chart-card,.mini{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px 18px}}.chart-card svg,.mini svg{{width:100%;height:auto;display:block}}svg .tick{{font:12px -apple-system,BlinkMacSystemFont,sans-serif;fill:#6c8293}}svg .legend{{font:12px -apple-system,BlinkMacSystemFont,sans-serif;fill:#647e90}}.minis{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}}.mini-title{{display:flex;align-items:center;justify-content:space-between}}.mini-title span{{font-weight:700;color:#4b6273}}.mini svg{{margin-top:-7px}}
.data-table{{background:#fff;border:1px solid var(--line);border-radius:13px;overflow:auto}}table{{width:100%;border-collapse:collapse;text-align:left;min-width:720px}}th{{background:#eaf0f4;color:#4c677a;font-weight:700;text-transform:uppercase;letter-spacing:.045em;font-size:11px}}td,th{{border-bottom:1px solid #e7edf2;padding:10px 12px;vertical-align:top}}tr:last-child td{{border-bottom:0}}tr:hover td{{background:#f7fafc}}.pill{{display:inline-block;border-radius:30px;padding:3px 9px;font-weight:700;font-size:11px;white-space:nowrap}}.pill.bad{{background:#fde6e3;color:#9e3a36}}.pill.unknown{{background:#fff1d8;color:#90631c}}.positive{{color:#238260;font-weight:700}}.negative{{color:var(--red);font-weight:700}}.mono{{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}}.footnote{{font-size:13px;color:var(--muted)}}.notes{{background:#eaf1f5;border-radius:14px;padding:16px 21px}}.notes li{{margin:6px 0}}
@media(max-width:760px){{.page{{padding:22px 13px 70px}}.metrics{{grid-template-columns:repeat(2,1fr)}}.minis{{grid-template-columns:1fr}}}}
@media print{{body{{background:#fff}}.page{{max-width:none;padding:0}}section,.chart-card,.mini{{break-inside:avoid}}.chart-card,.mini,.data-table{{box-shadow:none}}}}
</style></head><body><main class="page">
<header class="top"><div class="eyebrow">BILQIS MLX / DETERMINISTIC LEARNING FORENSICS</div>
<h1>Where learning held.<br>Where it struggled.</h1>
<p class="lede">A read-only reconstruction of saved, source-scored examinations and teaching receipts. Charts are generated locally; no LLM interprets or scores the run.</p>
<p class="footnote">Latest optimizer step <b>{report["latest_step"]:,}</b> · source event line <b>{report["latest_line"]:,}</b> · {src["distinct_exam_snapshots"]:,} distinct exam snapshots · {src["repeated_identical_exams"]:,} repeated exams omitted from learning trajectories</p></header>
<div class="metrics">{''.join(badges)}</div>{spotlight}
<section><h2>01 / Whole-student and grade trajectories</h2><p class="section-lead">These panels use only the latest compatible assessment scope. Scores within a single cohort can be compared on the same questions; dashed boundaries mark new questions. Green (at least 90%) and red (at most 65%) are visualization bands, not diagnoses of learning or chance.</p><div class="chart-grid">{''.join(charts)}</div></section>
<section><h2>02 / Capability-level timelines</h2><p class="section-lead">Each capability retains its own denominator, question cohort and optimizer-step identity. A high score followed by a low one on different questions is descriptive, not a paired regression.</p><div class="minis">{''.join(capability_charts)}</div></section>
<section><h2>03 / Strongest observed versus latest</h2><p class="section-lead">High-water observations are selected within the current rubric, score inventory and numeric scope. The final column states whether the high and latest measurements used the same questions.</p><div class="data-table"><table><thead><tr><th>Capability</th><th>Observed high</th><th>Latest</th><th>Difference</th><th>Comparison</th><th>Event lines</th></tr></thead><tbody>{_metric_table(report)}</tbody></table></div></section>
<section><h2>04 / Score discontinuities and investigation clues</h2><p class="section-lead">Fixed-cohort regression requires changed student checkpoints on the same questions. Cross-cohort gaps are kept separate. Nearby candidate actions are counts and leads, never proof of cause.</p><div class="data-table"><table><thead><tr><th>Evidence type</th><th>Target</th><th>Scores</th><th>Optimizer steps</th><th>Cohort / event provenance</th><th>Next investigative clue</th></tr></thead><tbody>{_alert_table(report["alerts"])}</tbody></table></div></section>
<section><h2>05 / Original five warning signals</h2><p class="section-lead">S1–S3 come from saved scored-exam diagnostic receipts where available. S4–S5 come from delivered-lesson methodology receipts. NOT_MEASURED is preserved, not reclassified as healthy.</p><div class="data-table"><table><thead><tr><th>Signal</th><th>Observed targets</th><th>Not measured</th><th>Currently observed targets</th></tr></thead><tbody>{_signals_table(report)}</tbody></table></div></section>
<section><h2>06 / Teacher friction and policy observability</h2><p class="section-lead">Each capability uses its last 16 visit events. "Old delivery unreported" means a positive older-grade allocation has no delivered-example receipt; it does not prove zero rehearsal. "Stalled" means at least eight attempts with no admitted update, not that the skill is permanently unlearnable.</p><div class="data-table"><table><thead><tr><th>Capability</th><th>Attempts</th><th>Retained</th><th>Rejected</th><th>Updates retained</th><th>Old delivery unreported</th><th>Leading rejection</th><th>Signal</th></tr></thead><tbody>{_teacher_table(report["teacher"])}</tbody></table></div></section>
<section><h2>07 / Further deterministic clues</h2><p class="section-lead">Peer lag means at least 15 percentage points below the grade's capability median on the same exam. A proposal stall means at least eight recent attempts with no admitted update. A missing delivered-rehearsal receipt is a telemetry gap, not proof that rehearsal did not occur. These are investigation leads, not new teacher controls.</p><div class="data-table"><table><thead><tr><th>Clue</th><th>Capability</th><th>Observable evidence</th><th>Interpretation boundary</th><th>Event line</th></tr></thead><tbody>{_clue_table(report["additional_clues"])}</tbody></table></div></section>
<section><h2>08 / Evidence, coverage and limits</h2><div class="notes"><ul>
<li>Event snapshot SHA-256: <span class="mono">{_h(src["sha256"])}</span>; first {src["bytes"]:,} complete bytes, {src["events"]:,} readable events.</li>
<li>Input event stream: <span class="mono">{_h(src.get("events_file", "test fixture / no file path"))}</span>.</li>
<li>{src["legacy_exams_without_checkpoint_identity"]:,} older Grade A examination events lack the optimizer-step identity needed for longitudinal comparison; they were excluded from comparable trajectories, not assumed to show learning or failure.</li>
<li>Latest declared assessment scope: <span class="mono">{_h(report["latest_declared_scope"] or "NOT DECLARED")}</span>. {report["scopes"]} distinct rubric/answer inventories present, {report["cohorts_in_latest_scope"]} cohorts in this scope.</li>
<li>Source cohorts are not interchangeable. Even a 20+ point score difference on a new cohort is not measured forgetting; an identical checkpoint with divergent results is direct evidence of evaluation differences.</li>
<li>S1/S2 classification uses stored source-scored diagnostic observations, not guessed chance baselines; S3 needs separate student checkpoints on one fixed cohort; S4/S5 depend on delivered-lesson evidence. Unavailable evidence remains unavailable.</li>
<li>Optimizer step is the timeline axis. The event stream provides no verified wall-clock time per transaction; calendar time is not fabricated.</li>
<li>The report does not run neural training, evaluate checkpoint weights, change teacher policy, assert causality or substitute for graduation. Companion JSON holds the machine-readable findings.</li>
</ul><p><strong>Input integrity flags:</strong></p><ul>{warnings}</ul></div></section>
<footer class="footnote">Bilqis deterministic reporter · {SCHEMA} · static standalone HTML/SVG · print to PDF using your browser if desired.</footer>
</main></body></html>'''

