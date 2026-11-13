# A02.1 prospective factor authority repair v1

## Disposition

`SCOPED_IMPLEMENTATION_EGM_PENDING`

This repair removes the circular authority seam identified by the A02.1 preflight. It does **not** complete A02.1, activate a semantic identity, mutate a durable student, or satisfy A02 parent acceptance.

## Root cause

A02 must initialize a newly admitted identity row from a source-qualified FP32[768] factor. The accepted A06 manifest contains feature rows only for active identities. B02.2 had a provisional source-composed new-row proposal, but B02 depends on A02 and explicitly requires A02 qualification before activation. Treating B02 as A02's authority provider therefore created a dependency cycle.

## Repair

- A06 now exposes `plan_prospective_identity_features(...)`, which derives immutable type/graph features for source-known inactive ABI identities without activating them. It preserves the accepted predecessor feature digest and extends only the categorical type map needed by the proposed batch.
- B01 topology now exposes `project_identity_source_factor(...)`, a read-only type/graph projection bound to `GenerationExtents.factor_map_digest`. Contextual role/schema/local features remain outside identity seeding.
- A02 now has `semantics/atlas_vocabulary.py:prepare_identity_factors(...)`, which composes the A06 source plan with the B01 numerical projection. It has no B02 dependency.
- `initialize_bamf_row(...)` remains the existing B01 row initializer and still adds the deterministic seeded residual. No optimizer update or persistent state write occurs.

Authority direction is now:

`A01/A06 source snapshot + feature authority -> A02 prospective factor staging -> A02 allocation/activation -> B02 downstream consumption`

## Failing-before witness

Before production changes, focused tests failed on missing `plan_prospective_identity_features` and `project_identity_source_factor` imports. The default interpreter also lacked `rdflib`; all semantic/MLX verification below therefore uses the established Python 3.12 environment rather than treating that environment deficiency as a product failure.

## Verification

Command:

`/private/tmp/bilqis-c-runtime-py312/bin/python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_vocabulary.py bilqis_mlx/semantics/tests/test_atlas_features.py bilqis_mlx/runtime/tests/test_model_topology_v2.py`

Result: **33 passed, 0 failed, 2 expected optional skips**.

Additional checks:

- `git diff --check` -> clean.
- `python -m compileall` on changed production modules -> clean.
- `scripts/check_semantic_boundaries.py` reports only the three pre-existing `semantics/frame_adapters.py` import-boundary failures; this repair adds no new boundary finding.
- Static readback confirms the A02/A06/B01 repair modules do not import `bilqis_mlx.learning.frame_embeddings`.

## Remaining A02.1 work

This repair supplies the missing source-authoritative prospective factor seam. A02.1 still owns the actual append-only bank allocation/activation transaction, active mask/output-domain update, candidate-state integration, rejection/crash proof, exact 8191/8192/16384 boundary acceptance, and final fresh Google EGM turn-in review.

The exact Google EGM review required by #399 could not be run in this Chat execution surface. A fresh local review worker also failed to start because its configured model/reasoning combination was unavailable. No substitute review is represented as EGM.
