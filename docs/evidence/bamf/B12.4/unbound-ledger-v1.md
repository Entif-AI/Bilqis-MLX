# B12.4 unbound constructor and normative ledger

Issue #477 remains open for complete-model/candidate integration. This slice
consumes actual B01 initialization and tensor metadata; it introduces no
replacement initializer or independent tensor inventory.

Predecessor `1416d65231e5f40d9db4d741dfe39487d2a6d543` consumes reviewed
unified `da0431bee37c0e4f766f05cc94ceb6b23ac7d054`, unchanged at the leaf fetch.
The private `_create_unbound_bamf_optimizer` calls
`model_topology_v2.create_unbound_bamf_state` and borrows its parameter and
native moment arrays and original UNBOUND manifest. Names, shapes, initializer
classes and decay flags come from `expected_bamf_shapes`.

Identity, motif and feature tables have uint64 leading-row zero counts.
Two-dimensional embedding tables also use leading-row counts, while vector
seeds and dense parameters use scalar zero counts. Every moment remains FP32
zero. This is fresh disposable initialization, not migration of a historical
optimizer or source admission. B01's original manifest and topology/extents
digests remain intact; count-state schema remains provisional-v1.

Red: one missing-API failure with twelve existing tests passing. Green:
**13/13 native MLX tests**, zero skips, including real initialization and
validation of the full disposable B01 tensor tree. The witness checks exact
keys/shapes, all zero moments/counts, uint64 types, representative table/scalar
geometry, literal initializer values, decay flags and original UNBOUND status.
Available disk at test preparation was238GiB; no model binary was written.

Fresh pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`: scoped PASS,
no Blocker/Major; independently reproduced13/13. Explicit operator audit and
diff check pass. No production caller exists beyond the focused test.

Actual source-admitted row values, B11 model execution, B09 participation,
B12 retained transactions and B13/C serialized counts remain pending. This
constructor supplies none of those authorities and does not close #477.
IPR-0220 remains open; PM-2026-10-29-001/002/003/004/006 controls remain.
No durable student/own AdamW/teacher/champions/originals changed; actual
learning and retention remain unmeasured. Human owns integration and durable
training initiation.
