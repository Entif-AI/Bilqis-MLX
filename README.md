# Bilqis MLX

Private, source-oracled MLX training for a compositional semantic transformer. **This is the one active repository:** `~/Code/bilqis-mlx`. The human operator alone launches real neural updates; CI, tests, and agents must not train or replace the human student.

The former Bilqis implementations are preserved as pinned, read-only source dependencies under `vendor/legacy-v16/`. They are not separate runtime repositories. The native historical bootstrap checkpoint and inherited teacher state live in the ignored `vendor/legacy-v16/runs/`. The current model, its matching AdamW, learning history, champions and soups live under ignored `runs/`. None of those binaries are committed to Git.

## Keep training the existing student

**Championship authority:** [Championship lifecycle specification](docs/specifications/CHAMPIONSHIP_LIFECYCLE_V1.md) governs curriculum-boundary resets, same-grade champions, cross-origin takeover and frozen soup eligibility. The opt-in mentor-epoch branch is experimental, not an automatic change to the human's canonical school.

```bash
cd ~/Code/bilqis-mlx
npm run train -- --dry-run --resume --verify-source
npm run train -- --human-run --resume --minutes 90
```

The first command is **read-only** and reports blockers. Only the second, explicitly run by the human, makes neural updates. Both use the default `runs/school-mlx-v1` and the internal historical oracle files. No `--legacy-code-root` flag, another checkout or checkpoint clone is needed. The actual progress and optimizer step always come from the latest `runs/school-mlx-v1/state.json`, not from dated documentation.

## Resume the existing isolated championship experiment

The issue #340 trial is already isolated under `~/Code/bilqis-mlx-retention-lab`. **Continue its existing complete student and own AdamW. Do not make another 8 GB fork or discard any earlier optimizer steps.** Historical champion and soup checkpoints remain archived. After the explicit one-time championship reset, **no baseline or old champion advises at all** until fresh post-reset checkpoints earn championship roles. Only newly earned grade soups advise across grade boundaries. Cross-origin takeover requires a perfect entire target grade and, when incumbents exist, strict same-cohort cumulative school superiority over each incumbent.

```bash
cd ~/Code/bilqis-mlx-retention-lab
python3 -B -m scripts.reset_epoch_championships --run-dir ./runs/issue-340-mentor-epoch-trial
python3 -B -m scripts.reset_epoch_championships --run-dir ./runs/issue-340-mentor-epoch-trial --apply
npm run train -- --dry-run --resume --verify-source --run-dir ./runs/issue-340-mentor-epoch-trial
npm run train -- --human-run --resume --minutes 15 --run-dir ./runs/issue-340-mentor-epoch-trial
```

The reset script's first invocation previews; `--apply` commits **one metadata generation**, not a neural update or model copy. Use it only when no human trainer is running; a process lock prevents concurrent writes. The human alone starts the **last** command after the dry-run reports no blockers. It resumes the latest intact optimizer, never a lower-step checkpoint. The trial was first activated mid-Grade-C; **it tests forward learning with the corrected championship policy, not a replay of historical B-to-C admission**. Evaluate retained A/B mastery, new C roles, cross-origin eligibility, grade-soup ingredients, whole-school scores and teacher outcomes before deciding whether to keep or discard the trial. Preserve both original and experimental runs until that decision.

**Retention is the default for every training launch and resume.** The former `--experimental-retention` opt-in is no longer needed (older commands remain accepted for compatibility). Existing protected student/AdamW lineages keep their recorded policy and cannot be resumed without retention. To deliberately run the older, unprotected teaching path for an **independent** experiment, supply `--no-retention` with a distinct explicit `--run-dir`; this cannot turn off protection for `runs/school-mlx-v1/`. An opt-out is never inferred from an omitted flag. Retention rejects locally non-improving candidates and preserves matching AdamW; whole-student regressions can still occur.

```bash
npm run status
npm run dashboard
npm run diagnostics -- --run-dir ./runs/school-mlx-v1
```

**Candidate retention net-grade correction (ADR-054):** A target gain never justifies a larger within-grade loss. Every admitted capability in that grade is checked on a complete equal-size fresh paired panel, which must improve strictly in aggregate. When the current grade has a saved matching whole-grade exam cohort, its fixed score must not regress either. For example, B.XOR +1 versus B.IFF -1 and B.IMPLIES -1 is a rejection, not a retained improvement. See docs/specifications/CANDIDATE_RETENTION_GRADE_NET_V1.md. No previous student optimizer steps are rolled back by this prospective rule.

**Staged scoring refinement (ADR-055):** Check the candidate's target first and reject immediately if it makes no gain. For a possible retained candidate, score only still-missing capabilities in its own currently admitted grade, reusing valid scores from this exact candidate and paired source cohort. Only a complete positive same-grade result proceeds through its fixed-grade and bounded cross-grade guards. Champion scoring is a different promotion: all own-grade capabilities must be tested before assigning an individual title. An outside-grade challenger must be perfect across the **entire destination grade** before it can take **all of its titles at once**, then also strictly beat all real displaced incumbent checkpoints on the same whole-school cohort; otherwise **none** of that grade's titles move. An uncontested destination grade needs only its complete grade proof. The ordinary whole-school graduation exam remains independent, not a prerequisite for every provisional neural candidate.

The source-backed Grade C staircase teaches established counting, number, successor, addition and subtraction operations on gradually expanded domains before introducing multiplication and division. New semantics enter an append-only native registry. The vocabulary size is graph-bound, not permanently 222 tokens. A/B retention is assessed on the same whole student; individual best champions and frozen grade soups remain distinct from live student promotion.

The retention-aware teacher tests parent-versus-challenger changes and preserves recoverable best whole-student checkpoints with **their own AdamW**. **Only a strictly positive, source-oracled gain in the targeted capability can promote a candidate.** Rejected attempts still teach both the contextual teacher **and the inherited strategy-selection bandit**, using the measured causal rejection penalty rather than incorrectly reporting zero reward to the bandit. Rejection does not change the student or AdamW; recorded instructional accuracy and historical teacher rewards retain their original meanings. Graduated A/B capabilities retain mature protection in every C scheduling phase. The active probe has a bounded size informed by that skill's current exam count, while cross-grade protection probes stay small. This provisional gate is neither perfect retention nor a graduation shortcut. Temporary forgetting remains possible. The whole student always advances from its latest committed checkpoint unless the human explicitly directs recovery.

When a comparable full-school examination includes B.OR and B.XOR, candidate screening also replays their 24 source-oracled, truth-balanced fixed-cohort questions. Any newly wrong answer on these already-correct compositions rejects the trial, without evaluating all school capabilities. Teacher feedback still records the rejection. The dashboard's **LESSON%** column measures fresh instructional examples; cumulative qualification is reported separately under **GRADES & MASTERY**.

Longitudinal learning diagnostics must examine **distinct student checkpoints**, not count re-examinations of the same unchanged checkpoint as new learning. Repeated exams remain individually source-verified and present in the audit; genuinely changed or backward checkpoint identities still fail closed. The School50 diagnostic display must expose a history-validation failure instead of silently presenting an unavailable durability signal as “no active warnings.”

Recovery ranks the complete cumulative pool of introduced and graduated capabilities. Perfect capabilities must not pad a weakest-three recovery round. The normal teaching pass should avoid an unnecessary optimizer trial when the current student is already perfect on a fresh source-oracled target probe; whole-student examinations still recheck every admitted capability. The experimental matrix-strain signal compares parent-to-candidate weight movement against an immutable curriculum-epoch starting checkpoint and the best **comparable whole-student** high-water checkpoint. That high reference advances only on a strictly higher cumulative score recorded by the whole-student peak authority, never on ties or grade-soup refreshes. Matrix-strain diagnostics are advisory, not an automatic retention veto or replacement for examinations.

## Repository layout

| Path | Ownership |
| --- | --- |
| `bilqis_mlx/` | Active semantic engine, MLX teacher/student, training, runtime, checks and School50 telemetry |
| `vendor/legacy-v16/` | Frozen historical source oracles and teacher implementation; no new feature development |
| `vendor/legacy-v16/runs/` | Ignored original historical bootstrap checkpoint and teacher-state provenance |
| `runs/school-mlx-v1/` | Ignored active human student and its saved optimizer, source/oracle receipts and teacher history |
| `runs/archive/` | Ignored historical local safety copies pending independent external backup |
| `docs/` | Current operator contracts and historical/research records |
| `tests/` | Disposable, source-verified fixtures; no actual-student optimizer writes |
| `.github/workflows/` | Portable integrity checks and private release automation |

`BILQIS_STORAGE_ROOT` configures the default local run home. The retention trainer requires that home to remain inside this repository's `runs/` tree; its current fully tested default is `runs/school-mlx-v1/`. Store backups on a distinct, explicitly selected volume and verify them before deleting any original checkpoint; moving files between folders on the same volume does not free space.

## Checkpoint and disk maintenance

Full student and matching optimizer checkpoints are kept together. A saved state is immutable, and source-cohort graduation tests never combine best scores from different students. Routine checkpoint retirement only removes genuinely unreferenced bundle directories after commit. Unexpected files and symlinks fail closed; harmless macOS Finder metadata no longer blocks resume. Protected champions, live state, accepted whole-student peaks, frozen soup recipes and qualified sources retain explicit identity.

```bash
npm run storage:plan
# Optional, when training is inactive: losslessly compress older immutable JSON states
npm run storage:compact -- --max-files 0
```

The normal human-run stop path also performs bounded lossless compression of old state JSON. It does not delete neural weights, AdamW, original authority records or checkpoints held by a live role. See [checkpoint and release migration](docs/CANONICAL_REPOSITORY_AND_RELEASE_20261017.md) for custody details. No backup script runs automatically against arbitrary external drives.

## Development and release

```bash
python3 -B -m unittest discover -s tests -q     # Apple Silicon/MLX integration suite
npm run quality:check
npm run release:check
python3 -B scripts/check_historical_abi.py
python3 -B scripts/check_semantic_boundaries.py
```

The portable Linux GitHub Actions jobs verify source, semantic ABI, release manifests, selected neural-inert tests and regression-aware code hygiene. Full neural testing is Apple Silicon only. Conventional Commits, Semantic Versioning and a dated `CHANGELOG.md` govern private releases. Tag an immutable annotated `vMAJOR.MINOR.PATCH` on a verified clean `main`; the tag workflow validates and publishes private release notes. See [contribution and release rules](CONTRIBUTING.md).

For detailed historical decision-making and source provenance, read [ADR.md](ADR.md), [AGENTS.md](AGENTS.md) and the [archived pre-consolidation README](docs/history/README_PRE_CANONICAL_20261017.md). Historical example paths in old research papers are **provenance**, not current operator commands. Protected research contracts must not be copied into public repositories.
