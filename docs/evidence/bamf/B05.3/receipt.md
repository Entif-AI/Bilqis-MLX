# B05.3 | Exact B01 selector ledger view and diagnostic ownership

- Issue: #451; parent B05 #355; Lane B.
- Isolated local candidate:
  `codex/bamf02-b05-candidate-20261029`.
- Consumed reviewed Lane B head `5b2b640` and unified `6e83c0f`.
- Owner module: `bilqis_mlx/runtime/block_attnres.py`.
- Independent EGM: **PENDING**.
- B13 checkpoint integration: **PENDING**, not silently assumed.

`depth_parameter_view` validates the entire B01 normative
`ModelTopologySpecV2` parameter tree before returning references
to exactly five shared depth tensors (norm, query, key, value,
output) and the selected boundary's gate vector/bias. It
does not copy or allocate trainable arrays, expose feature/
identity/block tensors, or create a competing tensor registry.
Every returned shape matches B01 `ParameterSpec`; wrong
boundary, missing, extra, malformed or wrong-dtype tensors
fail closed. All three boundary gates remain distinct,
while Q/K/V/output/norm are shared.

The existing B01 ledger already declares all four shared
selector projections and three gate vectors/biases. Their
generation checkpoint custody is reserved for B13, not
implemented by this leaf. Optional source-axis alpha
diagnostics are available through the pure
`_depth_components` helper without assigning cognitive
functions to particular depth groups.

## Prime verification

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_block_attnres.py`:
**9 passed, 0 failed, 0 skipped** on native MLX
after source-state gradient, non-finite and sealed-view
adversarial repairs. The view is now an immutable
`DepthParameterView` with exact boundary binding;
the public selector rejects anonymous local mappings.
Two additional literal tests construct the full B01 ledger,
verify reference identity for three distinct gate boundaries,
run the selector through each exact view, and reject
missing/extra/wrong-shape/wrong-dtype tensors anywhere
in the full tree and invalid boundary indices. The
independent NumPy FP32 depth-selector oracle and real
gradient tests remain passing.

No optimizer, source admission, checkpoint, historical
run or live student training state was mutated. This is
a candidate pending independent review, B13 custody
integration and human-reviewed Lane B turn-in.
