# #1618 | Selective participation and exact activation reuse

Research spike, not an admitted trainer policy. Base: `83671fea5420e13499d83c92b31ca96f44b2a4fc`.

## Governing dependency map

B01 owns the parameter census (`runtime/topology_v2/ledger.py`), B09 derives eligibility and per-row participation (`learning/_retention/_atlas_plasticity_base.py`, `_atlas_plasticity_policy.py`), B11 owns the source-bound numerical execution (`runtime/_model/backbone/atlas_model_forward.py`, `learning/source_atoms/backbone.py`), and B12 owns optimizer update and candidate custody (`runtime/_model/atlas_optimizer.py`, `learning/_retention/_atlas_candidate/step.py`, `transaction.py`). The ordinary C08 candidate path calls `derive_participation_inputs` before invoking the B12 owner; it does not authorize a new plasticity transition.

| Region | Actual support and dependency frontier | FAST implication |
| --- | --- | --- |
| Source compilation | Source release, semantic catalog, admitted graph, source authority, compiled task/frame, masks and sequence scope, topology/extents | Parameter-independent preparation may be reusable on identical source/contract; use existing owner caches, not an activation cache. |
| Input encoding | Gathered `identity.bank.*` rows, `features.*`, `frame.*`, source inputs and authority | Young identity rows may train; source input activation is not uniformly invariant. |
| Input motif read | Input hidden state, motif allocation/map, selected `motif.page.*` rows, `motif.site.0.*` | FAST-eligible even when dense layers are frozen. |
| Blocks 0–3 | Input/motif result, `blocks.0.*` through `blocks.3.*`, exact validity/scope/positions | Dense weights are SLOW; activations inherit mutable upstream support. |
| Mid-depth motif, depth selection, adapter | Group-0 hidden state, original and group summaries, `motif.site.1.*`, selected motif rows, shared `depth.*`, `plastic.group.0.*` | FAST motif and adapter may change next group's input. Shared depth parameters span groups. |
| Blocks 4–7 and 8–11, depth selectors, adapters | Prior group and residual history, masks, each group's dense leaves, `depth.*`, respective `plastic.group.*` | No unconditional activation reuse across FAST updates; every downstream group inherits preceding changes. |
| Refinement and readout | Group output, query-specific refinement choices, `refine.*`, `readout.*`, tied semantic banks and valid answer choices | SLOW readout parameters do not freeze outputs; tied young identity rows and upstream FAST updates matter. |

A numerical region is reusable only when its complete transitive support is unchanged, its inputs and numerical/semantic contracts are identical, and no required differentiated path is cut. For a cached detached prefix, every participating upstream parameter must be frozen for the differentiated objective. A thaw invalidates even before weights change. A candidate's rejection discards its speculative cache; a new admission, source/scope/mask/position change, changed upstream activation, or changed eligible support cannot reuse stale output. Never enter speculative derived state into accepted custody.

## Bounded comparison

The research harness under `scripts/experiments/issue1618/` uses the native C16 disposable fixture and C05 retention owner in ordinary mode. The only changed learning variable is the existing B01/B09 group-eligibility mask selected at the issue-local C08 seam (FULL versus FAST). No ADAPTIVE transition is claimed, no production policy is modified, and no candidate is published. Both arms start from the same deterministic genesis state, draw the same B.AND lesson, use matched optimizer/seed, batch and horizon, and score a fixed row-disjoint target/sibling/earlier-grade cohort in addition to native C05. The C05 cohort itself may depend on candidate identity and is not the matched comparison instrument. An untrained genesis has no established protected baseline; earlier-grade fixed scores are diagnostic rather than evidence of preservation of an earned baseline.

`frozen_region.py` is a standalone numerical proof: exact tensor-byte keys and bounded single-entry storage, no production integration or hot-path hashing recommendation. It proves value and suffix-gradient equivalence only for the declared frozen dependency support; an enabled upstream gradient bypasses the cache. The native arms deliberately do not cache activations: FAST alone does not establish the required frontier. Report actual numerical/retention outcomes and separate fixture throughput from full trainer throughput. Compare at equal attempted steps; wall-time normalized rates are not a matched-wall-time experiment.

Reproduce with the native MLX environment:

```sh
python3 -B -m pytest -q scripts/experiments/issue1618/test_frozen_region.py
python3 -B -m scripts.experiments.issue1618.run --mode FULL --batch-size 32 --horizon 4
python3 -B -m scripts.experiments.issue1618.run --mode FAST --batch-size 32 --horizon 4
```

Run the two native arms sequentially in a detached, otherwise idle accelerator window. The native measurements remain pending until the run receipt closes. No performance or retention conclusion is inferred from the proof alone.
