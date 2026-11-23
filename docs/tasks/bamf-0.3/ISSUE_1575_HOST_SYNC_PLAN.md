# Issue #1575 implementation plan

## Outcome

Collapse avoidable Python-visible MLX synchronization around the ordinary
non-strict B11/C08 gradient path without changing the numerical objective,
optimizer semantics, retention decision, or strict/evidence behavior.

The common production shape is one route-vectorized C08 microbatch group. Its
B11 owner must retain exactly one explicit gradient materialization barrier.
This leaf does not introduce `mx.compile`, change batch geometry, change step
authority/currentness, or redesign optimizer policy; those are owned by sibling
issues #1576, #1578, and #1574.

## Current synchronization inventory and disposition

The inventory below is for the ordinary non-strict path from B11 gradient
dispatch through the C08 logical-batch result. Strict/evidence and distributed
execution retain their existing deeper checks.

1. `runtime/_model/backbone/atlas_model_microbatch.py::_materialize_gradient`
   calls `mx.eval` for the vectorized loss, gradient tree, route tensors, and a
   finite-gradient witness. **Required.** This is the one intentional B11
   gradient materialization barrier. Extend the already-materialized witness to
   cover mean loss as well as every gradient leaf.

2. `runtime/_model/backbone/microbatch/route_evidence.py::microbatch_trace_from_route`
   currently creates `mx.stack(trajectory)` after the B11 barrier and converts
   it with NumPy. **Graph construction removable; one host route-index readback
   required.** Stack the trajectory before the existing barrier and materialize
   that stacked tensor with the gradient result. The subsequent NumPy conversion
   reads an already-materialized route-index tensor; it must not create another
   MLX computation that Python then waits on.

3. `runtime/_model/backbone/atlas_model_forward_validation.py::_validate_route_trajectory`
   rebuilds expected MLX tensors and consumes `bool(mx.all(...))` after the
   route output was reconstructed from those exact route indices. **Removable
   from non-strict execution.** In learning-first mode the output is constructed
   deterministically from the materialized route indices, so this is a
   self-comparison. Strict/evidence mode retains trajectory validation.

4. `runtime/_model/backbone/atlas_model_forward_validation.py::finalize_microbatch_gradient`
   rebuilds a row-loss mean and consumes `bool(mx.allclose(...))` after the
   vectorized mean loss was already materialized. **Deferrable from non-strict
   execution to regression qualification.** Strict/evidence mode retains this
   parity check. Learning-first runtime still requires output attestation,
   structural gradient validation, and the fused finite witness.

5. `runtime/_model/backbone/atlas_model_contracts.py::BamfMicrobatchGradientExecution.__post_init__`
   currently creates and reads another finite-mean-loss predicate after the B11
   owner has already materialized and consumed its fused loss/gradient witness.
   **Move numerical finiteness to the B11 owner.** The issued microbatch contract
   keeps structural/identity validation only. The scalar `BamfGradientExecution`
   contract keeps its existing behavior because scalar fallback is not the
   ordinary vectorized target of this leaf.

6. `runtime/_batch/c08_distributed/c08_gradient_contracts.py::LogicalBatchGradientExecution.__post_init__`
   creates and reads a fresh finite-loss predicate. **Move to the numerical
   owner.** The full-batch one-group route reuses the B11 mean loss whose fused
   witness already passed. C08 paths that create a new aggregate must include
   aggregate loss/gradient finiteness in their existing final materialization
   barrier before issuing the logical-batch contract. Add an issuer-only private
   boolean `_numerical_finite_attested` to `LogicalBatchGradientExecution`.
   Local C08 sets it true only after either (a) reusing a B11 microbatch whose
   fused witness has passed or (b) consuming the C08 aggregate finite witness.
   `__post_init__` skips its tensor predicate only when that private attestation
   is true. Existing distributed reconstruction does not set the attestation,
   so its current finite-loss predicate and failure behavior remain unchanged.

7. `runtime/_batch/c08_distributed/c08_gradient_accumulation.py::_finalize_logical_batch`
   calls `mx.eval(aggregate, weighted_loss)` only when C08 has actually created
   a new aggregate tree. **Required for aggregate/fallback shapes, absent for
   the common one-group vectorized shape.** When present, the same barrier also
   materializes its finite witness. No additional validation `mx.eval` follows.

8. `runtime/_batch/c08_distributed/factory_candidate_cost.py::realized_candidate_cost`
   converts the already-materialized final loss to a host float for durable
   reporting. **Required reporting readback, not a gradient materialization
   barrier.** It remains outside differentiated graph construction and is
   reported separately from device materialization.

9. Learning-first AdamW has its own numerical validation/materialization
   boundaries in `runtime/_model/atlas_optimizer.py`. **Retained by this leaf.**
   Those checks are downstream of the B11/C08 gradient result and own optimizer
   state safety rather than gradient-graph materialization. #1575 proves their
   outputs remain equivalent but does not redesign optimizer authority or
   validation. Any later optimizer synchronization collapse requires its own
   bounded owner change.

## Production telemetry contract

Telemetry describes explicit software boundaries, not inferred Metal hardware
stalls.

- `b11_materialization_barrier_count`: number of explicit B11 `mx.eval`
  materialization calls issued by the gradient owner for the current logical
  batch. The common one-group vectorized path must report `1`.
- `b11_host_readback_count`: number of explicit post-materialization tensor
  value transfers to Python/NumPy owned by B11. The common route path reports
  `2`: one read of the already-materialized fused finite witness and one read of
  the already-materialized stacked route indices. Neither read is allowed to
  create a new MLX predicate/transform. It excludes ordinary host-only metadata.
- `b11_validation_sync_count`: number of additional device predicates created
  after B11 gradient materialization and synchronously consumed by Python for
  validation. The common non-strict route path must report `0`.
- `b11_autodiff_materialization_wall_seconds` continues to report wall time of
  the required B11 barrier.
- Existing `c08_materialization_barriers` continues to describe the logical
  batch contract. For the common one-group vectorized path it remains `1` and
  `c08_reused_materialized_full_batch` remains true.

These fields flow through the existing B11 performance observation,
`realized_candidate_cost`, and operator `STEP_COST_FIELDS`. No test-only
monkeypatch counter is used as production evidence.

Before/after comparison uses the same production-shaped 32-row non-strict
single-group workload, source/release identity, run seed, and warm-up policy at
base SHA `c8650c20f4463e65db2bf31c121c7961bb13cb89` and the feature head. Report
candidate-step wall, B11 materialization wall, materialization count, host
readback count, and validation-sync count together.

## Implementation locations

1. `bilqis_mlx/runtime/_model/backbone/atlas_model_microbatch.py`
   - build the stacked route-index tensor before the one B11 barrier;
   - include mean-loss and gradient finiteness in the fused witness;
   - materialize those tensors together;
   - attach exact B11 boundary counters.

2. `bilqis_mlx/runtime/_model/backbone/microbatch/route_evidence.py`
   - consume the already-materialized stacked route-index tensor directly;
   - preserve one required host route-index readback without post-barrier MLX
     stacking.

3. `bilqis_mlx/runtime/_model/backbone/atlas_model_forward_validation.py` and
   `atlas_model_contracts.py`
   - distinguish learning-first finalization from strict/evidence finalization;
   - in learning-first mode remove redundant tensor self-comparison and loss
     parity synchronization while preserving output attestation and gradient
     structure checks;
   - keep microbatch numerical-finiteness enforcement at the already-materialized
     B11 witness owner rather than re-reading a new finite predicate in the
     issued contract.

4. `bilqis_mlx/runtime/_batch/c08_distributed/c08_gradient_accumulation.py` and
   `c08_gradient_contracts.py`
   - make numerical finiteness an owner check at the existing materialization
     boundary rather than a contract-side device read;
   - preserve the one-group reuse fast path exactly;
   - add `_numerical_finite_attested` as an issuer-only, non-comparison contract
     field: local owner-issued results set it true only after their finite witness
     passes; distributed/coordinator results leave it false and therefore retain
     the existing contract-side finite-loss check.

5. `bilqis_mlx/runtime/_batch/c08_distributed/factory_candidate_cost.py` and
   `bilqis_mlx/runtime/bamf_operator/performance.py`
   - project the new production counters without creating synchronization.

6. Focused tests under the existing model/batch runtime test directories.

## Equivalence control

The pre-change control is exact base SHA
`c8650c20f4463e65db2bf31c121c7961bb13cb89`.

Required proof:

1. Existing scalar-versus-vectorized FP32 test remains green using the existing
   `FP32_ATOL` and `FP32_RTOL` constants for mean loss and every gradient leaf.
2. Add a focused learning-first test that patches/counts `mx.eval` and tensor
   readback owners and proves the common route path has one B11 materialization,
   two B11 host readbacks (fused finite witness + route indices), and zero
   post-materialization validation syncs.
3. Non-finite mean loss and any non-finite gradient leaf must fail before a
   gradient result can be admitted, using the fused witness and only the owner
   materialization barrier.
   Add a distributed regression showing a non-finite distributed weighted loss
   is still rejected through the unchanged non-attested contract path.
4. Run the existing directly affected optimizer/candidate tests to prove the
   same parameter, first-moment, second-moment, update-count, and participation
   semantics after the unchanged learning-first AdamW owner consumes the
   gradients.
5. Run the directly affected retention tests/witnesses and require identical
   accept/reject outcome and accepted-generation behavior for the deterministic
   fixture. The optimization may not alter C05 criteria or teacher semantics.
6. The production-shaped before/after witness must use the same immutable
   workload identity on base and feature snapshots. Timing is reported as
   measurement, while numerical and retention equivalence are hard gates.

## Failure ordering

Structural request errors remain host-side and fail before dispatch. Numerical
loss/gradient non-finiteness fails immediately after the one B11 materialization
barrier and before C08 issuance or optimizer admission. C08 aggregate paths fail
their finite witness immediately after their own required aggregate barrier.
Output/shape/participation structural failures remain fail-closed at their
current owners. Strict/evidence mode keeps its current deeper replay/parity
checks.

