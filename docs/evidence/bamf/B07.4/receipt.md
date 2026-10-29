# B07.4 | Motif-only B01 tensor registry view

- Issue: #459; parent B07 #356; Lane B.
- Isolated candidate branch:
  `codex/bamf02-b07-pages-candidate-20261029`.
- Reviewed unified consumed: `6b5460032fc0b19115843cce95fe8be9582af141`.
- B01 normative authority:
  `bilqis_mlx/runtime/model_topology_v2.py`.
- Candidate output schema:
  `bilqis.mlx.motif-parameter-view/v1`.
- Independent EGM: **PENDING**.
- Direct prerequisite B07.3: **NOT YET ACCEPTED**.

`motif_parameter_view` first validates the **entire** B01
`ModelTopologySpecV2` / `GenerationExtents` parameter tree
against `expected_bamf_shapes` and
`validate_bamf_parameters`. It then returns a sealed,
read-only mapping of references to all declared motif
pages and exactly one site's five local tensors:
projection, norm, hidden gate, feature gate and bias.
Both sites share page tensors, but their site parameters
are distinct. No new parameter, optimizer, checkpoint,
identity, depth, feature or neural-write authority is
created. The view cannot be constructed with anonymous
weights or modified after construction.

Owner `test_atlas_engram_parameters.py`: **3 passed,
0 failed, 0 skipped** on native MLX. Tests verify exact
B01 reference identity across both sites, two-page
extent expansion without reindexing, complete ledger
name/shape/dtype enforcement (including unrelated
tensors), invalid site rejection and immutable view
semantics.

This is a **staged candidate**, not B07.4 turn-in.
B07.3's accepted-generation custody and independent
review are prerequisites; B13 checkpoint integration,
actual read-site execution and parent acceptance remain
separate gates. No student run or live optimizer write
was performed.
