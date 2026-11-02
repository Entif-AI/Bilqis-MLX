# B13.3 cache separation and genuine historical-v1 reader witness

2026-11-02. Issue #480; parent #372; Lane B #343. Authority: IPR-0220.
Consumed unified and Lane B: `67c964a1548cb0075a28a90aa2565d8bdab0fd71`.

## Observations and implementation choice

The existing owners already implement the required separation. `bamf_bundle.codec`
serializes named learning state and eight strict sidecars; it does not serialize
inference caches. `mlx_checkpoint.load_semantically_bound_bundle` retains the v1
reader. `topology_lifecycle.dispatch_model_factory` rejects checkpoint import into
v2 before either factory runs. This change adds witnesses, with no runtime policy,
optimizer, schema or checkpoint changes.

`test_cache_separation.py` saves a small disposable numerical B12 candidate using
the established test geometry and reserve patch. It asserts the exact durable file
set, introduces corrupt disposable cache bytes, then deletes those bytes. Both
cold reads preserve weights, both moments, local update counts, optimizer step,
plasticity policy, motif allocation, teacher, ABI, compiler/correction and evaluation
records. Every durable file remains byte-identical. This is a numerical fixture,
not a source-qualified retained generation.

`test_frozen_v1.py` requires an explicit external archive path and pinned manifest
SHA. Without both it skips as NOT_MEASURED. The test reads the archive using the
existing historical reader on CPU, validates the historical six-layer geometry and
absolute-position tensor, checks own-AdamW state and rejects both direct v2 bundle
loading and architecture dispatch before v2 allocation. Genuine manifest bytes are
indexed into an isolated temporary data plane, so direct rejection is not merely a
missing-node failure. Every source file is hashed before and after. No training,
archive copy, source-file write, cache repair or checkpoint publication occurs.

## Actual archive receipt

- Archive: `runs/codex-0001-prometheus/bundles/best-5534-bacead84d07e` under the
  workstation's existing `/Users/emilie/Code/bilqis-mlx` checkout.
- Manifest SHA-256: `d44011f9d1de5c99cedceae325181ff5597bd1640b5046e91b0bfd8f7ee5bd13`.
- Tensor SHA-256: `8156b322981009e20bd255c803dc5efc6a468a81a724a892e1ba2814918bd3be`.
- v1 schema, 39 parameter tensors, 119 stored arrays, AdamW step 128440.
- Historical 6-layer / 24-head / width-384 / context-96 geometry passed validation.
- This is a genuine saved historical MLX whole-student bundle, not the original
  native `student-116760-7e9af4651f28.pt` checkpoint and not an admitted BAMF model.

## Reproduce

From repository root, select the immutable archive and independently pin its SHA:

```sh
export BILQIS_FROZEN_V1_BUNDLE=/absolute/path/to/archived/v1/bundle
export BILQIS_FROZEN_V1_MANIFEST_SHA256=d44011f9d1de5c99cedceae325181ff5597bd1640b5046e91b0bfd8f7ee5bd13
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle
```

Observed: **33/33 passed, zero skips**, including the real archive witness. Without
archive selection: 32 passed, one explicit unmeasured skip. Historical ABI guard
passes locally; independent external expected fingerprint remains unconfigured.
The source-only/default CI result must not be reported as a genuine-v1 read.

## Remaining acceptance

#479 and remediation #709 still require the source-qualified accepted-generation
publication/lock path, reconstructed Factory next visit and next controlled
optimizer step, cross-backend continuation and retained-learning evidence. #708
owns accepted-generation predecessor authority. This proof does not supply those
receipts or full #480/#372 acceptance. Final pinned EGM remains pending until the
complete dependency-qualified candidate is merge-ready. No real student, matching
AdamW, teacher, source release or human training was changed. Existing related
incidents PM-2026-11-01-004/005 remain provenance; no new runtime defect was found.
