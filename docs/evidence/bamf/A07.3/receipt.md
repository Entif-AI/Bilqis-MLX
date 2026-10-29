# A07.3 | Bounded execution receipts and compositional typed DAG nodes

- Issue: #415; parent A07 #353; Lane A
- Consumed unified trunk:
  `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
  through merge `982ba51127b7e851cd795039644565bc3625ebaa`
  (already an ancestor; no manufactured no-op merge)
- Direct prerequisite: A07.2 #414, independent EGM PASS
  at `819a653` with final receipt `9232a42`
- Implementation head: pending commit/push
- Independent EGM: **PENDING**

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
  **40 passed, 0 failed, 0 skipped**.
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
