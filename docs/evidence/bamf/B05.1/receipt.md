# B05.1 | Shared 128-channel depth selector and normalized residual weights

- Issue: #449; parent B05 #355; Lane B.
- Isolated candidate branch:
  `codex/bamf02-b05-candidate-20261029` (local only).
- Consumed reviewed Lane B head:
  `5b2b64035f37f7e30174ed08b0ad27734bc72e9a`;
  consumed unified `6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
- Owner module: `bilqis_mlx/runtime/block_attnres.py`.
- Source feature schema:
  `bilqis.mlx.depth-frame-features/v1`.
- Completed summary schema:
  `bilqis.mlx.depth-summary/v1`.
- Independent EGM: **PENDING**.
- No shared Lane B push, integration or live training is claimed.

## Exact implemented equations and ownership

The shared FP32 selector consumes current [B,F,768], an ordered
tuple of h0 plus only the completed group summaries g1..gk,
and A06-composed `frame_seed` and `type_role` [B,F,768].
Each summary carries its source identity and completed layer
(h0=0, g1=4, g2=8, g3=12). A boundary-group tag requires
exactly the corresponding prefix; reordered or future
summaries fail closed. No target label or future teacher
content is accepted by the input record.

Shared bias-free Q/K/V matrices [128,768] and output
[768,128] implement the original B05 equations:
q=Wq*RMSNorm(current+frame_seed),
key_i=Wk*RMSNorm(summary_i+type_role),
alpha=softmax(dot(q,key_i)/sqrt(128)) over only available
sources, mix=sum(alpha_i*(Wv*summary_i)),
and output=current+g_k*(Wout*mix).
The per-boundary gate is
g_k=0.1*sigmoid(dot(gate_vector,RMSNorm(current))+gate_bias),
with B01's zero gate vector and log(1/9) bias yielding
exactly 0.01 at initialization.

All tensors are FP32, with exact shape/name validation
against the B01 local selector parameter names. The
module allocates no trainable parameters, changes no
optimizer or checkpoint state, and does not re-run
backbone layers. The factor composer remains upstream
A06 authority; this module does not invent type/role
semantics or inspect source labels.

## Prime verification

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_block_attnres.py`:
**9 passed, 0 failed, 0 skipped** on installed native MLX.
An independent NumPy FP32 oracle recomputes the
RMSNorm/QKV/source softmax/gate/output equations. Literal
tests verify weights sum to one, initial gate 0.01,
boundaries 1/2/3 use exactly 2/3/4 ordered sources,
future/reordered groups reject, all shared selector
and gate tensors and all four completed source states
receive finite nonzero gradients, and
wrong-shape/dtype/source release/parameter names fail.

This is an isolated implementation candidate. The final
source-qualified factor-composer integration, per-boundary
B01 tensor-ledger view, independent EGM and human-reviewed
Lane B turn-in are still required.

## Independent review repair

Goldfish worker-4 found zero Blockers and one Major proof gap
at immutable `7f40b3a`: the existing gradient test
differentiated selector parameters but not the h0/g1/g2/g3
source states. The repair adds a nondegenerate native
MLX gradient witness for all four completed source
summaries at boundary 3. The full owner suite now passes
**9/9** after additional adversarial repairs.

Independent adversarial review at `7f40b3a` found
three Majors. Two are repaired locally: non-finite
FP32 input/source/parameter tensors now fail closed
before producing a residual, and public `depth_select`
now accepts only a sealed, immutable
`DepthParameterView` produced by full B01-ledger
validation and bound to the exact boundary group.
Anonymous local Q/K swaps and cross-boundary gate
substitution cannot enter the public path. The
remaining Major is **source-summary provenance**:
a caller could relabel a genuine future g2 tensor as
g1 because B05.2's trusted backbone group-capture
receipt is not yet available. This is not waived.
Do not wire the candidate into production, push it
as accepted B05.1, or close the issue until that
source-owned group-boundary authority is integrated.

Fresh immutable-head re-review of the two repairs
remains pending. A06 factor-composer and B13 custody
integration are also separate gates.

Latest combined B01/B04/B05 native MLX owner preflight:
**41 passed, 0 failed, 2 optional witness skips**.
