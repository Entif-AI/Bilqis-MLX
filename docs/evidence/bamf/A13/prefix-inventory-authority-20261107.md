# A13 / A05 compiled-prefix authority checkpoint — 2026-11-07

## Scope

This checkpoint repairs one ownership inversion in the B06 source-positive path.
B06 previously defined the stable handle and evidence digest for the complete
compiled p-local prefix inventory even though its own contract required the A05
source owner to grant that inventory. A13 could grant atoms/frames/members, but
no production source boundary issued the complete compiled-prefix credential.

This patch moves identity/evidence ownership to A05 and makes A13 issue the grant
only after exact source-owned replay. B06 remains a verifier/consumer.

Canonical latest legacy-trainer adaptation source:
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`.
Prometheus remains historical evidence only and is not the current adaptation source.

## Exact identity

- reviewed unified base: `bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`
- branch: `codex/354-a13-prefix-inventory-20261107`
- semantic head: `06ef583f0722075bbb3bd1dbb8df6d931a1011b7`

## Change

A05 now owns `prefix_inventory_handle(...)` and
`prefix_inventory_evidence_digest(...)` in the frame compiler surface. A13's
public-formal source admission adds `authorize_public_formal_prefix(...)`, which:

1. requires the exact source AST, compiled prefix and current compiler config,
2. replays the A05 compile and requires exact equality,
3. checks current source/purpose/jurisdiction/scope/rights/correction policy,
4. issues the existing `SourceGrant` shape for the exact compiled inventory,
5. rejects conflicting prior grants rather than replacing them.

B06 imports the A05 identities and verifies the A13 grant. It no longer owns the
credential definition. No consumer-local grant, caller credential or duplicate
B06.2 policy was added.

## Proof

Exact-head snapshot-pinned `m3-ultra` proof at `06ef583f...` with the accepted
A01 artifact:

- 14/14 PASS in 6.521s
- real pinned public-formal source emits the exact prefix grant
- B06 public refinement consumes that source-issued grant
- repeated issuance is idempotent
- mismatched task boundary rejects
- revoked inventory, forged salience, future context and 8->9 quota invariance
  remain green

Repository checks:

- `quality:changed`: PASS; zero new changed-file findings
- legacy trainer 6/6
- flow-control 15/15
- BAMF contract verifier 43/43 mirrors and 214 identities/fingerprints
- `git diff --check`: clean

The existing B06 selector remains a historical long-function baseline finding;
this change introduces zero new changed-file smell findings.

## Remaining authority boundary

This is not full A13 parent closeout and spends no fresh EGM/PR. Downstream B11
must consume this source grant only after reviewed integration. Together with the
separate C05 AST-custody and B10 request-disposition branches, the remaining
independent B06 production authority gap is durable operator `run_seed` plus true
visit identity.

## Reviewed-unified refresh — 2026-11-09

The preserved branch consumed current reviewed unified
`4bfcbd5a9aaa22a1bc2bca4c7a64ec203df07044` exactly once at merge checkpoint
`55e94b29`. The only merge conflict was the shared Lane A flow ledger; current
reviewed-unified entries were preserved and this scoped #354 integration was
reactivated without changing A05/A13 ownership.

Current source-positive qualification used the accepted A01 artifact at
`/Users/emilie/Code/371-c02-complete-20261106/.local/c02-a01-rebuild/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`:

- source admission + prefix policy + salience ring: **14 passed + 6 subtests**,
  zero skips;
- BAMF contract verifier: **43/43** exact issue mirrors, **216** indexed identities;
- `quality:changed`: PASS, zero new changed-file findings;
- current Microspenics legacy-trainer authority and its 7 tests: PASS;
- BAMF flow-control and its 15 tests: PASS;
- `git diff --check`: clean.

The existing `select_prediction_refinements` long-function baseline remains
historical and this change adds zero new smell debt. No B06 policy duplication,
consumer-local grant, learner, optimizer, source publication, or A13 parent
closeout was introduced. Fresh merge-readiness review remains the next gate.

## Fresh review repair — 2026-11-09

Fresh review of exact head `fba3ecb2b9abdc3c3eacc45b5e890ceef7f60d4b`
returned **FAIL — 0 Blockers / 1 Major / 0 Nits**. Current-unified's later B06
module split had reintroduced a second `PREFIX_INVENTORY_SCHEMA`,
`prefix_inventory_handle(...)`, and `prefix_inventory_evidence_digest(...)` in
`runtime/refinement_contracts`, with `refinement_ranking` consuming that copy.
That violated the existing owner contract even though the active selector already
used A05 identities.

The bounded repair removes the duplicate definitions and imports the A05
`frame_compiler` identities into the split B06 contract module. A regression now
asserts object identity across the public refinement API, split contract module,
ranking module, and A05 owner.

Post-repair proof:

- accepted-A01 source/refinement ring: **15 passed + 6 subtests**, zero skips;
- exact import identity: contract/ranking handle and digest objects are all the
  A05 `frame_compiler` objects;
- BAMF contract verifier: **43/43** mirrors and **216** indexed identities;
- changed-file smell audit: zero new findings; the historical long-function
  baseline remains unchanged.

This is `SHARED_CONTRACT / MECHANICAL_PROOF` repair under ADR-127, not a new
authority or B11 composition. Fresh reinspection of the repaired exact head is
required before turn-in.
