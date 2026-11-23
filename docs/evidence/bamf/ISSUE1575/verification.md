# #1575 verification receipt

## Scope

Issue #1575 owns host synchronization/materialization boundaries on the ordinary
non-strict B11/C08 training path. It does not introduce `mx.compile` and does
not move strict/evidence ceremony back onto the default learning-first path.

The final branch consumes `main` through
`166d5620fffb7b3a7b747259dbdf2a23e849961b` (#1595).

## Synchronization inventory

Baseline source at `c8650c20f4463e65db2bf31c121c7961bb13cb89`
contained:

- one intentional B11 `mx.eval(...)` materialization of loss, gradients, route
  tensors, and the finite witness;
- one post-materialization finite-witness Python readback;
- one route-trajectory NumPy readback after materialization;
- one avoidable `bool(mx.all(...))` trajectory-validation synchronization on
  the ordinary no-preflight path;
- one avoidable `bool(mx.allclose(...))` loss-validation synchronization on
  the ordinary no-preflight path;
- a C08 aggregate `mx.eval(...)` only when the logical batch was not already
  materialized by the full vectorized B11 group.

The final ordinary non-strict path:

- retains exactly one B11 materialization barrier;
- materializes the finite loss/gradient witness in that same barrier;
- stacks route trajectory indices before that barrier and performs the NumPy
  conversion only afterward;
- retains two post-barrier host readbacks: the finite witness and route evidence;
- performs zero postflight validation synchronizations;
- performs no Python-visible tensor readback inside differentiated graph
  construction;
- retains one C08 gradient launch, one vectorized microbatch, and zero scalar
  fallback rows for the representative 32-row workload.

## Matched non-strict 32-row witness

A matched disposable production-path witness compared control
`caef2d9d6c59de4a7688e1558998905af14f4251` with feature
`9fd835a445535fad17113540783e816b96fbc5dc` under
`evidence_mode(strict=False)` using the same B.AND source workload and checked-in
Atlas artifact.

Hard equivalence gates passed:

- logical rows: `32 == 32`;
- loss: `0.6959685683250427 == 0.6959685683250427`;
- optimizer state SHA-256:
  `a67edb1da4f6ab47993917c6bd2bcaefcba34cc83d3bed992a09c93975286c9c`
  on both arms;
- resulting optimizer step: `1 == 1`;
- C08 gradient launches: `1 == 1`;
- C08 materialization barriers: `1 == 1`;
- vectorized microbatches: `1 == 1`;
- scalar fallback rows: `0 == 0`.

Feature synchronization telemetry on that witness:

- `b11_materialization_barrier_count = 1`;
- `b11_host_readback_count = 2`;
- `b11_validation_sync_count = 0`;
- `b11_autodiff_materialization_wall_seconds = 1.4652939578518271`.

Candidate wall was `3.440592834027484 s` on control and
`3.5260266659315675 s` on feature. This single matched sample is treated as
effectively flat and is **not** used to claim a speedup. The acceptance result
is the synchronization collapse with numerical/optimizer equivalence.

## Current-main integration verification

After #1595 merged into `main`, its new O(1) step-authority path exposed two
integration defects before #1575's materialization boundary:

1. `AdamWStateTree.parameters` is a `MappingProxyType`, which MLX rejects as a
   `value_and_grad` pytree. A focused red regression reproduced
   `[tree_flatten] The argument should contain only arrays`. The branch now
   presents a shallow plain-dict view containing the exact same tensor objects
   only at the autodiff transform boundary; the authoritative frozen mapping is
   unchanged outside autodiff.
2. `DepthParameterView` copied the trace parameter mapping into a new
   `MappingProxyType`, invalidating #1595's O(1) learning-first binding identity.
   A focused red regression reproduced the currentness failure. The view now
   preserves the exact private full-parameter mapping only when the execution
   binding explicitly owns that mapping; the prior defensive copy remains for
   other paths.

The final feature head `cbfba3fd076ce133f9ae64681c2955415344be61`
then completed the same disposable non-strict 32-row production path with:

- loss `0.6959685683250427`;
- optimizer state SHA-256
  `a67edb1da4f6ab47993917c6bd2bcaefcba34cc83d3bed992a09c93975286c9c`;
- optimizer step `1`;
- `b11_materialization_barrier_count = 1`;
- `b11_host_readback_count = 2`;
- `b11_validation_sync_count = 0`;
- `c08_gradient_launches = 1`;
- `c08_materialization_barriers = 1`;
- `c08_vectorized_microbatches = 1`;
- `c08_scalar_fallback_rows = 0`;
- `candidate_step_wall_seconds = 2.97463266691193`;
- `b11_autodiff_materialization_wall_seconds = 1.415057749953121`.

Current `main` itself cannot serve as an unmodified matched control for that
post-#1595 run because the two #1595 integration defects above occur before
#1575's synchronization boundary. The final feature-only production witness is
therefore integration evidence, while the earlier matched non-strict witness is
the controlled #1575 before/after comparison.

An additional inherited current-main observation API mismatch passes an empty
`fresh_support=()` keyword to an `ObservationCapture.delivery()` signature that
does not yet accept it. The disposable witness uses a symmetric compatibility
shim that refuses non-empty fresh support. No #1575 production behavior is
changed for that unrelated observer mismatch.

## Focused verification

Final MLX-capable focused set on `m3-ultra`:

- `bilqis_mlx/runtime/tests/depth/test_depth_contracts.py::DepthSelectionTests::test_learning_first_view_preserves_binding_owned_parameter_mapping`
- `bilqis_mlx/runtime/tests/model/execution/test_atlas_model_host_sync.py`
- `bilqis_mlx/runtime/tests/model/execution/test_atlas_model_microbatch_learning_first.py`
- `bilqis_mlx/runtime/tests/model/resources/test_accumulation.py`
- `bilqis_mlx/runtime/tests/batch/factory/test_c08_performance_observation.py`

Result: **21 passed, 3 subtests passed in 0.42 s**.

`git diff --check` passed on the reviewed final diff.

No broad repository suite is claimed here. After an initially over-broad
verification attempt was stopped, final verification followed the repository's
claim-first/differential rule and reran only evidence invalidated by subsequent
overlapping `main` changes.

## Acceptance disposition

- Host synchronization inventory: **PASS**.
- One intentional ordinary vectorized gradient materialization barrier: **PASS**.
- No Python-visible readback inside differentiated graph construction: **PASS**.
- Finite/shape/participation safety preserved: **PASS**.
- Numerical loss, optimizer update, and retained candidate state equivalent to
  matched control: **PASS**.
- Production synchronization/materialization and wall telemetry captured:
  **PASS**, with no unsupported speedup claim.

This receipt is verification evidence for human review, not merge authorization.
