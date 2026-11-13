# B07.4 | Motif-only B01 tensor registry view

- Issue: #459; parent B07 #356; Lane B.
- Isolated candidate branch:
  `codex/bamf02-b07-pages-candidate-20261029`.
- Reviewed unified consumed: `6b5460032fc0b19115843cce95fe8be9582af141`.
- B01 normative authority:
  `bilqis_mlx/runtime/model_topology_v2.py`.
- Candidate output schema:
  `bilqis.mlx.motif-parameter-view/v1`.
- Independent EGM: **PASS**, scoped to B07.4 at immutable
  `2274cdda4a32bdb4f139576a86e04bb0cc7ddd87`.
- Direct prerequisite B07.3: **NOT YET ACCEPTED**.

`motif_parameter_view` first validates the **entire** B01
`ModelTopologySpecV2` / `GenerationExtents` parameter tree
against `expected_bamf_shapes` and
`validate_bamf_parameters`. It then returns a sealed,
read-only mapping of differentiable copy-on-read handles to all declared motif
pages and exactly one site's five local tensors:
projection, norm, hidden gate, feature gate and bias.
Both sites share the same B01-owned page parameter, but their site parameters
are distinct. Returned arrays are copy-on-write values, not mutable
aliases into that shared state. No new parameter, optimizer, checkpoint,
identity, depth, feature or neural-write authority is
created. The view cannot be constructed with anonymous
weights or modified after construction.

Owner `test_atlas_engram_parameters.py`: **4 passed,
0 failed, 0 skipped** on native MLX. Tests verify exact
B01 parameter source identity across both sites, two-page
extent expansion without reindexing, complete ledger
name/shape/dtype enforcement (including unrelated
tensors), invalid site rejection, copy-on-read mutation
isolation and preserved gradients back to B01 parameters.

## Independent review repair

Fresh Goldfish at immutable `3af6977` found **one Major**:
the original view returned mutable `mx.array` objects
directly. Writing through `site0["page.0"]` or
`site0["bias"]` mutated B01-owned parameters and the
shared page observed at site1, despite the mapping
itself being sealed. This was reproduced.

The repair returns `mx.array(original)` on each public
read. Native MLX confirms this is a differentiable
copy-on-write handle: mutation changes only the returned
value, while gradients still reach the original B01
parameter. The source tensors are retained behind
private name-mangled custody rather than exposed
through the public mapping. The focused suite now
passes **4/4** with a literal write-through and
gradient regression.

Independent Goldfish re-reviewed immutable `2274cdd`
against pinned EGM `b3a3595` and returned **PASS,
zero remaining Blockers/Majors**. It independently
executed 4/4 owner tests and B01 18 pass/2 optional
skips, reproduced the former write-through adversary
with unchanged B01 and other-site tensors, and proved
autodiff still accumulates onto the original shared
page (gradient 8.0) and local site bias (gradient 6.0).
This scoped PASS does not waive B07.3 accepted-generation
custody or human-reviewed Lane B integration.

This is a **staged candidate**, not B07.4 turn-in.
B07.3's accepted-generation custody and independent
review are prerequisites; B13 checkpoint integration,
actual read-site execution and parent acceptance remain
separate gates. No student run or live optimizer write
was performed.
