# C10 durable domain binding repair

PARTIAL_PENDING_OWNED_COVERAGE_AND_UPSTREAM. IPR-0220; PM-2026-10-29-009 logged/read back before repair. Base b9027026b1d624397ff233b33babc23147abb291; reviewed unified da0431bee37c0e4f766f05cc94ceb6b23ac7d054.

Fresh independent EGM found durable queue storage discarded six wrapper identities, allowing reload/rebind under changed rights despite10 green tests. Akasha event rows now store immutable domain JSON in the same transaction. Duplicate comparison includes complete source-event envelope plus domain binding. Historical bare rows remain bare after nullable-column schema migration; bound/bare reinterpretation rejects. A cold reader reconstructs and validates complete BamfProjectionEvent wrappers. Staging checks queued wrappers against durable bindings. Offline staging without an outbox remains an explicitly provisional fixture surface.

11 owner tests pass, zero failures/skips. Fresh independent pinned EGM re-audit scoped PASS for the binding repair, with nine additional migration/bare-bound/restart/idempotency assertions. Each of six altered fields rejects on enqueue and staging. No actual graph/services, learner/AdamW, MLX or source promotion.

C10 coverage Major remains OPEN: prescribed teacher visits, plasticity epochs, package exports and existing-owner #297/#299/#300 consumption/accepted-generation producer bridge. This is child-owned missing behavior, not only a deferred live-service proof. Keep519/520/521 open and PR550 draft/unmerged; no full C10 acceptance. Next work: implement missing owner bridge/categories against authoritative existing receipt contracts, then independent review and actual upstream/service qualification.
