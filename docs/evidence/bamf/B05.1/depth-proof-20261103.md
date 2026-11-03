# B05 depth proof after accepted producer integration

As of 2026-11-03, Lane B consumed reviewed unified
`48315ee7bae3caa7d5ac279128c79217b9178d16` by fast-forward and remote readback.
Issue #449's branch is `codex/bamf02-b-449-depth-proof-20261103`.

## Changes and accepted dependency

The branch consumes #756's existing test repair, original commit
`25c626c39ef865d82a14498d23b38a82bb1af03b`, without production changes.
The old test constructed a changed future tensor but never used it in a competing
execution. Paired boundary executions now supply the changed g2 or g3 tensor,
require every earlier output to remain identical, and require that group's own
output to change. A deliberate future-read mutation must fail the same assertion.

B11 producer #586 was human-integrated through PR #762, merge
`2d4b99f3b7f8f82857028a7c1f31c1e5da61b23b`, and explicitly closed after native
GitHub reconciliation. The accepted producer is already in this branch's base.
Public B05 selection takes that producer, independently replays source-owned
boundaries, validates the ordered receipt chain and parameter/generation identity,
and computes with the replayed tensors. Caller receipt tuples are not authority.
The source-qualified B08 hit path remains quarantined; no B13 retained-generation
or complete-model assembly acceptance is inferred.

## Reproduction

Run `python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/depth`.
Observed: **18/18 PASS, zero skips**. This includes independent NumPy equations,
normalization, gradients, illegal source order, and both future-read mutation cases.

Set `BILQIS_A01_ATLAS_BUNDLE` to an externally supplied A01 artifact whose bundle
identity is `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`.
Then run:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx.learning.source_atoms.tests.test_backbone_receipts
```

Observed: **16/16 PASS, zero skips**, including actual h0/g1/g2/g3 capture,
g2-as-g1 rejection, foreign parameter-tree and generation/prefix/cache rejection,
selected-state chaining, and gradients from public B05 into executed backbone and
source identity parameters. This is disposable engineering proof, not learning.
The dotted target preserves compatibility with the base's file-loader import
defect; issue #778 / PR #779 independently repairs that test-only entrypoint.

Structure, governance, architecture, docs, error-control (zero new debt), code
hygiene and whitespace checks pass. Historical ABI checks remain advisory because
the independent external expected fingerprint is absent. Live flow inventory is
reconciled separately against GitHub before turn-in.

## Boundary

Issue #577's producer dependency has landed; its remaining selector acceptance is
reviewed against the existing merged implementation rather than another local
producer. Fresh pinned EGM remains the final candidate review gate. IPR-0220
governs. No actual student, matching AdamW, teacher, champion, checkpoint or
human-run state was changed. Human integration remains separate.
