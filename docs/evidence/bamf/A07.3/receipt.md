# A07.3 | Bounded execution receipts and compositional typed DAG nodes

- Issue: #415; parent A07 #353; Lane A
- Consumed unified trunk:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
  through merge `982ba51127b7e851cd795039644565bc3625ebaa`
  (already an ancestor; no manufactured no-op merge)
- Direct prerequisite: A07.2 #414, independent EGM PASS
  at `819a653` with final receipt `9232a42`
- Current pushed implementation head:
  `6b7f4daaf89293f5a12a1381e016d01e877128f4`
- Independent EGM: **PASS**, zero Blockers/Majors at
  immutable `6b7f4da`; independent 48/48 test execution
  recorded on issue #415 (comment `6489015092`).

## Source-qualified API

`bilqis_mlx/semantics/cognitive_dag.py` provides immutable
`TaskGoal`, `DAGProgram`, `DAGNode`, `DAGOperand`,
`DAGBudget`, `DAGReceipt`, `DAGResult`, and
`execute_dag(goal, binding, memo=None) -> DAGResult`.
`bilqis_mlx/semantics/memo.py` adds a process-local
`PureOperationMemo`. The public A07.1/A07.2
`execute_pure` contract remains source-qualified.
Its internal pure computation is factored behind a
validated entrypoint, without the draft's caller-asserted
derived-value bypass.

Exact wire schemas:

- `bilqis.task-goal/v1`
- `bilqis.cognitive-dag-operand/v1`
- `bilqis.cognitive-dag-node/v1`
- `bilqis.cognitive-dag-program/v1`
- `bilqis.cognitive-dag-budget/v1`
- `bilqis.cognitive-dag-receipt/v1`
- `bilqis.cognitive-dag-result/v1`
- Existing A07.1 typed value/operator/binding schemas are unchanged.

The task goal pins the semantic release, scope, output type,
source-visible reference identities, allowed operator IDs,
and a bounded budget. Input refs carry the exact approved
frame occurrence ID, role and occurrence index; literals
carry admitted source handles; result refs point only to
typed predecessor nodes. All refs, grants, signatures,
task limits, cycles, orphan nodes and depth are checked
before computation. Nodes execute topologically using only
executor-owned predecessor results. The program cannot
inject assessment labels or a caller-declared derived proof.

Holes declare candidate operators, per-slot candidate
source-visible operands and typed applicability constraints.
A unique legal operator/operand combination binds
deterministically; unresolved ambiguity returns a typed
`UNRESOLVED` answer and unsatisfied signature rather than
guessing. The future B10 single-backbone typed decoder
remains a separate integration owner; this leaf does not
invent or invoke a neural decoder.

Receipts count pure compute attempts, cache lookups and
memo hits; failed applicability consumes one compute unit.
Cache hits consume a lookup and zero compute units. Keys
include the exact operator version/source/implementation
identity, ordered immediate source or predecessor
dependencies, and consulted rights/policy authority,
not unrelated source grants. Only known VALUE and
source-attested NONE outcomes are cached. Receipts retain
selected operator/operand bindings, executed nodes,
source-binding digest and unresolved signature, without
verbose internal prose.

## Verification

- Focused A07.3 plus A07.1/A07.2 owner suite:
  **48 passed, 0 failed, 0 skipped**.
- Literal `ADD(MUL(2,3),4)` produces `10` in
  two operations; exact replay uses two memo hits
  and zero compute operations.
- One-legal-candidate operator and partial-operand holes
  resolve deterministically; ambiguous holes return
  `UNRESOLVED` without a neural call.
- Forged literals, disallowed operators, cross-task
  scopes, output mismatches, frame-occurrence substitutions,
  cycles, orphan nodes, forged predecessor result types,
  invalid receipts and revoked late-node grants reject.
- Node/depth/decision/operation budgets and failed
  applicability are tested. Unrelated grant additions
  preserve a memo hit; changed consulted inputs miss.
- Explicit NONE remains distinct from zero and may be
  cached; unknown/alternative frame bindings remain
  unresolved rather than silently supplying a value.
- A transitive import-closure test excludes assessment,
  gold-label, Factory and oracle dependencies; a socket
  trap covers the two-node pure execution.

A07 parent integration, B10 neural selection, C05
end-to-end scoring, and live optimizer/trainer execution
remain separate owner gates. No unified/main merge,
source promotion or live training is claimed.

## Independent EGM findings and bounded repairs

The first immutable Goldfish review at `ab32669`
independently executed 40/40 tests and identified four
code Majors plus a stale implementation-head receipt.
The `e0ba655` repair filters hole operators and
candidate operands using independently source-visible
applicability, including zero-divisor and partial-hole
preconditions, and bounds candidate fanout. The
`88621bc` repair fail-closes *all* ungranted hole
candidates before computation; includes internally
consulted UnitConversion edges and frame/member rights
in memo dependencies; and counts an actual memo lookup
even when a compute-budget miss prevents execution.

Negative tests now cover unauthorized alternative
ambiguity, revoked/missing internal knowledge,
frame-content drift, two-hole applicability, candidate
fanout and a counting memo on budget exhaustion.
The current source and tests were pushed. At this
intermediate checkpoint full independent immutable-head
EGM re-review remained **PENDING**; final PASS is below.
The pinned EGM checkout is available at
`../bamf02-egm-b3a359` with verified SHA
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

The second independent Goldfish review at `e0ba655`
found two additional behavioral Majors not resolved
by that target: a multi-slot hole with exactly one
jointly applicable operand combination was left
unresolved, and a caller-poisoned memo could supply a
type-valid but false cached answer. The intervening
`88621bc` commit already fixed the reviewer's
internal source-dependency Major. Repair `6b7f4da`
performs bounded local combination checks (maximum
4096 per DAG, no speculative tree execution) and
accepts memo hits only with a process-local
executor-computed value witness. Negative tests prove
unique DIV(4,2) among four typed combinations and
recompute ADD(2,3)=5 after a caller inserts a forged
cache value 7. Focused suite **48/48 passed**.
At this repair checkpoint final independent immutable-head
EGM was still pending; the final disposition is below.

## Final review and integration receipt

Independent Goldfish reviewed immutable
`6b7f4daaf89293f5a12a1381e016d01e877128f4`
and executed **48/48** owner tests, with zero remaining
Blockers/Majors. Review: issue #415 comment `6489015092`.

The reviewed receipt head
`fadbe684140220776f906627a1c4ec28b41ba216`
is the exact second parent of human-approved unified
merge `6b5460032fc0b19115843cce95fe8be9582af141`
through PR #551. Integration receipt: issue #415
comment `6489034037`. This closes the A07.3 leaf
review/integration gate, not the separate A07 parent
acceptance or live neural training.
