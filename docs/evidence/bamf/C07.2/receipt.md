# C07.2 native debt inspection groundwork

Status: **PARTIAL_PENDING_PLANNER_AND_UPSTREAM**. This is a bounded diagnostic slice of #511, not completed C07.2. IPR-0220. Base `813c5afd8961ca41f7595f8cd93d246f5cfc0c0d`; consumed unified `da0431bee37c0e4f766f05cc94ceb6b23ac7d054`. PR #550 remains draft/unmerged.

`read_native_atlas_debt` consumes an owner-supplied current manifest plus independently loaded expected canonical digest. It reuses cold native Factory admission and SchoolState verification. Actual execution-plan membership supplies grades; carried mastery debt, mature capability debt and mature grade debt remain distinct. Current profile digest/provider parameters preserve current numeric/source scope without inventing a historical scope. Missing debt fields reject instead of defaulting to no debt; debt-changing legacy migration requires explicit existing-owner handling. The returned immutable view grants no learning/admission permission and writes no files.

Native legacy debt does not record per-item historical scope/policy evidence. This remains explicit NOT_MEASURED. The current policy is never assigned retroactively. Hash equality is not B13 custody authentication. This API does not discover or load a live learner.

Proof: 24 affected tests passed, zero failures/errors/skips. Expected red was missing new module. Fresh Goldfish used EGM pin `b3a35956759bf7f024af2ff061b2e0b44b438e4c`, verified both source hashes, independently ran four new tests, and found no scoped blocker/major. A documentation nit was corrected: canonical content digest, not original-file byte identity. No full #511 review PASS is claimed.

Remaining: lease renewal/out-of-scope continuation integration; source-attested constructive successor selection; historical scope/policy receipts; accepted predecessor/adoption receipt integration; event-driven planner integration. Reuse native proposal/staging/evidence owners. #510 PR #567 is informational until accepted through unified. No sibling code imported, no actual student/AdamW, MLX, graph, generation publication or training.
