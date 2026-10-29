# Issue #438: historical state isolation at the v2 boundary

Starting Lane B HEAD: `0bc58c840d9fac703f41e5987b05a4e79a0f3de4`. Consumed unified: `44f78431709ec3b8fc23f47b45d9b18f167c7354`. Direct #437 receipt: https://github.com/Entif-AI/Bilqis-MLX/issues/437#issuecomment-6486356082.

The required boundary already exists in the #434 implementation. This leaf reuses it without another transfer path or numeric migration API. `dispatch_model_factory` deserializes the selected topology before calling an allocator, rejects a v1 topology under the v2 selector, and rejects every checkpoint manifest/path at the v2 selector with typed `SCHOOL.MODEL_TOPOLOGY.MISMATCH`. A renamed architecture, compatible shape declaration or optimizer metadata cannot enter the fresh v2 constructor. The historical selector retains the original read-only bundle loader.

The F14 proof uses a real frozen historical six-layer absolute-position bundle. It attempts the v2 selector with the original bundle and with a disposable clone containing spoofed v2 metadata plus an actually reshaped tensor. Both fail before the v2 constructor is called. The legacy selector still reads the original six layers, absolute-position tensor and matching optimizer step. Original file hashes remain byte-identical. The protected local witness locator is excluded from this public evidence note.

BAMF-REQ-007 is traced by the explicit architecture/topology records, central tensor ledger and frozen geometry. BAMF-REQ-023/F14 is traced by the historical checkpoint negative proof. Existing `bamf_deserialize_arrays` requires the entire exact v2 named tensor set and shapes; it is not exposed as a historical checkpoint promotion path. Durable v2 generation loading remains with its custody owner.

The topology factory accepts no behavioral teaching artifact. Such artifacts remain with the independently approved teacher/source interface; this leaf grants no numeric student-state import. The separate generation provenance record supplies identity storage only. No teacher API or source-admission policy is invented here.

Validation consumes the unchanged #437 full witness result: **20/20 passed, zero skips**, including the actual F14 bundle/clone/readback checks. There is no implementation change requiring another red/green cycle or repeated neural run. Fresh independent Google EGM pinned at `b3a35956759bf7f024af2ff061b2e0b44b438e4c` returned `EGM_VERIFIED_NO_MATERIAL_FINDINGS` for this owned reuse boundary. No blocker or major remains.

Controls: PM-2026-10-28-004 / RC-138 / PAT-099; PM-2026-10-28-006 / PAT-090; PM-2026-10-28-008 / PAT-086. IPR-0220 governs. No durable student, own AdamW, teacher, champion or original checkpoint changed. Actual source coverage, learning and retention remain unmeasured. Human approval owns integration and actual student starts. Original B01 parent acceptance remains with its integrator.
