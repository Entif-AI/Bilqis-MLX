# B08.1 source-context continuation — 3 November 2026

## Scope and branch custody

Issue #460 resumed after the recorded C01/#347 structural trigger was satisfied
by human-merged PR #803. Consumed reviewed unified and remotely verified Lane B:
`e9226be2f6a41f47109ca02a1103a363e64909a7`. The issue feature branch is
`codex/bamf02-b-460-qualified-reads-20261103-resume`, cut from Lane B and then
fast-forwarded to that reviewed unified. Its ledger is ACTIVE before source edits.

Implementation commit `b37eaf93234b40ba7c066d4203ed87b811ee91db` extracts
`source_qualified_motif_context` from the existing B07 preparation path. It returns
the replayed approved projection, complete source-qualified nested motif inputs,
and source-issued frontier without performing allocation. Existing allocation
preparation consumes that same replay. Returned records are derived data, not
transferable source admission or retained-parameter credentials.

This is a bounded prerequisite stage. It does not enable public motif hits, complete
#460, change the gate equation, or establish B08/B11/B13 learning acceptance.

## Red/green proof

The new test module first failed to import the absent
`source_qualified_motif_context` symbol. After extraction:

- four new source-context cases pass, including real pinned A/B/C replay,
  exact frame/member/key agreement with allocation, prefix hold, revoked source
  rejection, and absence of caller projection/schema/allocation inputs;
- eight existing B07 source tests pass, including forged row/graph/proxy and
  source-release negatives;
- eleven existing motif-read tests pass, including both numerical read sites,
  page/projection/gate gradients, held/missing/foreign-release behavior, nested
  keys and the unchanged public quarantine.

Total affected proof: **23 passed, zero failures/errors/skips**, on native MLX CPU.
The repository runner does not discover tests merely from the dotted
`bilqis_mlx.learning.tests.motif_reads` package. The eleven adjacent tests were
therefore run through their explicit physical test files and counted separately.

Environment: `/private/tmp/bamf-b08-460-native/bin/python`, Python 3.14;
MLX/MLX-Metal 0.32.4, NumPy 2.5.4, rdflib 7.6.0, cryptography 50.0.2,
pyshacl 0.40.1. CPU was explicitly selected before importing test targets.
The externally mounted A01 bundle is
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`;
release and source-bundle identities are checked by the existing pinned fixture.
No artifact contents are copied into public Git.

Reproduction from the repository root with those dependencies and the pinned
artifact mounted at `$BILQIS_ATLAS_REAL_ARTIFACT`:

```sh
python3 -B - <<'PY'
from pathlib import Path
import runpy
import mlx.core as mx
mx.set_default_device(mx.cpu)
runner = runpy.run_path('scripts/run_tests.py')
targets = [
    'bilqis_mlx.learning._engram.tests.test_motif_context',
    'bilqis_mlx.learning._engram.tests.test_atlas_engram_source',
    *(str(path) for path in sorted(
        Path('bilqis_mlx/learning/tests/motif_reads').glob('test_*.py'))),
]
main = runner['main']
raise SystemExit(main(targets))
PY
```

Committed-scope structure and governance checks report zero violations; changed
code hygiene scans both changed code files with zero findings or new debt.
Ordinary independent GPT-6.1 Terra High review reports no findings. This is not
fresh whole-candidate EGM, which remains reserved for merge readiness.

## Remaining work

The public read boundary still needs both sites connected to this exact source
replay, B02 features derived from the same projection, and B13-owned allocation
and parameter custody. Do not accept caller-created projection, motif input,
`CompleteStudent`, feature manifest, or digest strings as authority. B13's actual
bundle reader validates custody; its public record type alone does not. Preserve
source-held/revoked misses without structural fallback, differentiability and full
source/rights/generation cache identity. Reconcile the training execution interface
at the canonical owner rather than inventing a consumer-local credential.

The local flow checker passes. A live admission check additionally reported open
concurrent PRs #808 and #809 absent from this candidate's ledger snapshot; this
stage opens no PR and does not change another writer's inventory. Final PR admission
must be reconciled against current authoritative inventory when #460 is ready.

Separately, PR #802 is verified human-merged as
`05e31a576e3432e4238c9b4477a70d70ec4fc487`. #481 was explicitly closed completed
and read back after that accepted integration. This retires only B13.4's schema
leaf; full #480/#754/#372 learning-generation acceptance remains open.

IPR-0220 remains opaque. No durable student, optimizer, teacher, checkpoint,
source, graph, human-run or self-merge mutation was performed.

## Tracking readback

All 13 worksheet tabs were reconciled directly: 38 changed cells read back with
zero mismatches; eight inspected formula cells remained formulas. The live canonical
leaf query reconciles Lane B at 32/55 closed and 23 open; all lanes total 97/163
closed. B13.4 is 1/4 closed. No B08 leaf was counted closed.
