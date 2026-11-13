# C04.1/C04.2 provisional repair

Status: IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION.
Issues #498/#499; parent #373; draft PR #550.
Authority: IPR-0220. No live student, AdamW or graph changes.

Consumed unified: 6b5460032fc0b19115843cce95fe8be9582af141.
Starting Lane C HEAD: 7cb35bf7b97b784f7a99839add57b1d195fe4307.
The previous uncommitted draft at a745e18 was preserved in a named Git stash;
this patch repairs the newer A07-based implementation already on Lane C.

## Repairs and scope

Independent fresh-context EGM reproduced three majors: total operation allowance
reset across attempts; rewriting fixed operands through a neural proposal; decoder
construction failures escaping legal fallback. Red regression run recorded two
failures and two errors. The valid SUB proposal test now explicitly grants SUB.

One shared operation allowance covers exact, cached, neural, refinement and fallback
attempts. Actual A07 execute_dag gains optional operation_limit, validated in
0..goal.budget.max_operations, excluding bool. Omission preserves its interface
behavior. Zero allows verified memo hits but no computation. Executor errors with
no cost receipt conservatively reserve all remaining compute. No evaluator is
duplicated in Lane C.

All candidate routes preserve original fixed nodes/operands/topology and fill only
declared holes. This version supports qualified fillings of the original lowered
DAG; it does not claim independently transformed DAG equivalence. Decoder payload
BilqisError/ValueError failures allow bounded refinement or verified fallback.
Unexpected callback failures remain visible.

## Verification and review

Package-local runtime solver, semantic DAG and semantic operator tests:
60 passed, zero failures/skips; exact output in tests.txt. git diff --check passed.
New witnesses cover operation exhaustion across refinements, fixed-operand rewrite
rejection across neural/cache/fallback, malformed decoder construction, zero-budget
memo hits/misses, invalid operation limits and typed malformed-goal errors.

Pinned EGM: b3a35956759bf7f024af2ff061b2e0b44b438e4c.
Fresh Goldfish c04_current_audit independently reproduced the majors, then cleared
all three after repair with 59/59 passing tests. It found one input-error nit;
_prepare now validates goal before optional-limit dereference, with a regression
assertion in the final 60-test run. No remaining blocker/major in targeted review.

Incident PM-2026-10-28-011 was enriched and native-Sheet readback verified before
repair. Earlier C04.1/.2 EGM_PENDING receipts are superseded for these repaired
software boundaries, not for upstream integration acceptance.

Actual accepted A07 source interfaces are used. Actual B06/B10/B11 integration,
decoder decision receipts, real neural routes and disposable MLX witnesses remain
pending. Refinement-call limits do not prove decoder decision accounting. C02
upstream requalification remains pending. Issues stay open; PR stays draft/unmerged.
Next leaf: C04.3 #500 provenance-safe replay and gold separation.
