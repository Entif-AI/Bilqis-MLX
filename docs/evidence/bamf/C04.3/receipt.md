# C04.3 | Provenance-safe solver replay

Issue #500; parent #373; predecessor #499.
Status: IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION.
Authority: IPR-0220. Lane C codex/bamf02-c-runtime; draft PR #550.
Consumed unified 6b5460032fc0b19115843cce95fe8be9582af141,
already contained at implementation baseline 050b4f648b0fce9eda1051d988b4f4cf30dec3ef.

## Owned behavior

CapabilityResult/v3 exports bilqis.c04.solve-replay/v1 through replay_record().
The immutable result binds the original TaskGoal digest, generation/source/release
identities, rights/correction epochs and declared compute allowance. Per-attempt
A07 DAG receipts retain selected node/operator IDs, ordered operand references
(including predecessor-result dependencies), executed nodes and unresolved signatures.
Only measured operations are reported as measured. Unknown cost after an executor
failure reserves the remaining allowance separately. Lookup/memo, backbone and
local-refinement counts retain distinct meanings.

Replay outcomes contain actual answer type/state/digest; raw source values, answer
payload, gold labels and scores are absent. The runtime uses canonical accepted A07
TaskGoal/v1 and explicit typed source-lowered DAG/hole boundaries. It introduces no
second planner or TaskGoal implementation. Source adapters supply released handles;
the golden-label evaluator remains outside the solver dependency graph.

## Proof and EGM

Red: missing replay_record() caused one expected test error. Final package-local
solver/DAG/operator suite: 64 passed, zero failures/skips (tests.txt).
Witnesses cover exact/neural/refinement replay, fixed bindings, measured versus
reserved costs, memo lookup without compute, typed outcome digest, repeatable JSON
export, and transitive source import closure including parent-package initializers.
Whitespace check passed.

Fresh Goldfish c04_3_goldfish read pinned EGM
b3a35956759bf7f024af2ff061b2e0b44b438e4c and live #500, then reviewed the actual
two-file implementation diff. Verdict PASS for the bounded leaf, no blockers or
majors. Two test nits (nonexact/failed/memo receipts and package initializer closure)
were addressed in the final 64-test run. Reviewer inspected the earlier 62-test
receipt; it did not independently rerun tests. The final run is author verification.

## Remaining integration gates

Accepted actual A07 TaskGoal/DAG/operator APIs are consumed. B06 refinement and
B10/B11 typed decoder/backend remain contract-shaped callbacks. Decoder decision
counts are explicitly unmeasured (None), pending actual upstream receipts; callback
counts do not substitute for that evidence. Cross-lane C02 requalification, actual
neural role-binding witness and disposable Studio MLX proof remain pending.
No actual student, AdamW, graph, optimizer or private-source operations occurred.
No issue is closed and PR #550 stays draft/unmerged. Parent acceptance remains open.
Next dependency-ready Lane C child: C05.1 #501 against frozen B12/B13 boundaries.
