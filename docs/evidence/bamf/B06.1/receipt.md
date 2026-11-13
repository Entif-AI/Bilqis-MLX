# B06.1 #452: private numerical recurrence

Status: **VERIFIED_PROVISIONAL_NUMERICAL_KERNEL; SOURCE_INTEGRATION_PENDING**.
No completed-leaf or production refinement interface is claimed.

Lane B starts at `bce4b879213445249703e20d8cf43bab11f1e9e6`, consuming
unchanged unified `6b5460032fc0b19115843cce95fe8be9582af141`. Direct B03
and B05 dependencies are usable only for bounded software work: B03 complete
and atomic slices are provisional pending actual A05 compiler/A02 embedding
qualification; B05's trusted completed-group summary capture remains missing.
The synthetic summary relabeling negative control in B05.1 remains an open
Major. This kernel adds no public source-origin claim or replacement credential.

`runtime/atlas_refinement.py` exports only a source-neutral B01 parameter view
and the private `_refine_frame` numerical seam. No `refine_selected` public API,
source/member resolver, scheduling choice, admission path, model generation,
checkpoint write or optimizer operation is introduced. Input arrays are
disposable fixtures: hidden, immutable seed and requested-role vectors `[768]`,
and a complete unmasked nonempty member matrix `[M,768]`, all FP32. They are
not evidence of actual source visibility, requested-role rights or trusted
backbone origin. Actual B03/A05/B05/B11 adapters must establish those properties
before use outside numerical tests.

The kernel accepts an integer pass count0/1/2 and the exact canonical refine
prefix. It validates names/shapes/dtypes through B01's ParameterSpec ledger,
finite inputs/parameters and finite positive-pass results. For ledger shape
enumeration, generation extents are fixed placeholders used only to obtain
extent-independent refine shapes; they confer no release/generation authority.
The public parameter view instead validates a supplied complete B01 tree and
borrows the exact canonical refine tensor references, introducing no arrays.
All invalid boundaries use the existing typed MODEL_TOPOLOGY error.

For each pass, with state initialized from hidden:

1. Normalize `state+original_seed+requested_role` using shared refine.norm and
   B01 epsilon1e-5, then apply refine.query `[192,768]`.
2. Attend to the same member keys/values with score scale1/sqrt192 and softmax
   over the member axis. Project the192-channel mixture through refine.output.
3. Add the residual scaled by
   `0.1*sigmoid(dot(refine.gate_vector,RMSNorm(state))+refine.bias)`.
   Zero gate vector and log(1/9) bias give initial gate0.01.

The same seed, member keys/values and parameter tensors are reused in pass2.
Zero passes returns the original hidden object and no routing computation.
Positive passes return a separate local hidden result and three diagnostic
logits `state @ refine.route.T + refine.route_bias`. No route decision or
supervision policy is invented. Result schema is
`bilqis.mlx.refinement-numerical-result/provisional-v1`, with hidden, optional
route logits and applied pass count. Quota/selection, sampling, missing-label
auxiliary loss and answer fallback remain the other B06 leaves' obligations.

Red import failure retained in local validation log
`2026-10-29T13-30-50-399Z-39692.log`. Owner proof **5/5 real MLX tests pass,
zero skips**, through the prepared Lane B Python and validation-output runner.
The independent NumPy oracle checks one and two complete recurrence steps and
route logits. Tests prove exact zero-pass object identity, gate0.01, input
immutability, original seed recall on the second pass, literal single-member
attention, nonzero finite two-pass gradients for every refine tensor and all
four input families, malformed tensor/count/prefix rejection and exact full-tree
parameter aliases. These are numerical/gradient proofs; actual nested-role
learning, retained learning, source causality, backbone reuse and model
save/resume remain unmeasured until integrated owners provide their witnesses.

The fresh EGM contract review at
`b3a35956759bf7f024af2ff061b2e0b44b438e4c` permitted this private numerical
scope and identified the source/public-interface gates above. Fresh scoped
turn-in EGM returned **PASS_FOR_PROVISIONAL_NUMERICAL_KERNEL**, no Blocker/Major,
and independently reproduced5/5 real MLX tests, zero skips. #452 remains open
without a closing link. PR #552
continues to require human integration approval.

IPR-0220 remains open. PM-2026-10-29-001/003/004, RC-024/PAT-028 and prior
controls remain applicable. No durable student, its matching AdamW, teacher,
champion, original checkpoint or source release changed. Human owns durable
training starts/resumes/stops. Next action: scoped fresh review, repair material
findings, push the bounded software receipt, then continue dependency-ready
Lane B work while actual upstream qualification remains pending.
