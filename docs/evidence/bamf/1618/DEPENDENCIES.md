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

## First-run failure and correction

The initial detached comparison (`throughput-20261124-1618-selective-region`, PID 61262, immutable source digest `ed524a4e0ff2f5d23c6a6ce71abd9d159d9571312645f2b406c95cf45b6d5984`) completed the FULL training arm and C05 screen (`PAIRED_SCREEN_WITHIN_BUDGET`) but failed before emitting the complete arm receipt because the supplementary probe named `B.OR`, absent from the reduced-Boolean executable release. No FAST arm ran; no comparative measurement is claimed. The replacement derives the sibling from the admitted capability roster (`B.IFF`), selects a common row-disjoint seed before outcomes are measured (98318 for the 32-row fixture; 98317 collided with one training row), and compiles and evaluates the baseline probe before training. The actual-release regression test verifies deterministic row disjointness and the three selected capabilities. Both arms must still finish and match their control coordinates before interpretation.

## Matched four-step result and bounded follow-up

`matched-four-step.json` preserves both successful arm receipts and the immutable detached receipt. Fifteen control fields and the fixed cohort/parent scores match exactly. At 4 updates and the acceptance-witness rate of 1e-6, both candidates pass C05 without score change; FAST reduces attempt time from 13.6535 s to 11.6712 s and peak MLX memory from 6.2244 GB to 3.7480 GB. The ordinary-mode cost map is intentionally empty, so its raw zero gradient-launch count is missing instrumentation rather than a measured zero. The follow-up reads the existing C08 result counter at the issue-local seam without enabling strict evidence.

Predeclared follow-up: 32 rows, 1e-5 learning rate in both treatments (the existing fixture documents this previously tested rate), FULL 10 steps and FAST 10 steps for equal-step comparison, then FAST 12 steps for an approximately equal attempt-time comparison based on the four-step measured rate ratio. This is a bounded experimental rate intervention, not a default optimizer/teacher change. Report measured durations and their mismatch; do not call the 10/12 pair exact wall-time parity. Preserve the same seeded initial state, lesson, assessment and optimizer settings between the new arms. A null or harmful result remains admissible and does not authorize default FAST.
