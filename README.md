# Bilqis MLX

Private, source-oracled MLX training for a compositional semantic transformer. **This is the one active repository:** `~/Code/bilqis-mlx`. The human operator alone launches real neural updates; CI, tests, and agents must not train or replace the human student.

The former Bilqis implementations are preserved as pinned, read-only source dependencies under `vendor/legacy-v16/`. They are not separate runtime repositories. The native historical bootstrap checkpoint and inherited teacher state live in the ignored `vendor/legacy-v16/runs/`. The current model, its matching AdamW, learning history, champions and soups live under ignored `runs/`. None of those binaries are committed to Git.

## Keep training the existing student

```bash
cd ~/Code/bilqis-mlx
npm run train -- --dry-run --resume --verify-source
npm run train -- --human-run --resume --minutes 90
```

The first command is **read-only** and reports blockers. Only the second, explicitly run by the human, makes neural updates. Both use the default `runs/school-mlx-v1` and the internal historical oracle files. No `--legacy-code-root` flag, another checkout or checkpoint clone is needed. The actual progress and optimizer step always come from the latest `runs/school-mlx-v1/state.json`, not from dated documentation.

**Retention is the default for every training launch and resume.** The former `--experimental-retention` opt-in is no longer needed (older commands remain accepted for compatibility). Existing protected student/AdamW lineages keep their recorded policy and cannot be resumed without retention. To deliberately run the older, unprotected teaching path for an **independent** experiment, supply `--no-retention` with a distinct explicit `--run-dir`; this cannot turn off protection for `runs/school-mlx-v1/`. An opt-out is never inferred from an omitted flag. Retention rejects locally non-improving candidates and preserves matching AdamW; whole-student regressions can still occur.

```bash
npm run status
npm run dashboard
npm run diagnostics -- --run-dir ./runs/school-mlx-v1
```

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
