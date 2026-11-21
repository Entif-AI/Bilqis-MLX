# Issue #1504 verification

Date: 2026-11-20

## Acceptance target

The reopened #1504 acceptance target supersedes the earlier roughly ten-second
restoration target below. The qualifying surface is now the real BAMF operator
candidate step, including terminal motif staging, and MUST be **<= 1.000 second**
where physically achievable. Reduced, source-only, prepared-owner-only, and
non-terminal witnesses remain diagnostic evidence only. Timing ownership must be
exhaustive to a noise-floor residual and nested spans must not be double-counted.

The matched historical warm production target is the #1388 live B.COMPOSITE
four-row path observed on 2026-11-17 and retained locally in
`baseline-1388.md`:

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

The final bounded witness was rerun after the CI-mandated structure and hygiene
refactors against frozen implementation commit
`cdb4d6c0dcef4651dc28a88d5339a874e98ed3a6` and is retained machine-readably in
`warm-step-witness.json`. It used the real Factory candidate-step owner with:

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

Observed frozen-revision steps:

| step | candidate wall | pre-neural compile | currentness/binding | B11 preflight | B11 autodiff | C08 wall | optimizer/admission |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 7.011000 s | 1.012415 s | 0.202317 s | 0.039939 s | 2.877528 s | 4.058310 s | 0.178321 s |
| 2 | 6.731590 s | 1.024446 s | 0.250151 s | 0.037090 s | 2.456570 s | 3.762938 s | 0.143651 s |
| 3 | 6.566422 s | 1.018080 s | 0.239614 s | 0.040025 s | 2.513083 s | 3.660077 s | 0.142000 s |
| 4 | 6.954136 s | 1.032737 s | 0.344165 s | 0.039660 s | 2.671310 s | 3.863968 s | 0.142361 s |

Warm median (steps 2-4): **6.731590 seconds**.

Every step used one C08 gradient launch, one vectorized microbatch, zero scalar
fallback rows, four source-authority-bound rows, and zero cold source
requalification rows. `motif_staging_wall_seconds` was 0 because this witness was
non-terminal; publication was deliberately not executed, so there is no hidden
publication span inside the candidate wall.

Span accounting is deliberately non-additive: `candidate_step_wall_seconds` is the
top-level wall. Pre-neural source compile, currentness/binding and
optimizer/admission are owner spans around the logical batch. B11 preflight and
B11 autodiff are nested inside `c08_logical_batch_wall_seconds`; they MUST NOT be
added again to C08 or the candidate wall. The machine-readable receipt records the
same nesting explicitly.

Every sampled candidate step added:

- `candidate_identity_full_computations = 0`;
- `candidate_identity_numerical_bytes_hashed = 0`.

This is below the retained ~9.78-second warm production baseline rather than merely
explaining the 40+ second regression.

That witness is historical diagnostic evidence only after #1504 was reopened. It
did not exercise the real operator terminal path and therefore does not satisfy the
current <=1.000-second acceptance contract.

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
- `test_prepared_b11_binding_reuses_compiled_encoder_input_with_live_owner_check`
  requires a sealed prepared B11 binding to construct its immutable encoder input
  once, then re-run live packed-frame currentness on reuse rather than rebuilding
  the same compiled structure every optimizer step.
- `test_accepted_parent_batch_seal_does_not_reload_validated_bundle` forbids the
  terminal batch motif owner from cold-loading the accepted B13 bundle after the
  exact `CompleteStudent` parent is already custody-bound in memory; the paired
  manifest-drift test fails closed before motif planning.

## Reopened real-operator qualification

The reopened repair was qualified through the unmodified production
`prepare_bamf_visit(...)` entrypoint against a fresh disposable generation while
using the host's real read-only source-authority registry and signer. The sovereign
human learner was not mutated. The operator performed real planning, selected a
lawful four-row A.EDGE visit, executed the candidate, staged terminal motifs, and
completed real retention with status `ACCEPTED`.

Before the final terminal-staging repair, a representative operator candidate at
114 compiled positions measured **1.410617250 s**. Its dominant remaining serial
owner was `motif_staging_wall_seconds = 0.533700750 s`. Direct subspan profiling on
the same operator surface localized **0.450828916 s** of that cost to a redundant
`load_bamf_bundle(...)`; actual source-qualified batch motif planning was only
**0.022350375 s**. The accepted `CompleteStudent` parent and its exact manifest
identity were already present in memory under the same currentness transaction.

The repair therefore preserves the private continuation issuer and exact manifest,
run, generation, topology, and extents checks, but seals the batch motif proposal
directly against that already custody-validated accepted parent. It does not move
the cold read outside the timed interval; it removes a redundant second custody
read of the same immutable parent.

Two consecutive post-repair real-operator terminal candidates measured:

| witness | candidate wall | rows | compiled positions | currentness/binding | B11 binding | C08 wall | optimizer/admission | motif staging | candidate residual |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | **0.969292042 s** | 4 | 114 | 0.343177416 s | 0.134653833 s | 0.198069417 s | 0.120554416 s | 0.080009042 s | 0.000122290 s |
| 2 | **0.839155208 s** | 4 | 114 | 0.248139083 s | 0.106188209 s | 0.201128375 s | 0.122167166 s | 0.077031250 s | 0.000114747 s |

Both candidates used one C08 gradient launch, one vectorized microbatch, four rows,
and zero scalar fallback rows. Witness 1 additionally recorded B11 autodiff at
0.160632541 s, C08 row-input preparation at 0.075831000 s, pre-neural source compile
at 0.144537793 s, evidence capture at 0.002513500 s, training orchestration at
0.000383833 s, C08 unattributed wall at 0.000018834 s, and reporting at
0.000039583 s. Candidate-level unattributed time is therefore at the noise floor.

The <=1.000-second acceptance target is satisfied on the actual operator candidate
surface twice, including terminal motif staging. Planning and retention remain
separately measured visit-level work and are not relabeled as candidate-step work.

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

