# #1575 final drift report

## Authority reviewed

- Issue: #1575, `BAMF MLX hot path | Collapse avoidable host synchronization around gradient materialization`.
- Parent: #1535.
- Predecessor: #1566.
- Issue-local design/inventory:
  `docs/tasks/bamf-0.3/ISSUE_1575_HOST_SYNC_PLAN.md`.
- Current integration main consumed by the final branch:
  `166d5620fffb7b3a7b747259dbdf2a23e849961b`.

## Drift findings

No Blocker or Major design drift remains.

| Classification | Severity | Disposition |
|---|---|---|
| `IMPLEMENTATION_BUG` | Resolved Major | The first implementation removed ordinary learning-first postflight validation synchronizations but also made strict vectorized finalization require preflight executions. Strict vectorized route/loss validation was restored and covered by explicit accept/reject regressions. |
| `VERIFICATION_GAP` | Resolved Major | The first sync-count test asserted mostly mocked telemetry. A real-owner regression now observes the actual MLX materialization owner and route-evidence readback owner, requiring one `mx.eval`, one NumPy route readback, one B11 materialization barrier, two host readbacks, and zero learning-first validation syncs. |
| `INTEGRATION_REPAIR` | Resolved Major | #1595 changed the candidate parameter input from a plain dict to the optimizer's frozen `MappingProxyType`, which MLX does not accept as a pytree. The fix is confined to the transform boundary and creates only a shallow dict of the same tensor objects, preserving O(1) authority/currentness outside autodiff and causing no tensor readback. |
| `INTEGRATION_REPAIR` | Resolved Major | #1595 learning-first bindings use exact parameter-mapping identity. `DepthParameterView` previously replaced the bound mapping with a new proxy after initial validation, causing later currentness checks to fail. Binding-owned full mappings now preserve identity; unbound/other-bound views retain the prior immutable proxy behavior. |
| `INHERITED_MAIN_DEFECT` | Minor, external | Current main passes `fresh_support=()` into an `ObservationCapture.delivery()` signature that does not accept it. This occurs after candidate execution and is outside #1575's host-sync boundary. The disposable witness shims only the empty keyword and refuses non-empty fresh support; production code is not changed here. |
| `MEASUREMENT` | Info | The matched non-strict sample showed effectively flat candidate wall (`3.4406 s` control, `3.5260 s` feature). The change claims fewer avoidable synchronizations, not a statistically established wall-time speedup from one sample. |

## Contract reconciliation

- Ordinary non-strict graph construction contains no Python-visible tensor
  readback.
- Loss/gradient finiteness is checked by a lazy scalar witness materialized with
  the owner loss/gradient barrier and inspected afterward.
- Route trajectory is stacked before the barrier and read by NumPy only after
  materialization.
- Learning-first finalization skips the two redundant tensor-value parity
  synchronizations while strict mode retains exact trajectory/loss validation.
- C08 full-vectorized reuse avoids a redundant aggregate materialization while
  scalar/multi-group aggregation retains fail-closed finite validation at its
  required aggregate boundary.
- No `mx.compile` is introduced.
- No evidence-plane ceremony is restored to ordinary Step 1.
- Telemetry reports B11 materialization barriers, host readbacks, validation
  syncs, and the existing C08 launch/materialization/wall fields.

## Final verdict

**PASS.** No Blocker or Major drift remains between #1575's durable outcome and
the reviewed implementation. The #1595 repairs are necessary compatibility work
at the same learning-first/autodiff boundary, preserve the O(1) authority design,
and do not expand #1575 into compilation or evidence-plane policy.
