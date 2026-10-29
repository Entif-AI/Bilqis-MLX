# Lane B producer-safety integration candidate | 2026-10-29

Lane B source head: `ae08c4aa6c9eee86cbc28142de626f382662876d`.
Isolated integration head: `b64717a` before this receipt.
Canonical B11.1a producer issue: #586 (#587 closed as duplicate).
No shared B/unified/main merge occurred.

## Inputs

- #577 B05.4 draft PR #584, source head `3c0f45e`:
  public depth selection fails closed with
  `BLOCKED_PRODUCER_DEPENDENCY`. The private numerical start/append
  fixtures cannot authorize a source-owned group. The g2-as-g1 and
  cross-parameter-tree adversaries are rejected at public admission.
  Independent worker-20 reviewed the safety mitigation as PASS,
  but **full B05.4 acceptance remains BLOCKED**.
- Canonical #586 B11.1a numerical draft PR #588, source head
  `49095a0`: fixed B01/B04 four-layer numerical forward, exact
  parameter geometry, native attention/FFN, causal prefix isolation,
  nonzero gradients and explicit `UNADMITTED_NUMERICAL` result.
  Independent worker-20 returned numerical-only EGM PASS.

The two branches were merged into a new isolated integration branch.
The source-owner B lane was not mutated.

## Integration proof

The combined B05/B11/B04/B01 suite initially passed 50 tests,
0 failures, 2 existing optional skips on Apple MLX. A new cross-module test
executes a real four-layer B11 group and then attempts to pass its
`UnadmittedGroupNumerical` output to the public B05 selector.
The selector rejects with `BLOCKED_PRODUCER_DEPENDENCY`, proving
that actual numerical execution alone is not a producer credential.

`git diff --check` passes. No new B05/B11 error-control-plane or
module-size finding remains after the owner branches' static guard
repairs. Subsequent B11.1a independent review found an inherited
internal sequence-reset Major. The fixed numerical wrapper now
passes `AttentionScope.sequence_starts` to every B04 layer; its
failing-before regression proves post-reset output isolation even
when the scope ID stays constant. After this owner repair, the
combined suite passes **51 tests, 0 failures, 2 existing optional
skips**. It remains unadmitted producer evidence.

## Remaining source authority

This is a **safety integration**, not completed #577 or #586.
The B11 producer must bind B03/A05.4-approved source h0, the
actual B01 parameter-tree content digest and execution prefix,
B04 cache scope chain, B08 group-1 motif-read disposition (explicit
no-hit while source authority is quarantined), and the executed
group chain before B05 may admit summaries. B13 final-generation
publication is a separate downstream gate, not a prerequisite.
Worker18's separate draft PR #590 explores observed
execution-chain fingerprints but is not included in this proof
until its own independent review and reconciliation.

No neural training, source promotion, issue closure or merge occurred.
