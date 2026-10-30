# B12.3 private preclip numerical seam

Issue #476 remains open. This cut implements its numerical mask-before-clip
clause against supplied masks; actual execution provenance and retained-state
integration are still required. Source predecessor is
`0a04c3c7a38f8d6a7cbae3c2f9635f2778c8edcd`, consuming reviewed unified
`da0431bee37c0e4f766f05cc94ceb6b23ac7d054` (unchanged at issue-boundary fetch).

The private `_masked_clipped_gradients` validates exact FP32 gradient keys,
shapes and Boolean scalar/row masks against the numerical state. It uses
selection to zero frozen rows before calling the existing `mlx_parity`
global L2 clipping implementation. Nonfinite gradients and a nonfinite
selected norm reject; masked finite large gradients cannot affect the norm.
`_adamw_update(max_norm=...)` routes through that helper before any native
AdamW moment/decay arithmetic. Without max_norm the already-clipped input
contract remains unchanged. Invalid limits reject before an update.

Red: two missing-API failures with ten existing tests passing. Green:
**12/12 native MLX tests**, zero skips. The adversary changes frozen gradients
from zero to +/-3e38 while the selected row remains [3,4]; both norms equal5
and clipped arrays and resulting parameters/moments/counts match exactly.
Tests also cover invalid limits and overflowing selected norm rejection.

Fresh independent EGM at pin
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`: scoped PASS, zero Blocker/Major;
independently reproduced12/12. Explicit operator audit and diff check pass.

No model-derived participation grant, historical scalar-step migration,
accepted global step, persisted establishment ages or retained-candidate
publication was added. #475's complete transaction and #476's remaining
clauses stay open. No closing links or full B12 acceptance claims.

IPR-0220 remains open; PM-2026-10-29-001/002/003/004/006 controls remain.
No durable student, own AdamW, teacher, champion or original changed.
Learning/retention remain unmeasured. Human owns unified integration and
actual durable training initiation.
