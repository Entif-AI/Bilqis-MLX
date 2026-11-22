# Issue #1539 verification

Issue: `Entif-AI/Bilqis-MLX#1539`

Branch: `codex/1539-candidate-step-overhead-20261122`

Verified implementation head: `9382495d3f604c81b8640f9574268ee65315485b`

Consumed `main`: `d3d03c222c1f880cc4f0f89d85a71eb15d7a3c6a`

## Representative workload

The acceptance witness uses the same representative workload that motivated #1539:

- entrypoint: `bilqis_mlx.runtime.bamf_operator.session.prepare_bamf_visit`
- capability: `A.EDGE`
- candidate horizon: 4 steps
- logical batch: 4 rows
- compiled positions: 114 per step
- one MLX worker on Apple Metal
- checked-in bootstrap A01 Atlas artifact
- disposable learner and data plane
- no publication to the human production learner

PR #1562 changed the operator default logical batch to 32 rows while preserving 4 rows as
the source-balance floor. The #1539 witness therefore pins `batch_size=4` explicitly.
Using the new 32-row default would change the neural workload to 912 compiled positions
per step and would no longer measure the workload used by the #1539 acceptance target.

## Final performance result

The final merged-head witness passed:

- median candidate-step wall: `0.7540267499862239 s`
- max candidate-step wall: `0.8366400410886854 s`
- target: `<= 1.2 s`
- stretch: `<= 1.0 s`
- terminal step: `0.8366400410886854 s`
- terminal motif staging: `0.07887916709296405 s`

All four steps preserved the required execution invariants:

- one gradient launch per step
- one vectorized microbatch per step
- zero scalar fallback rows
- zero B11 Atlas reloads
- zero cold source requalification rows
- zero feature-manifest rebuilds
- zero full candidate-identity computations
- zero candidate-identity numerical bytes hashed

The exact per-step receipt is in `candidate-step-witness.json`. The detached-run custody
receipt is in `detached-run-receipt.json`.

## Root cause and repair

The first valid four-step witness on the initial #1539 implementation measured a median
of about `0.780 s`, but its terminal step reached about `1.545 s`.
`motif_staging_wall_seconds` accounted for about `0.757 s` on that step, and the same
step performed two full candidate-identity computations over about 1.91 GB of numerical
state.

The terminal motif path was reopening accepted custody and recomputing canonical
candidate identity even though the visit already held an authenticated accepted parent
and currentness transaction. The repair keeps terminal motif sealing and staging on that
warm custody path. The cold fallback remains available for callers that do not hold the
visit-bound accepted authority.

This preserves fail-closed currentness and optimizer admission. It does not reuse stale
candidate execution identity or generation identity.

## Focused regression proof

After merging current `main`, the focused affected set passed:

```text
..........                                                               [100%]
10 passed in 0.44s
```

The set covers:

- terminal progress mutation without synchronous dashboard drawing
- staged observation activity without synchronous durable writes
- step-boundary observation staging
- visit-bound accepted-priority authority reuse
- accepted-parent motif sealing without bundle reload
- accepted-parent motif staging without full candidate-identity hashing
- resource/session continuation under the current logical-batch contract

## Inherited baseline debt

Two broader pre-neural assertions failed identically on the feature branch and on
pristine `main` before this turn-in:

- `accepted_cache_currentness_count`: observed `17`, expected `16`
- `candidate_identity_full_computations`: observed `8`, expected `0`

Those failures are inherited baseline debt and are not changes introduced by #1539.
They were not modified in this issue.

## Witness custody

The final detached run completed with return code 0 and reported `source_mutated=false`.
The source snapshot and mutation-guard digests match before and after the run. The
witness used fixture teacher/source authority only to compose a disposable, internally
consistent test environment. Production teacher authority code was not patched.
