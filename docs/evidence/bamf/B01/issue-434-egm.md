# Issue #434: architecture identity and legacy isolation

- Lane: `codex/bamf02-b-neural`; consumed unified commit: `44f78431709ec3b8fc23f47b45d9b18f167c7354`.
- Implementation parent before the final factory repair: `f4da35cf5d0ee5dfec118c640a37b9031007a1da`.
- Direct prerequisite: #320 topology contract and its `f09e44d35b5f544ef8d3e61ec127e326d0b09eb1` receipt.
- Schemas: `bilqis.mlx.model-topology/v1`, `bilqis.mlx.model-topology/v2`, `bilqis.mlx.bamf-shape-policy/v1`, and the unbound initialization schemas. Architecture selector: `bamf-atlas-v2`.
- Governing protected curriculum authority remains IPR-0220. This evidence does not admit semantic rows or authorize training.

## Independent review

A fresh-context Google Elephant-Goldfish Model reviewer used the pinned checkout `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Initial findings identified an unintegrated factory and missing real-checkpoint evidence. The factory now executes the actual v1 and unbound v2 constructors. The reviewer inspected the pinned local witness and a targeted re-audit of the strengthened adversary; **no #434-owned blocker or major remains**.

The v2 factory constructs an unbound parameter and zero-moment tree. It does not implement the later atlas forward backend, source admission, masked AdamW or durable generation loader. The existing operator path continues to reject v2 until those owners integrate it.

## Proof

With `BILQIS_BAMF_FULL_WITNESS=1` and `BILQIS_V1_BUNDLE_WITNESS` set to the locally preserved frozen v1 bundle, `python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/test_model_topology_v2.py` passed **14 tests, 0 failures, 0 skips** on the MLX host. The full disposable tree was serialized, reloaded, expanded and compared. A real six-layer v1 bundle was rejected by v2 selection before v2 construction, while its v1 reader remained usable. A disposable clone with both spoofed metadata and an actually reshaped QKV tensor was also rejected. Original manifest, model/own-AdamW payload and catalog hashes remained byte-identical.

The opaque v1 manifest identity is SHA-256 `8ca7d08aceeded4db57e7b923e9da9d89c7ddd5fce823297114b065e63d17833`. The protected local receipt and validation log retain the fixture locator, exact command, payload hashes and reviewed diff identity under `.local/bamf-lane-b/`.

The existing topology/lifecycle package tests passed **14/14**. The historical ABI check passed local checks with the independent expected fingerprint absent, so it remains advisory. `PM-2026-10-28-004` / `RC-138` / `PAT-099` records the corrected serializer near miss. `PM-2026-10-28-006` / `PAT-090` records three inherited unified-base size-gate regressions; no Lane B change caused or suppressed them.

No durable student, teacher, checkpoint, or optimizer was modified. Source coverage, actual learning and retention remain unmeasured. The human alone starts a durable student.
