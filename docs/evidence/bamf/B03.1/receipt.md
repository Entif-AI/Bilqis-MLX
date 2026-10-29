# B03.1 #442: provisional complete-member frame encoder

Status: **IMPLEMENTED_PENDING_A05_AND_UPSTREAM_REQUALIFICATION**.
This is a bounded software receipt, not a completed leaf or source admission.

Lane `codex/bamf02-b-neural` starts this slice at
`84a10e9076074b158c44e287a776d67532c34712` and consumes unified
`6b5460032fc0b19115843cce95fe8be9582af141`. The fetch found no new unified
commits. B02 consumes the provisional source-bound implementation from #439–#441
(`2cd16cb`, `a5b5feb`, `807a9b8`); A02 allocation qualification remains open.
A05 #357 has no integrated `frame_compiler.py` here. Its concrete record on the
sibling lane was inspected read-only; no sibling code was imported or merged.
Only reviewed unified may supply that implementation.

## Input and output contracts

`encode_frames(compiled, atom_vectors, parameters)` accepts only B03-owned
`FrameEncoderInput`, schema `bilqis.mlx.frame-encoder-input/provisional-v1`.
It is explicitly **A05_COMPILER_SCHEMA_PENDING**, not an implementation of A05's
`CompiledFrameBatch`. Requests are immutable batch/position/member tuples. Each
position contains every concept-valued binding of one A13 projected frame,
in canonical role/occurrence order, with exact source frame/member handles.
Coordinates are rederived through B02 FeatureRequest. Each row uses one
projection digest and contains no duplicate frame handle. Rows have equal frame
counts; members can vary per frame. Every tensor is FP32 `[members,768]`.
Members are complete and unmasked; atomic, partial, empty and nested input
assembly belongs to #443/#444 and actual A05 integration.

The caller supplies B02 atom embeddings in that same order. This bounded seam
does not independently authenticate the numerical origin of those arrays.
Actual compiler source-position maps, cache identities, masks, source ordering,
embedding correspondence and fixed-prefix/future-suffix invariance must be
qualified at the actual A05/B03/B11 assembly. Arbitrary objects are rejected;
there is no guessed A05 field parser or production caller.

Output `FrameEncoding`, schema `bilqis.mlx.frame-encoding/v1`, contains FP32
`global_seeds[batch,positions,768]`, the original member tensor tuple object,
the original immutable source request tuple object, and per-position
`FrameFactorTerms`. Requests retain exact FrameInstance source span, parent,
occurrence, scope and role/occurrence coordinates through their projections.
Factor terms contain raw schema128, arithmetic mean role128, shared projected
type_role768, original requests, semantic release and feature-manifest digest.
These are computational outputs, not eligibility/admission credentials.

## Equations and ownership

B02 owns `frame_factor_terms`: it validates complete source member groups,
uses actual A06 `features_for`, and gathers shared raw schema/role tables with
the exact-ID overflow vector. It also returns the shared composer's mean
type/role768. No inversion of projected features or independent feature table
is introduced. Both table gathers retain gradients.

B03 implements B01's 192-channel schema-query/member-key/member-value pooling,
single-head interaction attention over projected member values, interaction
residual RMSNorm, same-weight re-pooling, sigmoid pool gate, summary projection
of `(schema128+mean_role128)/2`, and final RMSNorm with epsilon1e-5. Every member
in this bounded input is present, so attention has no masked entry. Positions
and role features arrive through the actual B02 atom embeddings. The pass
does not rerun a backbone or use depth-selector128 weights.

`frame_encoder_parameter_view` validates the complete B01 tree and borrows
exact frame/shared-feature tensor objects. The encoder also validates the
canonical prefix names/shapes/dtypes from B01 and finite input/parameter values.
Invalid input uses the existing typed MODEL_TOPOLOGY error. No parameter,
optimizer, release, source grant, checkpoint or model generation is created.

## Observed proof

Red: the new owner suite failed at import because `frame_encoder` did not exist
(local validation log `2026-10-29T13-16-51-588Z-62520.log`).
Green: the combined new encoder8 and existing B02 owner15 tests pass **23/23,
zero skips**, using `.local/bamf-lane-b/.venv/bin/python -B scripts/run_tests.py`
on `learning/tests/test_frame_encoder.py` and `test_frame_embeddings.py` through
the validation-output runner.

An independent NumPy implementation checks literal output against all B01
equations. Source-grounded role-swapping changes the seed. Repeated concepts
retain separate role/member handles. A real B02 embedding-to-frame backward
reaches the identity bank, shared role/schema tables and all active frame
tensors; `frame.empty_seed` is intentionally unused in this complete-member
slice. Separate member gradients are nonzero. Batch row isolation has exact
output equality and zero foreign-row gradient. Raw overflow factors match an
independent SHA256 expansion. Reordered/incomplete/mixed-source groups,
unknown compiler objects, bad shape/dtype/nonfinite tensors and invalid full
parameter trees reject. The view retains canonical tensor object identity.

Fresh EGM contract review at pin
`b3a35956759bf7f024af2ff061b2e0b44b438e4c` required an explicitly provisional
adapter and source-bound raw factors; both are present. Fresh-context turn-in
review returned **PASS_FOR_PROVISIONAL_SOFTWARE**, no Blocker or Major, and
independently reran23/23 tests. No #442 closing link is justified before actual upstream
qualification. PR #552 is the cumulative human-review gate.

IPR-0220 remains open. PM-2026-10-29-001/003/004, RC-024/PAT-028 and prior
controls remain applicable. Durable student, its AdamW, teacher, champions and
original artifacts are unchanged. Actual source coverage, learning and
retention are unmeasured. Human initiation owns durable training. Next action:
push the scoped receipt, then consume
actual A05 through unified or continue another independently ready Lane B leaf.
