# B12.4 unbound constructor and normative ledger

Issue #477 remains open for complete-model/candidate integration. This slice
consumes actual B01 initialization and tensor metadata; it introduces no
replacement initializer or independent tensor inventory.

Predecessor `1416d65231e5f40d9db4d741dfe39487d2a6d543` consumes reviewed
unified `da0431bee37c0e4f766f05cc94ceb6b23ac7d054`, unchanged at the leaf fetch.
The private `_create_unbound_bamf_optimizer` calls
`model_topology_v2.create_unbound_bamf_state` and borrows its parameter and
native moment arrays and original UNBOUND manifest. Names, shapes, initializer
classes and decay flags come from `expected_bamf_shapes`.

Identity, motif and feature tables have uint64 leading-row zero counts.
Two-dimensional embedding tables also use leading-row counts, while vector
seeds and dense parameters use scalar zero counts. Every moment remains FP32
zero. This is fresh disposable initialization, not migration of a historical
optimizer or source admission. B01's original manifest and topology/extents
digests remain intact; count-state schema remains provisional-v1.

Red: one missing-API failure with twelve existing tests passing. Green:
**13/13 native MLX tests**, zero skips, including real initialization and
validation of the full disposable B01 tensor tree. The witness checks exact
keys/shapes, all zero moments/counts, uint64 types, representative table/scalar
geometry, literal initializer values, decay flags and original UNBOUND status.
Available disk at test preparation was238GiB; no model binary was written.

Fresh pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`: scoped PASS,
no Blocker/Major; independently reproduced13/13. Explicit operator audit and
diff check pass. No production caller exists beyond the focused test.

Actual source-admitted row values, B11 model execution, B09 participation,
B12 retained transactions and B13/C serialized counts remain pending. This
constructor supplies none of those authorities and does not close #477.
IPR-0220 remains open; PM-2026-10-29-001/002/003/004/006 controls remain.
No durable student/own AdamW/teacher/champions/originals changed; actual
learning and retention remain unmeasured. Human owns integration and durable
training initiation.

## Complete production reconciliation — 2026-11-06

The remaining #477 integration seam is closed on implementation commit
`fef4146c3bad484ae9cb5e608618b3eb6e4a9c5e`, consuming reviewed unified
`3899649586b105b075e92f0ee3c51e80c379b473` after #476 / PR #886 was merged.
The earlier constructor slice already proved that fresh B12 state can be built
directly from the B01 ledger. The missing production property was that the live
B11 -> B12 candidate boundary still accepted a caller-authored AdamW `decay`
mapping, leaving one optimizer-manifest fact outside the normative ledger.

`reconcile_b01_optimizer_manifest` now validates the complete candidate
`AdamWStateTree` against B01 before every production step. It requires exact
ordered equality between the expanded `ParameterSpec` sequence and the
parameter, first-moment, second-moment and update-count trees; reuses B01's full
parameter validation; requires every moment to preserve its declared parameter
shape; requires every count tensor to use B01-derived scalar/leading-row count
geometry; and returns the immutable decay mapping directly from the same
`ParameterSpec` sequence. `_create_unbound_bamf_optimizer` uses the same
reconciler, so disposable construction and retained production execution no
longer maintain parallel optimizer manifests.

The production APIs `production_candidate_step`, `admit_candidate_step` and
`admit_uninterrupted_candidate_step` no longer accept caller-authored `decay`.
The real Factory continuation witnesses likewise stopped reconstructing a local
decay dictionary. A consistently renamed prefix such as
`frame.identity.bank.0`, an extra/missing parameter, an ordering drift or a
row/scalar count-geometry mismatch now fails at reconciliation before optimizer
arithmetic. Existing adapter, depth, attention and readout views continue to
borrow only their declared B01 prefixes; shared feature/depth/identity tensors
remain single entries in the complete tree.

Red-first evidence: the new
`test_decay_manifest_is_derived_from_b01_not_the_caller` initially failed
because `production_candidate_step` still exposed `decay` in its signature.
After the repair the focused production boundary is **9/9 PASS**, including
adversaries that reject wrong row/scalar count geometry, a consistently misowned
prefix and an otherwise-valid tree reordered away from the B01 ledger. The decay
witness uses a B01 declaration with `decay=False`, proving production derives the
flag rather than hardcoding the positive case. Nearby acceptance evidence is
**14/14** B13 production
authority, **7/7** cold continuation, **13/13** optimizer construction/arithmetic,
**11/11** plasticity/prefix, **5/5** depth-prefix, **6/6** attention and **5/5**
readout-prefix tests: **70 passed, 0 failed**. The two live-source model-forward
tests remain expected environment skips because the real pinned A01 artifact is
not mounted in this disposable worktree.

`npm run verify:leaf` completed **301 passed, 14 skipped** before reporting
seven failures and one collection error outside the #477 delta. Exact-base
reproduction on untouched `3899649586b105b075e92f0ee3c51e80c379b473`
confirmed all of them: six cache-authority tests stop at the pre-existing B13
generation-acceptance requirement, one cache-policy subtest fails only under
xdist because execnet cannot serialize NumPy's dtype object, and the unchanged
legacy backbone wrapper imports a pre-relocation test module. None is used as
B12.4 acceptance evidence. The exact commands, failure identities and the
discarded stale-base comparison are preserved in
`docs/evidence/bamf/B12.4/leaf-baseline-classification-v1.md`.

Post-commit `quality:changed` passes: module-size and governance checks are
clean, the changed-file smell audit scanned ten files with zero findings, BAMF
flow control passes and its 15 regressions pass. Contract mirrors remain 43/43.
Fresh merge-readiness Goldfish review is still required before `EGM-Passed` and
PR turn-in. No live student, optimizer, teacher, source admission, checkpoint or
champion was mutated by this work.
