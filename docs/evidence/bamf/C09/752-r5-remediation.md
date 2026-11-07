# C09 #752 Round-5 remediation authority packet

## Status and review boundary

This document is the self-contained engineering handoff for remediation after
EGM episode `C09-752-EGM-20261107`, round `5/5`.

- Repository: `Entif-AI/Bilqis-MLX`
- Issue: `#752` — EGM mitigation: connect dependency indexing and correction
  holds to artifact owners
- Named source: `#516` — BAMF-0.2 C09.1
- Round-5 reviewed head: `b81fd8799b502e0e88706e63e6c40058acfdcc6a`
- Round-5 branch: `codex/752-final-prime-20261106`
- Remediation branch: `codex/752-r5-remediation-20261107`
- Required integration trunk: `codex/bamf-unified-base-20261028`
- Unified SHA fetched for the remediation integration boundary:
  `3899649586b105b075e92f0ee3c51e80c379b473`
- Repaired checkpoint: pending final commit/freeze

Round 5 was a FAIL. This packet does not revise that verdict, claim a sixth
review round, claim EGM PASS, authorize a PR, or authorize merge/issue closure.
`docs/tasks/bamf-0.2/EGM_EXECUTION.md` caps an episode at five complete rounds.
Another exact-head EGM requires explicit human/design authority for a new
review path. Until then issue #752 remains OPEN and `EGM-Failed`.

## Governing acceptance

Issue #752 requires the production owners for atlas features, packed frames,
motifs, exact cache entries, operator compositions, and capability support to
declare their real direct dependencies and route reuse through correction and
eligibility custody. Directly affected reusable artifacts must be held before
use. Lazy revalidation must respect topology and then exigency-before-impact,
propagating only when materialized content or eligibility changes. A replay of
a superseded belief after a claimed remediation must become an actionable
process fault and hold affected descendants, while genuinely independent later
evidence must remain distinct.

No neural/student/optimizer/teacher/champion/checkpoint mutation is authorized
by #752.

## Round-5 finding closure

### Blocker 1 — motif cold-restart before-use ordering

**Finding:** persisted accepted corrections could replay after the motif
owner's only `require()` check, allowing one stale retained-motif use.

**Remediation:** retained execution-cache custody replays accepted correction
state before motif authorization, and `atlas_motif_owner.require()` checks both
its source frame artifacts and retained motif artifact through the accepted-run
hold gate before returning reusable state.

Primary surfaces:

- `bilqis_mlx/runtime/_custody/bamf_bundle/execution_cache.py`
- `bilqis_mlx/runtime/_correction/owners/atlas_motif_owner.py`
- `bilqis_mlx/runtime/_correction/accepted_correction_runtime.py`

### Blocker 2 — last-write-wins correction ingress

**Finding:** a second relevant correction could replace an unresolved owner
queue instead of preserving concurrent alternatives.

**Remediation:** accepted dispatch retains authenticated `CorrectionBranches`
per dependency and stages concurrent corrections until the active branch has
been revalidated or explicitly superseded. An unrelated correction cannot
clear another active hold.

Primary surfaces:

- `bilqis_mlx/runtime/_correction/accepted_correction_runtime.py`
- `bilqis_mlx/runtime/_correction/owners/operator_composition_owner.py`
- `bilqis_mlx/runtime/_model/cache/atlas_cache_runtime.py`

### Blocker 3 — future dependents could escape an earlier correction

**Finding:** accepted dispatch could mark an event seen when an owner had no
current direct dependent, allowing a later learned artifact to depend on the
corrected source without inheriting the hold.

**Remediation:** unresolved accepted corrections remain staged when no direct
dependent exists. Owner mutation calls `refresh_owner_corrections()`, which
activates any newly applicable correction and retries deferred signed
revalidation evidence. Newly learned affected compositions therefore join the
existing correction window before reuse.

Primary surfaces:

- `bilqis_mlx/runtime/_correction/accepted_correction_runtime.py`
- `bilqis_mlx/runtime/_correction/owners/operator_composition_owner.py`

### Blocker 4 — accepted correction history could disappear

**Finding:** the run-local `events.jsonl` could disappear or be truncated while
the data-plane event index remained rebuildable rather than authoritative.

**Remediation:** every accepted C09 append now advances a content-addressed
history commitment stored through a stable canonical data-plane object
reference. The commitment binds the accepted manifest, resolved run identity,
ordered event IDs, and canonical record-set digest. A missing ledger after
history exists, a truncated/replaced subset, or a drifted immutable object now
fails closed before owner reuse. Prior immutable commitment objects remain
addressable when the stable reference advances.

Primary surfaces:

- `bilqis_mlx/_data_plane/store.py`
- `bilqis_mlx/runtime/_correction/accepted_correction_ledger.py`

### Blocker 5 — live Factory construction could omit correction custody

**Finding:** the source-prefetch worker intentionally has no `run_dir` or
correction registry, so allowing that worker context to become the live Factory
execution authority made compiled-batch/solver registration inert.

**Remediation:** worker isolation remains intact. Privileged accepted-run
custody is required at the host boundary instead: the live Factory retention
owner calls `SourceExecutionContext.require_accepted_runtime(run_dir)` and
therefore refuses an authority-free or wrong-run context. Offline compilation
remains legal; live retention/progression cannot silently inherit the worker's
reduced authority.

Primary surfaces:

- `bilqis_mlx/runtime/_source/source_execution.py`
- `bilqis_mlx/runtime/_capability/factory_retention_owner.py`

### Production ingress closure — host evidence and exact-cache consumption

**Review concern:** the accepted correction/revalidation functions and accepted
exact-cache wrapper existed, but source inspection still found no non-test
production caller that owned both accepted-run identity and the trusted
`SourceAuthorityRegistry`.

**Remediation:** `AcceptedRuntimeHost` is the narrow host boundary for one
accepted run. It binds the accepted correction authority once, routes externally
signed correction/revalidation/remediation/derived-claim evidence into the
existing accepted ledger/runtime, mints admitted `SourceExecutionContext`
instances without granting worker processes correction authority, and consumes
exact-cache state only through `interactive_accepted_cache_inference`. It does
not infer public keys, mint source signatures, or replace the six owner-specific
dependency/hold gates.

The real exact-cache integration witness now uses this host for both accepted
cache consumption and correction delivery. The retained-motif witness uses the
same host for signed correction and signed revalidation delivery. Thus the
production ingress is connected to actual owner consumers rather than only to
fixture-local helper calls.

Primary surface:

- `bilqis_mlx/runtime/_correction/accepted_corrections.py`

### Major 1 — multi-result revalidation could be partially consumed then seen

**Finding:** one persisted revalidation frontier could contain several owner
results, but only the current next task advanced before the record was treated
as consumed.

**Remediation:** accepted runtime records per-event consumed
`(correction_event_id, artifact_id)` pairs across retries. Deferred frontiers
remain live until every currently relevant signed result has been consumed.
Newly arriving revalidation evidence also retries earlier deferred frontiers,
so `F1={A,C}` followed by `F2={B}` converges rather than permanently stranding
`C`.

Primary surface:

- `bilqis_mlx/runtime/_correction/accepted_correction_runtime.py`

### Major 2 — stale-replay process fault existed only as a fixture path

**Finding:** `escalate_stale_replay()` had no reviewed accepted-run production
ingress for remediation receipts and later derived claims.

**Remediation:** accepted-run APIs now persist remediation receipts and later
derived claims into the same committed C09 ledger. The runtime reconstructs an
aggregate dependency graph only from actual registered production owner nodes,
calls the existing stale-replay classifier, persists the resulting
`PROCESS_FAULT` record, and installs before-use holds on every registered owner
that actually owns an affected artifact. Capability support is also forced to
`REQUALIFICATION_REQUIRED` when its retained support is implicated. Persisted
process-fault holds replay on cold registration without requiring the runtime to
manufacture replacement evidence. A later claim with independent actor/event/
time/receipt evidence does not satisfy the stale-replay identity and remains
usable.

Primary surfaces:

- `bilqis_mlx/runtime/_correction/accepted_corrections.py`
- `bilqis_mlx/runtime/_correction/accepted_stale_replay_ledger.py`
- `bilqis_mlx/runtime/_correction/accepted_stale_replay_runtime.py`
- `bilqis_mlx/runtime/_correction/accepted_correction_runtime.py`
- all six production owner before-use gates

### Major 3 — review authority packet was not self-contained

**Finding:** the Round-5 packet required outside context to reconcile the fresh
branch and widened production surface against the original C09 lane packet.

**Remediation:** this document carries the governing acceptance, exact failed
head, complete Round-5 finding set, authority decisions, changed production
surfaces, proof receipts, integration target, and bounded-review status in one
artifact. It supplements rather than rewrites the historical Round-5 packet.

## Authority decisions that must survive review

1. **Source-prefetch remains unprivileged.** Do not pass accepted-run mutation
   authority into worker processes merely to make Factory registration easy.
2. **Accepted C09 history is both append-only and externally committed.** The
   local ledger remains the replay sequence; the data-plane commitment proves
   the exact sequence expected for this accepted run.
3. **Correction branches and process faults are different state.** Concurrent
   source corrections remain branch-aware correction custody. A post-remediation
   stale replay creates an independent process-fault hold rather than being
   disguised as another source correction.
4. **Owner replacement is logical, not global.** A cold-loaded owner supersedes
   an older retained target only when the owner kind and exact owned-artifact set
   match. Distinct same-kind owners remain concurrently registered.
5. **No self-ratification.** Revalidation, remediation and later-evidence
   records remain source/host supplied; the accepted runtime may verify, route,
   persist and hold but may not fabricate evidence that clears its own holds.

## Current verification receipts

These receipts belong to the uncommitted Round-5 remediation working tree and
must be refreshed only if their dependency surface changes.

- Focused accepted-run remediation core: **20/20 PASS**.
  Covers concurrent branches, future-dependent correction activation, exact
  committed-history truncation detection, deferred multi-result retries,
  production stale-replay process faulting, independent later evidence, and
  immutable data-plane object-reference advancement.
- Widened C09 / owner / source-context / accepted-cache ring: **73/73 PASS**.
  Includes the full correction test directory, C09 revalidation tests, Factory
  retention adversaries, source-execution context tests, and the accepted-run
  remediation tests.
- `npm run quality:structure` against current reviewed unified: **PASS**.
- governance integrity: **PASS**.
- `python3 -B scripts/check_bamf_flow_control.py`: **PASS**; lane C remains
  ACTIVE and #752 is not blocked by a competing writer.
- `git diff --check`: **PASS**.
- Host ingress and real exact-cache consumer witness: **7/7 PASS**.

The historical Round-5 candidate receipts remain historical evidence only and
do not prove this remediation. Repository-required changed-scope and detached
leaf/premerge validation are recorded below only after they run on the final
repaired integration head.

## Final checkpoint fields

Populate these only after the engineering body is committed, current unified
is consumed at the integration boundary, and the remote feature ref is read
back exactly.

- Repaired exact head: `PENDING`
- Consumed unified exact head: `PENDING_INTEGRATION`
- `quality:changed`: `PENDING`
- BAMF contracts: `PENDING`
- detached `verify:leaf`: `PENDING`
- detached `verify:premerge`: `PENDING_INTEGRATION`
- EGM: `BLOCKED_AFTER_ROUND_5_PENDING_EXPLICIT_AUTHORITY`
- Final PR: `BLOCKED_PENDING_AUTHORIZED_EGM_PASS`
