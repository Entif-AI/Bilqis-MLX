# B06.4 | Refinement tensor registry reconciliation

## Scope

This receipt covers the issue-owned B06.4 registry seam only. It projects the
existing B01 tensor ledger into an immutable typed refinement view. It does not
create a second parameter registry, authorize a student generation, or claim
B06.3 acceptance while #454 remains gated on the pinned Google EGM.

Consumed reviewed unified / Lane B:

`0cac1a27abfb909b61646e5303ed40e9f60aa977`

## Registry contract

`refinement_parameter_view(parameters, spec, extents)` first validates the
complete supplied parameter tree against B01's authoritative
`expected_bamf_shapes`. Only then does it return a frozen
`RefinementParameterView` containing:

- the exact B01 topology digest;
- the exact generation-extents digest;
- the exact ordered B01 `ParameterSpec` declarations whose names begin
  `refine.`; and
- immutable mapping ownership over the original MLX array objects.

The view does not rename, copy, reshape or independently initialize tensors. Its
mapping order is the B01 ledger order, and the numerical B06 kernel consumes the
view through the ordinary `Mapping` contract with byte-identical results.

The B01 disposable constructor remains the only initializer owner. The B06.4
tests independently compare every refinement tensor produced by
`create_unbound_bamf_state` with `initialize_bamf_parameter` for the corresponding
B01 `ParameterSpec`, and with the initialization manifest's shape, initializer,
group and decay fields.

Generation extents are bound as identity metadata but do not redefine the fixed
refinement geometry. Changing semantic/motif extents changes the extents digest
while leaving the exact `refine.*` declaration tuple unchanged.

## Verification

```sh
PYTHONPATH=/tmp/bamf-b14-testdeps:. python3 -B -m unittest -v \
  bilqis_mlx.runtime.tests.model.refinement.test_registry

PYTHONPATH=/tmp/bamf-b14-testdeps:. python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/model/test_atlas_refinement.py \
  bilqis_mlx/runtime/tests/model/test_refinement_policy.py

PYTHONPATH=/tmp/bamf-b14-testdeps:. python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/model/topology \
  bilqis_mlx/runtime/tests/model/test_model_topology_v2.py

python3 -B scripts/check_module_size.py
python3 -B scripts/quality/check_governance_integrity.py \
  --base-ref origin/codex/bamf-unified-base-20261028
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/error_control_plane.py --check \
  --base-ref origin/codex/bamf-unified-base-20261028
git diff --check origin/codex/bamf-unified-base-20261028...HEAD
```

Current local results:

- new B06.4 registry proof: **7/7 PASS**, zero skips;
- existing B06 numerical + B06.2 policy proof: **15/15 PASS**, zero skips;
- B01 topology/ledger/initialization/lifecycle proof: **21/23 PASS**, **2 explicit optional skips**;
- development structure: **0 violations**;
- governance integrity: **0 violations**;
- factory architecture: **PASS**;
- docs: **PASS**;
- error control: **new debt 0**;
- diff check: **clean**.

The two B01 skips are capability/evidence gates already declared by their owner:
one requires `BILQIS_BAMF_FULL_WITNESS` for a full disposable MLX allocation and
one requires `BILQIS_V1_BUNDLE_WITNESS` for a frozen historical v1 bundle. This
leaf does not convert either absence into a pass or manufacture those witnesses.

## Dependency and review posture

Issue #455 directly depends on B06.3/#454. Its own issue contract permits this
registry implementation against the frozen upstream interface while #454 is
finishing, but final turn-in must consume the actual accepted upstream receipt.
At this checkpoint #454/PR #684 remains remotely verified at its exact upstream
feature head `973f7e811519b99535e6de96ce72917a6c540d37` and
software/hosted/non-EGM clean, but remains `EGM_PENDING` because the pinned Google
EGM runner is not exposed on this execution surface. B06.4 consumes newer reviewed
unified `0cac1a27...`; final turn-in still must re-consume the accepted #454 receipt
after that prerequisite lands through unified.

B06.4 therefore remains a dependency-pending draft until #454 is accepted and
re-consumed. The same unavailable pinned Google EGM requirement applies to this
leaf's eventual acceptance. Any CoS review is defect-discovery evidence only and
must remain labeled non-EGM.

No actual student, native AdamW, teacher, checkpoint, retained generation or
human-run state is modified. No self-merge.
