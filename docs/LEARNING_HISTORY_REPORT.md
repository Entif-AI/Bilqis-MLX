# Read-only learning-history report

Generate the human-readable charts and machine-readable findings whenever a
human neural session is running or stopped:

```bash
cd ~/Code/bilqis-mlx
npm run learning:report
```

The default outputs are `runs/reports/school-mlx-v1-learning-report.html` and
the matching `.json`. Open the HTML in any browser or print it to PDF. The
command uses Python's standard library and does not require a GPU, `mlx`, npm
packages, network access, or an LLM.

Select a different saved run or output path:

```bash
npm run learning:report -- --run-dir /absolute/saved/run --output /absolute/report.html
```

The report reads only `events.jsonl`. It snapshots the readable byte boundary,
ignores a trailing partially written event, checks source identity and duplicate
examinations, and never loads model weights, AdamW, or mutable `state.json`.
It writes atomically **outside** the active run directory. Regenerating against
unchanged inputs produces identical HTML/JSON bytes.

The HTML contains grade and whole-student time series, all admitted capability
time series, best-versus-latest scores, notable score transitions, five original
diagnostic signals (S1-S5), teacher acceptance and rejection counts, rehearsal
receipt gaps, and event-line/cohort/step evidence for investigation.

The report **does not conflate cohorts**. A 65/72 B score and 44/72 B score
on two different exam question sets at the *same optimizer step and model SHA*
is evidence of an evaluation-cohort difference, **not** neural forgetting.
Within an unchanged source cohort, a measured drop across distinct students is
a paired score regression, but attributing it to a particular accepted lesson
requires additional evidence. Numeric scope and rubric changes also separate
comparisons. Repeated exams of one unchanged model count once for learning
trends; original event lines remain available for audit.

Green ≥90% and red ≤65% SVG zones are **visual aids**, not significance tests,
proof of chance-level behavior, or new admission gates. Alerting drops of at
least two correct answers and at least approximately 5% of the applicable
denominator is a descriptive screening threshold. S1-S5 are extracted from the
trainer's existing source-scored diagnostic receipts, never invented from
aggregate scores. Missing evidence remains `NOT_MEASURED`.

Nothing in this command changes student weights, optimizer, teacher policy,
graduation, curriculum or checkpoint custody. The report is a diagnostic
document, not an autonomous neural training control.
