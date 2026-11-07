# A13 / A05 compiled-prefix authority checkpoint — 2026-11-07

## Scope

This checkpoint repairs one ownership inversion in the B06 source-positive path.
B06 previously defined the stable handle and evidence digest for the complete
compiled p-local prefix inventory even though its own contract required the A05
source owner to grant that inventory. A13 could grant atoms/frames/members, but
no production source boundary issued the complete compiled-prefix credential.

This patch moves identity/evidence ownership to A05 and makes A13 issue the grant
only after exact source-owned replay. B06 remains a verifier/consumer.

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
