# B03.2 #443: atomic fallback slice

Status: **VERIFIED_ATOMIC_SLICE; EMPTY_AND_PARTIAL_PENDING**. #443 remains open.
Base Lane B `12c6545edcec8e1e74f05ebef583e31a162ab83f` consumes unchanged
unified `6b5460032fc0b19115843cce95fe8be9582af141`.

`encode_frames` now also accepts B03's `AtomicEncoderInput`, explicitly
`bilqis.mlx.atomic-encoder-input/provisional-v1`. Its immutable batch/position
handles each bind an actual A13 ApprovedContextProjection to one AtomicFrame
and its exact sole `(<atomic>,0)` member. Invented frame/member handles and
non-atomic substitutions reject. Each row uses one projection digest and no
duplicate frame handles. The caller supplies the corresponding FP32 atom
vector as `[1,768]` per position; its numerical embedding provenance remains
an assembly obligation, as with the B03.1 provisional adapter.

The seed is the supplied vector unchanged. No frame or feature parameter is
read, allocated or differentiated. Original member arrays and source handles
return unchanged. No semantic factors are manufactured for an atomic node;
its feature-summary entry is `None`. The additive atomic output variant uses
`bilqis.mlx.frame-encoding/v2`; the complete-member output fields and equations
from #442 are unchanged. Inputs remain separate homogeneous frame/atomic
batches pending actual mixed A05 assembly.

Red import failure: local validation log
`2026-10-29T13-25-00-310Z-72272.log`. Green: encoder **10/10**, zero skips,
including the prior8 and2 new atomic cases. A literal arange768 vector is
exactly preserved. Atom-vector derivative is exactly one; every unused
parameter derivative is zero. Malformed, wrong-dtype and nonfinite vectors,
foreign member handles and complete-frame substitutions reject.

The fresh preimplementation EGM contract review identified two remaining
requirements: legal-empty schema authority and actual partial-prefix
compilation. A caller-supplied same-ID/revision schema is insufficient to
establish empty cardinality; no replacement schema authority was introduced.
Partial source membership and future-suffix invariance require actual A05
prefix records and remain unimplemented. Empty arithmetic is also not claimed
as delivered. The complete #443 leaf and parent B03 acceptance are pending;
there is no closing link. This atomic slice does not claim the partial-prefix
F05 witness, new source admission or training readiness.

Fresh EGM turn-in returned **PASS_FOR_ATOMIC_SLICE**, no material defect, at pin
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. It independently reproduced
the combined encoder10+B02existing15 proof: **25/25**, zero skips, using the
prepared Lane B environment after system Python lacked RDFLib. IPR-0220 remains open;
PM-2026-10-29-001/003/004, RC-024/PAT-028 and prior controls remain.
No durable student, matching AdamW, teacher, champion or original artifact
changed. Actual source coverage, learning and retention remain unmeasured.
Human owns integration and durable training. Next action: independent scoped
review, push the atomic slice, then consume actual A05/schema qualification
through unified or continue independent Lane B work.
