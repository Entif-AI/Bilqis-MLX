# B04.3 | Native grouped-query attention, cache identity and FP32 oracle

- Issue: #447; parent B04 #350; Lane B.
- Original immutable implementation head:
  `06cc296a7f62a52c142058e306399f11559e8800`.
- Reviewed unified ancestor:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
- Independent Goldfish EGM: **PASS**, zero Blockers/Majors.
- Turn-in: pending cumulative Lane B candidate integration and GitHub readback.

The existing `atlas_attention.ccgqa` uses native MLX fused
scaled-dot-product attention with Q [B,16,T,24], K/V [B,8,T,24],
scale 1/sqrt(24), no KV tiling, causal/valid/scope/sequence
masking and exact zero for all-masked queries. Convolution
precedes nontraditional RoPE over all 24 Q/K coordinates.

The derived decode cache binds layer, generation, exact parent
prefix digest, next offset, installed MLX version, RoPE variant,
8-head KV shape, source scopes, sequence IDs and validity.
An extended cache cannot be substituted for an earlier prefix.
No v1 checkpoint, optimizer or source admission state is touched.

## Prime and independent verification

The prime ran the full owner suite against the installed MLX
backend: **12 passed, 0 failed, 0 skipped**. The test-owned
independent NumPy FP32 oracle explicitly computes QKV projection,
oldest-to-current depthwise convolution, RoPE, grouped head
mapping and attention softmax. Other tests cover full/chunked
parity, stale-cache rejection, fresh earlier-prefix equality,
future-suffix isolation, padding/all-masked zeros and real
gradients to all Q/K/V/conv/output parameters.

Independent Goldfish readback of immutable `06cc296` verified
the exact source, source/test correspondence and observed
installed MLX signature, and returned **EGM PASS with zero
Blockers/Majors**. It performed source inspection and an MLX
version/signature probe, not a second owner-suite execution.

B04.4 ledger integration and B04 parent acceptance remain
separate; no self-merge or live student training is claimed.
