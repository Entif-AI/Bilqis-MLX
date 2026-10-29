# A05.3 hidden-target isolation and bounded neural positions

- Issue: #410; parent A05 #357; Lane A
- Consumed unified:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
  (verified ancestor, no no-op merge)
- Direct predecessor A05.2 #409 implementation:
  `8065c52ee2c4cd4436fa92a3d0ddf7f5599036c7`
  and receipt `a4f76fcdcf9b582ae03a973a4f94b65fc3cad982`
- Pushed implementation head:
  `a9e55fb3e993c035655dd19ccf8b3110443c035e`
  (initial), then hardening
  `3d34d70e5eb9da9e683f85c6fa398209ccda8044`
- PR #546 native Development closing reference #410
  verified by GitHub GraphQL readback
- Independent A05.3 EGM: **PENDING**

## Hidden answer separation

`HiddenAnswerTargets` is a frozen integer target
tensor and mask record. `compile_training_example`
returns `CompiledTrainingExample(input_view, target_view)`
with separate custody. The model input is the existing
`CompiledFrameBatch`; it contains no target tensor,
teacher label or gold-only role hint. Changing only
the hidden target indices or target mask leaves the
entire input view, source positions, sidecars and
cache identity structurally identical.

This semantics-layer target tensor is immutable
integer data. Actual MLX tensor materialization
and neural-logit equivalence are downstream B11/C13
responsibilities, not claimed here.

## Length guard and lawful split

`MAX_NEURAL_POSITIONS=1024` counts both visible
raw source atoms and completed frame closures.
`compile_prefix` rejects an overflow with ErrorBus
`BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED` before packing,
neural-position allocation or padding. The
`CompiledFrameBatch` constructor also refuses an
oversized result.

For longer lawful source sequences,
`compile_lawful_segments` accepts a contiguous,
ordered sequence of source-adapter-declared
`LawfulSourceSegment` records. Each segment retains
its original global source span, source token
references and a source-granted boundary handle.
The boundary grant must match the exact
`boundary_evidence_digest`, actor/tenant,
purpose/jurisdiction/scope, semantic release,
rights/correction epochs and temporal frontier.
Overlaps, gaps, missing/revoked boundary grants,
cross-tenant mixing and any overlong segment
fail closed. The compiler preflights every segment
before allocating compiled positions, then returns
`CompiledFrameSegments` with exact total atom and
neural-position counts. No tokens are truncated,
invented or silently rebased across boundaries.

The source adapter owns the declaration of lawful
boundaries. The compiler does not invent split
points inside a frame or synthesize new source
authority. This preserves source-owned provenance
while permitting an original 1500-token sequence
to be compiled as two independently bounded
800/700-token segments.

## Actual accounting

`CompiledFrameBatch.stats: CompileStats` returns
actual atom count, complete frame count, neural
position count, exact per-disposition compact/
extended/atomic count-to-total shares and canonical
A04 sidecar byte count. The statistics are derived
from the actual packed positions, not estimated
from a desired model size or from padding.

## Schema versions

- `bilqis.hidden-answer-targets/v1`
- `bilqis.compiled-training-example/v1`
- `bilqis.lawful-source-segment/v1`
- `bilqis.source-segment-boundary/v1`
- `bilqis.compiled-frame-segments/v1`
- Existing `bilqis.compiled-frame-batch/v2`
  and `bilqis.compiled-prefix-maps/v1` retained.

## Executed evidence and predecessor trace

Owner `test_frame_compiler.py`: **18 passed,
0 failed, 0 skipped**. A target-only change
preserves input and cache identity. A 1024-atom
stream with one frame closure and a 1025-atom
stream fail before packing. Source-granted lawful
segments reconstruct all 1500 original tokens,
while missing grants, cross-tenant mixing, gaps
and oversized segments are rejected.

Adjacent A03/A04/A13 and A05 owner suites:
**70 passed, 0 failed, 1 optional skip**.

Predecessor: **BAMF-REQ-005**, causal input
noninterference and source-visible frame compilation.
Staged status:
`COMPILER_PREFIX_PASS; NEURAL_F05_PENDING_B11`.
The required actual 12-layer neural-logit witness
belongs to B11 #369 and C13 #385. A05 parent
integration remains open; no live training, source
promotion, optimizer mutation or merge occurred.

## Post-candidate boundary hardening

The follow-up `3d34d70` validates canonical
ATOM-before-CLOSURE ordering, complete contiguous
visible atom positions, required closure authority,
and duplicate approved occurrence IDs only when
their frame becomes causally visible. This prevents
future malformed approvals from poisoning an
earlier source prefix while failing closed at the
actual closure boundary. It also rejects empty
lawful segments. Owner tests remain **18/18 PASS**.
Independent A05.3 EGM remains pending.

The independent boundary-proof review identified
an additional test gap: previous overflow negatives
did not distinguish a correct inclusive 1024 limit
from an erroneous 1023 limit. The added literal
positive witness admits both exactly 1024 raw atoms
and 1023 raw atoms plus one completed frame closure,
while the existing 1025-position negatives still
fail before packing. This closes the reported
boundary discriminator gap without changing the
implementation's limit.
