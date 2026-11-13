# B04.4 | B01 tensor-ledger attention prefix witness (staged candidate)

- Issue: #448; parent B04 #350; Lane B.
- Isolated implementation candidate branch:
  `codex/bamf02-b07-candidate-20261029` (local only).
- Consumed reviewed unified head:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
- Existing B04.1/B04.2 source:
  `e40b19d`; B04.3 source:
  `06cc296`.
- Independent EGM: **PASS**, zero Blockers/Majors, at immutable
  `fc91591641ad679a792944cc2d3e4dd61eb279cc`.
- Lane B PR turn-in and human integration remain separate.

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

## Independent Goldfish EGM

The reviewer used an immutable archive of `fc915916` rather than
the advancing live worktree, and independently executed the full
attention suite: **14 passed, 0 failed, 0 skipped**. A separate
full-ledger probe confirmed 214 unique B01 tensors, seven
identity-preserving local references, native 16Q:8KV geometry,
exact agreement with direct attention parameters, and rejection
of missing, extra, wrong-shape and wrong-dtype tensors anywhere
in the full model. **Zero Blockers or Majors** remained.

B04.3's separate EGM also returned PASS at `06cc296`.
Neither leaf review closes B04 parent integration, neural
training, generation custody or human merge approval.
