# Issue #1504 verification

Date: 2026-11-20

## Acceptance target

The matched historical warm production target is the #1388 live B.COMPOSITE
four-row path observed on 2026-11-17:

- full optimizer step median: approximately 9.78 seconds;
- B11 autodiff median: approximately 4.09 seconds;
- C08 logical-batch median: approximately 5.35 seconds;
- B11 preflight median: approximately 0.027 seconds;
- approximately 49 compiled positions;
- one gradient launch, one vectorized microbatch, zero scalar fallback.

The later #1388 cold disposable full-step receipt (33.6231 seconds, including
20.8353 seconds of fresh source compilation) is a different workload and is not
the warm production target.

## Root cause 1: accepted-parent identity continuity was lost

The regressed live visit paid 24 full candidate-identity computations across four
steps, reused zero bindings, hashed 22,892,358,336 numerical bytes, and spent
15.73613845789805 seconds in full candidate hashing.

The repaired ownership split is:

- same-process current accepted state: reuse an already-authenticated
  `accepted_execution_cache` hydration and the existing #1238
  `CandidateIdentityBinding` consumer API;
- cold/public acceptance and publication reads: retain independent canonical proof;
- historical ancestors: retain independent bundle hydration/proof;
- currentness-owned proof: preserve the existing currentness transaction and live
  fence rather than replacing it with digest memoization.

The operator-shaped regression
`test_bound_accepted_parent_identity_is_reused_across_priority_hot_path` resets
identity counters after accepted hydration, crosses priority selection/currentness
and C03 successor custody, and requires:

- zero additional full parent identity computations;
- zero additional numerical bytes hashed for the bound parent;
- one full computation only when a genuinely new candidate state is first bound;
- no extra full computation when teacher successor custody consumes that binding;
- binding require/reuse activity remains observable.

Canonical public proof boundaries were deliberately kept separate. The focused
acceptance test that injects synthetic successor run-identity drift still fails
closed through `load_bamf_generation_authority(...)`.

## Root cause 2: v0.3.8 refinement routing disabled the vector B11 route path

Commit `c89fe3343ef4dab34992b4ff8dfb729986f1f8a1` introduced the v0.3.8
refinement-routing objective and conservatively disabled the vector route path
whenever any refinement supervision was present. That preserved correctness but
forced `microbatch_trace_preflight(...)` before every otherwise route-compatible
four-row B.COMPOSITE gradient.

Issue #1504 subspan instrumentation localized the cost on the exact retained
four-row B.COMPOSITE fixture (seed 37129, positions 14/14/12/12):

| B11 span | Before repair |
| --- | ---: |
| total preflight | 3.898683 s |
| fallback trace preflight | 3.695766 s |
| execution rebinding | 0.169049 s |
| finite validation | 0.028087 s |
| refinement selection | 0.005740 s |
| route compatibility | 0.000030 s |
| route kernel preparation | 0 s |
| autodiff | 3.722228 s |

The repair does not remove the new objective. The batched refinement kernel now
emits the same pre-pass 0/1/2 route-head logits as the scalar path, computes the
same per-row mean routing cross-entropy, applies the normative v0.3.8 weight, and
attaches materialized route supervision to the postflight row evidence. A
route-compatible refinement-supervised batch therefore remains vectorized without
paying a duplicate scalar trace.

After repair, the same four-row fixture reported:

| B11 span | After repair |
| --- | ---: |
| total preflight | 0.184192 s |
| fallback trace preflight | 0 s |
| execution rebinding | 0.160752 s |
| finite validation | 0.017413 s |
| refinement selection | 0.005161 s |
| route compatibility | 0.000029 s |
| route kernel preparation | 0.000835 s |
| autodiff | 1.883137 s |

The execution remained one gradient launch, one vectorized microbatch, zero
scalar fallback rows. Final B11/C08 postflight loss validation passed with the
refinement-routing term present.

## Warm production-shaped candidate-step witness

The final bounded witness used the real Factory candidate-step owner with:

- B.COMPOSITE;
- four rows;
- source seed 37129;
- compiled positions 14/14/12/12 (52 total);
- an accepted disposable generation-zero parent;
- a visit-scoped `PreparedPrioritySourceMaterialization`, matching the operator's
  warm handoff into `execute_factory_candidate_step(...)`;
- four consecutive speculative optimizer steps;
- no publication and no mutation of a real learner;
- one MLX worker.

Observed steps:

| step | candidate wall | pre-neural compile | B11 preflight | B11 autodiff | C08 wall | optimizer/admission |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6.453837 s | 1.008877 s | 0.033477 s | 2.472121 s | 3.596673 s | 0.193223 s |
| 2 | 6.464944 s | 0.983881 s | 0.038100 s | 2.322056 s | 3.460861 s | 0.246654 s |
| 3 | 6.587984 s | 0.962022 s | 0.040302 s | 2.353284 s | 3.596933 s | 0.155808 s |
| 4 | 6.161095 s | 0.944782 s | 0.038389 s | 2.285256 s | 3.392446 s | 0.131178 s |

Warm median (steps 2-4): **6.464944 seconds**.

Every sampled candidate step added:

- `candidate_identity_full_computations = 0`;
- `candidate_identity_numerical_bytes_hashed = 0`.

This is below the retained ~9.78-second warm production baseline rather than merely
explaining the 40+ second regression.

For comparison, the same disposable candidate owner without the prepared-source
handoff measured 21.466498 seconds, of which 15.826183 seconds was pre-neural
source compilation. That is expected cold/rebuild work and demonstrates why the
operator's visit-scoped prepared-source ownership is performance-critical.

## Deterministic regression enforcement

Timing is evidence, not the only gate. The patch adds deterministic multiplicity
oracles for the expensive work that regressed:

- the operator-shaped identity test requires zero repeated full parent hashes and
  zero numerical bytes once the accepted parent is already bound;
- `test_route_gradient_with_refinement_supervision_stays_vectorized` fails if a
  route-compatible refinement-supervised logical batch re-enters full trace
  preflight;
- `test_batched_routing_loss_matches_scalar_per_row_mean` locks the v0.3.8
  refinement-routing loss semantics while the vector route path is active;
- B11/C08 performance observation tests require the new subspan fields to survive
  through candidate reporting.

## Focused verification completed

- candidate identity binding + publication reuse + cold trust: 15 passed;
- generation acceptance authority/custody: 27 passed, 8 subtests passed;
- C09 capability-support materialization/lineage: 4 passed;
- Atlas binding persistence: 6 passed;
- teacher priority / learning-health / stop-receipt focused slices: green;
- operator-shaped parent identity regression: green;
- B11 trajectory suite: 9 passed;
- refinement-routing batched-loss parity test: green;
- B11 microbatch execution suite: 4 passed, 1 environment-gated skip, 10 subtests;
- C08 performance/candidate reporting: green;
- `git diff --check`: green at the recorded verification points.

The broader refinement test file contains a pre-existing MLX 0.31.1 compatibility
failure (`mlx.core.flip` is unavailable). That failure predates #1504 and is the
same environment drift family already recorded in #1388; the new routing-loss
parity test in that file passes.

## Witness environment

- Apple M3 Ultra, arm64;
- macOS 27.0.1;
- Python 3.14.3;
- MLX 0.31.1;
- mlx-metal 0.31.1;
- `BILQIS_TEST_WORKERS=1`;
- no sovereign human trainer process was active during the MLX witnesses.

