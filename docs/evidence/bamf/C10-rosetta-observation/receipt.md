# Native Rosetta Observation consumption

PARTIAL_PENDING_DOMAIN_AUTHORIZATION_AND_PUBLISHER_WIRING. IPR-0220/PM009; base250a7c9bb2b6b76e23bf990ad2c8980d2c099394; unified da0431bee37c0e4f766f05cc94ceb6b23ac7d054.

C-owned TS bridge imports actual Rosetta buildTile/verifyTileIntegrity. Python does not implement CID/canonicalization. A configured local runtime pins bridge bytes and owner revision; exact native response bindings are checked. Observation payload has only native observationId/source/signal fields. C-owned pack bilqis.bamf.c10 and envelope version0.1.0 are explicit, independent from workspace package version0.0.1. Parents stay empty absent verified parent CIDs. Explicit millisecond-UTC projection createdAt is checked separately because native integrity excludes it from CID identity. Source integer times remain unchanged, and unsafe JavaScript integers reject before invocation.

Signal holds compact digest references, source XID when available and fixture mode. No source payload, artifact bytes, private subject or fabricated measurements are projected. Native CID, C-owned observation reference, original external source ID and SHA256 receipt identity remain distinct. Returned Tile JSON is immutable; decoded copies cannot mutate retained results. All output remains INTERNAL_ONLY; this adapter grants no source/rights/evaluator authority or public-export permission.

Real owner test mode uses BILQIS_ROSETTA_CONTRACT_ROOT pointing to an authorized checkout, clean core/canon/cid packages at ce41904be268a9bfd6b7095e79a5cb83b6c5e8b3. esbuild bundles the tracked TS bridge with --conditions=@entif-ai/source and the actual core source alias into a temporary artifact; node executes it. No Rosetta checkout edits. Without explicit owner workspace, native tests skip rather than substitute a fake CID implementation.

22 affected tests passed, including3 actual-owner tests. Fresh pinned EGM independently22/22 scoped PASS plus fixture-mode/XID/private-byte/mutation-isolation probes. Native integrity independently rejects a tampered Tile; adapter rejects wrong returned binding, timestamp, bridge hash and unsafe integer. Expected red was missing adapter module. No external services, actual MLX or learner/AdamW actions.

This proves native Observation contract consumption only. No fabricated Run/Action/ToolCall/Evaluation is produced. #297 domain authorization, #299/#300 complete publisher wiring, actual upstream bank/package producers, public fixture schema and full C10 acceptance remain open. PR550 draft/unmerged; issues stay open.
