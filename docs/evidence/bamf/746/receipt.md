# #746 accepted package-import custody and publication

3 November 2026. This branch consumes current reviewed unified
`48315ee7bae3caa7d5ac279128c79217b9178d16`, reviewed execution-owned C05 screening
from #744, and the landed A12 export-clearance authority from #745. IPR-0220 remains
governing. No live learner or protected payload was used.

## Implemented ownership

B12 now has a separate, opaque `PackageImportTransaction`. It does not reuse or
weaken ordinary `CandidateTransaction`. A fixed versioned reset policy applies only
declared imported slices: changed parameter elements are taken from the screened
candidate, changed m/v elements are zeroed, and the native AdamW count cell that
governs each changed element is reset. For row-count tensors this is the touched
leading row; for scalar-count tensors it is the scalar. Changed identity rows reset
establishment age to zero. Untouched optimizer state, row ages, allocations,
plasticity mode and `optimizer_step` remain receiver-local and unchanged.
`accepted_fast_since_full` resets to zero. Undeclared parameter changes fail closed.

C12 `publish_screened_delta_import` accepts only an internally issued
`ScreenedDeltaCandidate` whose authoritative C05 decision is `ELIGIBLE`. It then
verifies the current A12 `ExportClearanceReceipt` under a host-provided C09
`SourceAuthorityRegistry`, rechecks the live A12 selection/frontier and exact export
artifact set, requires the portable `SourceRights` projection to match that signed
authority, and requires the screened parent manifest/tensor bytes to match the
current B13 receiver. A boolean, a bare C05 `Decision`, a rejected screen, forged
clearance, or stale parent cannot enter publication.

B13 adds `bilqis.mlx.bamf-generation-transition/v2` only for `PACKAGE_IMPORT`.
The transition is issued only inside the C12/B13 adoption boundary and binds package, screened
candidate, reset policy, C05 evidence/policy and A12 clearance digests. Cold readers
accept its strict serialized record, while a caller-created matching v2 mapping
cannot use the equal-step publication exception. The issuer is not exported from
`bilqis_mlx.runtime.bamf_bundle`. `PACKAGE_IMPORT` requires unchanged
topology/extents and an optimizer step exactly equal to its parent. Existing v1
transition fields, kinds and retained-candidate step rules are unchanged. The final
parent check remains under the B13 pointer lock. The durable import outbox records
`origin=PACKAGE_IMPORT`, receiver generation/manifest and the same package/reset/
C05/A12 lineage. A pre-pointer crash leaves the old pointer current; retry converges.

## Focused proof

Tests ran in an isolated Python 3.14 temporary environment with MLX 0.32.4,
NumPy 2.5.4, cryptography 50.0.2, rdflib 7.6.0 and safetensors 0.8.0. The repository
itself was not given a new environment or dependency file.

```sh
/tmp/bilqis-mlx-746-venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/learning/_retention/tests/test_atlas_candidate.py \
  bilqis_mlx/learning/_retention/tests/test_atlas_package_import.py \
  bilqis_mlx/runtime/tests/model/optimization/test_atlas_optimizer.py
# TEST_TOTALS total=27 passed=27 failed=0 skipped=0 errors=0

/tmp/bilqis-mlx-746-venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_package_import_transition.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_publication.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_codec_boundaries.py
# TEST_TOTALS total=26 passed=26 failed=0 skipped=0 errors=0

/tmp/bilqis-mlx-746-venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/runtime/cognitive_package/tests/test_delta_candidate.py \
  bilqis_mlx/runtime/cognitive_package/tests/test_receiver_custody.py \
  bilqis_mlx/runtime/cognitive_package/tests/test_adoption.py \
  bilqis_mlx/semantics/tests/test_atlas_release_audit.py
# TEST_TOTALS total=22 passed=22 failed=0 skipped=0 errors=0
```

The focused B12 proof includes two receivers with identical parameter bytes and
different optimizer histories: changed cells reset identically while untouched
moments/counts remain specific to each receiver. It also performs the next native
AdamW step from an imported row and observes count 1 rather than inherited sender or
receiver count. The B13/C12 proof covers strict v2 custody, a non-public issuer, v1
retained-candidate invariance, cold resume, C05/A12 authority, stale-parent
rejection, and crash/retry.

After reconciling the concurrent implementation with current unified, the combined
B12, C12, C05, A12, C09, optimizer and B13 custody selection passes **146/146**,
with zero failures, skips or errors. All new production and companion test files are
below 240 lines. Every touched directory remains below 18 direct Python files.

## Production composition closure

The final #746 implementation adds the production C12 composition seam
`cognitive_package.operator.receive_screen_and_publish_package(...)`. It is the
non-test caller of `receive_package`, A12/C09 verification, `apply_plastic_delta`,
`screen_delta_candidate`, and `publish_screened_delta_import`. The operator derives
receiver identity from current B13 custody and does not issue source, retention, or
publication authority.

This section supersedes the earlier pre-operator hold that was recorded while #746
was still being assembled. #746 does not spend a separate fresh EGM. #718/#526 owns
the final whole-candidate review after this implementation reaches reviewed unified.
