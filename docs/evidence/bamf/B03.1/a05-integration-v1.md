# B03.1 #442 and B03.2 #443: actual A05 atom/closure integration

Status: **VERIFIED_ACTUAL_A05_SOFTWARE_BOUNDARY; A02_QUALIFICATION_PENDING**.
This supersedes the A05-absent observation in the earlier B03 receipts.
A02 allocation/embedding qualification and complete B03 acceptance remain open.

Reviewed unified advanced to `ac498099b56a38f3b669e16d30f8bab580709f49`.
Lane B merged it without conflicts at
`5a2d84104e9bd20bfeba90d2e374069ebccb1573` and pushed that merge.
Actual A05 implementation/EGM receipt `de5bb9c562992e3620a539dc5519f26a7374e772`
is now consumed through unified, not a sibling merge. Immediate affected
A05/B03/B02 validation passed45/45 before B03 edits.

`CompiledEncoderInput` consumes actual A05 `CompiledFrameRows`, one current
`FrameCompilerConfig` per row, A06 `AtlasFeatures` and B01 `GenerationExtents`.
Input schema `bilqis.mlx.compiled-encoder-input/v1` is a B03 binding of those
actual records; it neither replaces nor guesses A05's compiled schema.
Construction and every encoding reconstruct each visible A05 row and recompile
it against its supplied current config, requiring complete record equality.
This rechecks current grants, rights/temporal/correction/policy state, schema
payload/map, sidecars, exact prefix/positions and cache identity. Stale compiler
data is not treated as a current source permission. No hidden targets enter
the input; configs are supplied by the compiler owner, never inferred here.

For closures, the adapter reprojects exactly the source-approved closed frame
set at the row prefix and checks the exact A05 context digest. Each complete,
concept-only frame supplies canonical FeatureRequests through B02, preserving
role/occurrence/source-member identity. Atomic raw positions carry only the
actual A05 SourceAtom and position; no token-to-semantic mapping is invented.
Empty, AtomicFrame and child/nested closures remain unsupported in this slice
and reject. Their separate B03 outcomes are not silently implemented here.

`CompiledEmbeddingVectors`, schema
`bilqis.mlx.compiled-embedding-vectors/v1`, supplies unpadded raw atom tensors
`[visible_end,768]` per row and exact ordered `MemberEmbedding` records. Each
member record binds one supplied FP32 `[768]` vector to one exact source
FeatureRequest. Missing, reordered, extra or foreign requests reject. Raw atom
row lengths are exact; future and padding vectors are not accepted. Numerical
vector origin is the embedding owner's obligation, consistent with the
original API's supplied atom vectors; this receipt does not qualify A02 or
assert that a caller-provided numerical vector proves source semantics.

Every actual compiler position receives one output: raw ATOM vectors pass
through unchanged; complete CLOSURE members use the existing B01 equations.
Original A05 padded-position tuples are returned as handles; the actual
CompiledFrameRows object is retained in the output. Global seeds have shape
`[batch,max_positions,768]`; padding is exactly zero and has no source handle.
Member matrices and factors retain per-row unpadded lengths. Raw positions have
no fabricated semantic factor summary. Output schema is now
`bilqis.mlx.frame-encoding/v3`, adding actual compiler metadata and handles.
The earlier numerical fixture inputs remain for focused equation tests.

Red import failure: local log `2026-10-29T13-43-01-575Z-97003.log`.
Current affected proof **48/48**, zero skips: encoder13+B02existing15+A05owner20.
Actual A05 interleaved8 atoms+closure preserves literal raw values and matches
the previous B02→B03 closure seed; every closure member receives a nonzero
gradient and raw atom gradients are exactly one. Prefix3 has no member request
or closure; changing source suffix after3 leaves output identical. Two actual
unequal A05 rows preserve the shorter row's output and expose only None handles
for its zero padding. Revoked config, changed policy/schema contract and
missing/reordered/extra member vectors reject. Source operator/hygiene checks
explicitly include new/changed files; no baseline or guard is widened.

Fresh EGM actual-A05 contract review required current-config recompilation and
an exact vector/source-occurrence bijection; both are implemented. Fresh scoped
turn-in review returned **PASS_FOR_ACTUAL_A05_BOUNDARY**, no Blocker/Major, and
independently reproduced48/48, zero skips, at pin
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. #442/#443 remain open without
closing links. #443 partial raw-atom behavior is now exercised on the actual
compiler; legal empty-frame encoding and its schema proof remain pending.
B03.3 owns nested scope/handle outcomes. B11/C13 own neural-logit F05.

IPR-0220 remains open. PM-2026-10-29-001/003/004, RC-024/PAT-028 and prior
controls remain. No durable student, own AdamW, teacher, champion, original
checkpoint or source release changed. Actual learning/retention and broader
source coverage are unmeasured. Human owns integration and durable training.
Next action: fresh review/repair, push this actual boundary, then implement
the remaining legal-empty B03.2 outcome against the actual compiler schema.
