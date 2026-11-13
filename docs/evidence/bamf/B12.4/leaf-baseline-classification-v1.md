# B12.4 leaf-gate exact-base classification v1

Date: 2026-11-06
Issue: #477 / B12.4
Reviewed-unified base: `3899649586b105b075e92f0ee3c51e80c379b473`
Semantic implementation: `fef4146c3bad484ae9cb5e608618b3eb6e4a9c5e`
Evidence head at classification: `f1991ae815ea3d466c41a1e6982d3c8218152535`

## Candidate leaf-gate result

Command:

`BILQIS_TEST_BASE_REF=3899649586b105b075e92f0ee3c51e80c379b473 BILQIS_QUALITY_BASE_REF=3899649586b105b075e92f0ee3c51e80c379b473 npm run verify:leaf`

The quality phase passed structure, governance, BAMF flow control and all 15
flow-control regressions. The differential leaf phase completed with **301
passed, 14 skipped, 7 failed, 1 collection error, 206 subtests passed**.

The seven failures were:

- five tests in `test_atlas_cache_authority_currentness.py`, each stopping at
  `BAMF_GENERATION_ACCEPTANCE_REQUIRED` before cache behavior;
- one test in `test_atlas_cache_authority_integration.py`, stopping at the same
  B13 generation-acceptance requirement;
- `test_atlas_cache_policy.py::CachePolicyTests::test_reference_candidate_evaluation_is_exact_fp32_only`,
  where pytest-xdist/execnet failed while serializing NumPy's `dtype('float16')`
  subtest metadata.

The collection error was unchanged
`bilqis_mlx/runtime/tests/model/test_backbone_group_inputs.py`, whose legacy
wrapper imports the pre-relocation module
`bilqis_mlx.runtime.tests.model.test_backbone_group_numerical`.

## Exact-base reproduction

A first comparison accidentally used a stale local unified worktree at
`309c727a7fa33401a18442bb652a2e55413a4e69` and was rejected as evidence. A new
detached worktree was then created at the exact consumed base
`3899649586b105b075e92f0ee3c51e80c379b473`. The following checks were run there:

1. `python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/model/attention/cache/test_atlas_cache_authority_currentness.py bilqis_mlx/runtime/tests/model/attention/cache/test_atlas_cache_authority_integration.py`
   -> **1 passed, 6 failed/errors**, with all six stopping at
   `BAMF_GENERATION_ACCEPTANCE_REQUIRED`.
2. `python3 -B -m pytest -q -n 4 --dist=loadscope --import-mode=importlib bilqis_mlx/runtime/tests/model/attention/cache/test_atlas_cache_policy.py::CachePolicyTests::test_reference_candidate_evaluation_is_exact_fp32_only`
   -> **1 failed** with the same `execnet.gateway_base.DumpError` for
   `numpy.dtypes.Float16DType`.
3. `python3 -B -m pytest -q --import-mode=importlib bilqis_mlx/runtime/tests/model/test_backbone_group_inputs.py`
   -> the same collection-time `ModuleNotFoundError` for the pre-relocation
   `test_backbone_group_numerical` module.

The exact-base detached worktree was removed after reproduction. These failures
are therefore inherited at the precise B12.4 base and are not candidate-owned
regressions. They are not used as #477 acceptance evidence.
