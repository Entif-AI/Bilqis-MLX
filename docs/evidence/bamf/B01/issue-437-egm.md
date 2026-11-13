# Issue #437: generation extents and topology configuration

Starting Lane B HEAD: `9c8d60fb25333315d305ac938fb0b56f1a0fa99e`. Consumed unified: `44f78431709ec3b8fc23f47b45d9b18f167c7354`. Direct dependency #436 receipt: https://github.com/Entif-AI/Bilqis-MLX/issues/436#issuecomment-6486256872.

GenerationExtents now has exact-field, schema-checked, digest-verified serialization under `bilqis.mlx.generation-extents/v1`. Its digest is unchanged for existing values. The unbound initialization manifest embeds the full extent record alongside its digest, keeping geometry and generation capacities separately inspectable. Independent bank/page growth changes the extent receipt while preserving the topology record and existing arrays/moments.

GenerationProvenance stores source identity, release content digest, teacher identity and teacher epoch under `bilqis.mlx.generation-provenance/v1`. It has its own verified roundtrip and digest. These fields do not enter the topology or extent digest. This record validates identity syntax; source admission and durable generation publication remain with their downstream owners. Unbound construction supplies no invented source or teacher binding.

The self-describing checked-in topology config and existing strict ModelTopologySpecV2 validation are reused. Explicit pre-allocation tests cover contradictory heads, zero head/bank/context sizes, odd RoPE dimensions, unsupported dtype and FFN method. No alternative architecture is introduced.

Red: the new suite failed importing the missing GenerationProvenance API, retained in validation log `2026-10-29T02-32-12-345Z-57569.log`. Green: full disposable MLX and real frozen-v1 witnesses **20/20 passed, zero skips**. Scoped operator-control and hygiene audits have zero findings; docs and diff checks pass. Existing inherited integration failures remain unresolved.

Fresh independent Google EGM pinned at `b3a35956759bf7f024af2ff061b2e0b44b438e4c` returned `EGM_VERIFIED_NO_MATERIAL_FINDINGS`. No blocker or major remains. The optional exact-error-code test suggestion is nonblocking. The final issue/PR receipts identify the pushed commit.

Controls: PM-2026-10-28-004 / RC-138 / PAT-099; PM-2026-10-28-006 / PAT-090; PM-2026-10-28-008 / PAT-086. IPR-0220 governs. No durable student, own AdamW, teacher, champion or original checkpoint changed. Actual source coverage, learning and retention remain unmeasured. Human approval owns integration and actual student starts. Next permitted leaf after this receipt: #438.
