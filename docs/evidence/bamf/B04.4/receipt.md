# B04.4 | B01 tensor-ledger attention prefix witness (staged candidate)

- Issue: #448; parent B04 #350; Lane B.
- Isolated implementation candidate branch:
  `codex/bamf02-b07-candidate-20261029` (local only).
- Consumed reviewed unified head:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
- Existing B04.1/B04.2 source:
  `e40b19d`; B04.3 source:
  `06cc296`.
- Independent EGM: **PENDING**. No Lane B PR turn-in or merge is claimed.

## Exact owner contract

`bilqis_mlx.runtime.atlas_attention.attention_parameter_view`
accepts a complete B01 `ModelTopologySpecV2`/generation-extents
tensor mapping and a layer index. It invokes the existing normative
`validate_bamf_parameters` against all B01 `ParameterSpec` entries
before returning references to only the seven attention-owned tensors
under that layer's `blocks.N.` prefix. No new trainable tensor is
constructed or copied; shared feature, depth, identity, FFN and norm
parameters remain owned by their original modules. Incorrect names,
shapes, dtype, missing or extra tensors and invalid layer indices
fail closed with catalog errors before attention computation.

The `ccgqa` forward path consumes the resulting local view unchanged.
Historical v1 parity and original model/optimizer/checkpoint state
are not touched. Full generation publication, source admission,
neural integration and human-started training remain later gates.

## Prime verification

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_attention.py`:
**14 passed, 0 failed, 0 skipped** on the installed MLX backend.
Two new literal tests construct the full B01 shape ledger, verify
identity-preserving references for two distinct layers, run zero-valued
attention through the exact view, and reject missing, extra, malformed,
wrong-dtype and invalid-layer inputs. Existing 12 attention tests
retain the independent 16Q:8KV reference, chunked/causal/gradient
and cache identity witnesses.

This candidate is not accepted until B04.3's independent review
and B04.4's own EGM, branch turn-in and GitHub receipt complete.
