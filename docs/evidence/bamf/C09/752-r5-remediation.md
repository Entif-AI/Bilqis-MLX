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
- Historical Round-5 remediation branch: `codex/752-r5-remediation-20261107`
- Final engineering recut branch: `codex/752-final-recut-20261107`
- Human-authorized one-off EGM episode: `C09-752-EGM-H1-20261107`
- H1 reviewed head: `b6f6a558addaaf16e5ccd94c2267fe338be19e54`
- H1 verdict: **FAIL — 2 Blockers, 2 Majors, 0 Nits**
- Human-authorized H2 EGM episode: `C09-752-EGM-H2-20261107`
- H2 reviewed head: `8006216c9103e77f609ad75a6c7cf1c28759fd5a`
- H2 verdict: **FAIL — 2 Blockers, 3 Majors, 0 Nits**
- Post-H1 repair branch: `codex/752-post-egm-h1-fixes-20261107`
- Required integration trunk: `codex/bamf-unified-base-20261028`
- Historical final-recut unified SHA:
  `58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`
- Current post-H1 repair unified SHA:
  `76f456776c88a642f79f5a7fa0df01bc729edb04`
- Current post-H2 engineering code freeze:
  `7a9a698865942af92c04217064c2e648fb8039cf`

Round 5 was a FAIL. This packet does not revise that verdict, claim a sixth
review round, claim EGM PASS, authorize a PR, or authorize merge/issue closure.
`docs/tasks/bamf-0.2/EGM_EXECUTION.md` caps an episode at five complete rounds.
The user subsequently authorized H1 and then one further exact-head H2 review.
Both reviews failed. H2 is the latest authorized review and remains historical
FAIL; the engineering repairs below do not rewrite that verdict. There is no
automatic further round. Any later exact-head EGM again requires explicit
human/design authority. Issue #752 remains OPEN and `EGM-Failed`.

## Human-authorized H1 finding closure in progress

The H1 review found four additional defects on exact immutable head
`b6f6a558addaaf16e5ccd94c2267fe338be19e54`. The repairs below are engineering
work only. They do not alter the H1 FAIL verdict or imply another EGM round.

### H1 Blocker 1 — live Factory training was outside accepted correction custody

**Finding:** the real Factory training bridge created gradient-bearing
`BamfCompiledBatch` rows without registering their AtlasFeature/PackedFrame
owners into accepted C09 custody. `require_pending_corrections()` is purposely
a no-op for an owner with no accepted target, so a correction already present in
the accepted ledger could be invisible before the B11 training read.

**Repair:** `_bind_b11_rows()` registers every compiled training batch with its
host-owned `SourceExecutionContext` before returning it, and
`execute_factory_candidate_step()` now requires that context to be bound to the
same accepted run before any neural execution. The source context now retains
the actual `AcceptedRuntimeHost` capability that minted it; matching `run_dir`
and correction-registry fields alone no longer satisfy the custody gate.
Structurally forged contexts therefore fail closed with
`FACTORY_SOURCE_CORRECTION_RUNTIME_REQUIRED`, while host-minted contexts clear
the gate. Source-prefetch workers remain unprivileged; authority stays at the
host boundary.

Primary surfaces:

- `bilqis_mlx/runtime/_batch/factory_training_bridge.py`
- `bilqis_mlx/runtime/_batch/factory_candidate_training.py`
- `bilqis_mlx/runtime/_source/source_execution.py`

### H1 Blocker 2 — motif custody mixed generation lifetime with batch identity

**Finding:** one generation-scoped `AcceptedExecutionCache` retained a single
`MotifArtifactOwner`, while that owner froze the first compiled batch's
occurrence-specific packed-frame IDs. A later legitimate same-generation batch
could therefore fail `BAMF_C09_MOTIF_OWNER_MISMATCH` before inference.

**Repair:** a retained motif *use* now has a batch-qualified immutable artifact
identity: retained manifest content remains `manifest.digest`, while the artifact
ID also commits the exact packed-frame artifact-ID tuple. The accepted cache
keeps weakly referenced owners per compiled-frame identity, so same-batch reuse
reuses custody, distinct batches get distinct dependency graphs, and dead batch
owners are not retained for the generation lifetime.

Primary surfaces:

- `bilqis_mlx/runtime/_correction/owners/atlas_motif_owner.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/execution_cache.py`

### H1 Major 1 — accepted history append was not crash-atomic

**Finding:** `append_record()` fsynced `events.jsonl`, synchronized the data-plane
index, and advanced the separate history commitment without one writer lock or a
recoverable transaction. Two real writers could race, and a crash after ledger
fsync but before commitment advancement could leave file and commitment
permanently divergent. The old test named “concurrent” executed serial calls.

**Repair:** accepted history uses a run-scoped process lock plus `flock` for
interprocess serialization. Before file append, the data-plane commitment
authority atomically publishes a `PREPARED` transaction containing the exact
prior file digest/size, prior history state, intended record, and target history
state. Restart reconciliation distinguishes no append, partial append, and full
append. Partial bytes are truncated only back to the committed exact prefix;
full intended append is synchronized and committed. Final history advancement
and transaction clearing occur in one SQLite transaction. The recovery protocol
therefore does not trust an auxiliary marker on the mutable ledger filesystem.

Primary surfaces:

- `bilqis_mlx/runtime/_correction/accepted/accepted_correction_ledger.py`
- `bilqis_mlx/runtime/_correction/accepted/accepted_correction_storage.py`
- `bilqis_mlx/runtime/_correction/accepted/accepted_correction_recovery.py`

### H1 Major 2 — registration could evict a still-live equivalent reader

**Finding:** accepted registration replaced an older same-kind target whenever
its owned artifact-ID set matched the new owner. A retained earlier context could
therefore remain readable after its correction target was removed.

**Repair:** accepted targets weakly reference physical owners. Multiple live
owners with equivalent immutable nodes and equivalent capability ledger state
remain registered concurrently and all receive later correction delivery. A
new owner with the same logical artifact IDs but divergent materialized node or
capability-ledger state is a re-materialization instead of an alias: it
explicitly supersedes the old target and marks the old owner fail-closed before
retirement. Dead physical owners disappear without unbounded target retention.

Primary surfaces:

- `bilqis_mlx/runtime/_correction/accepted/accepted_correction_runtime.py`
- `bilqis_mlx/runtime/_correction/accepted/accepted_correction_dispatch.py`
- `bilqis_mlx/runtime/_correction/accepted/accepted_correction_target.py`
- `bilqis_mlx/runtime/_correction/accepted/accepted_stale_replay_runtime.py`

## Human-authorized H2 finding closure

H2 reviewed immutable head `8006216c9103e77f609ad75a6c7cf1c28759fd5a`
and returned **FAIL — 2 Blockers, 3 Majors, 0 Nits**. The following repairs are
engineering closure only; H2 remains FAIL until a separately authorized future
exact-head review says otherwise.

### H2 Blocker 1 — unresolved C09 state could vanish across accepted successors

**Finding:** accepted correction evidence and live runtimes were scoped to one
accepted manifest. An unrelated accepted successor could advance the current
generation while ancestor corrections, holds, process faults, and
requalification evidence remained behind the previous manifest.

**Repair:** accepted C09 reads now walk the immutable accepted-manifest ancestry
and decode `events.jsonl` once in physical append order. Each generation's
existing crash-safe history commitment is still verified independently; no event
is copied, rekeyed, or rewritten into a successor. Cold successor custody
therefore sees unresolved ancestor evidence while retaining the original record
and commitment authority.

Focused regression:
`test_unresolved_correction_survives_unrelated_successor_and_cold_restart`.
It holds a real accepted motif on M0, publishes a legitimate unrelated retained
M1, clears process caches, and proves M1 refuses the affected motif before use.

### H2 Major 1 — another process could commit a correction after owner registration

**Finding:** durable accepted history was replayed at target registration, but an
already-registered reader could retain only process-local state while another
process committed a correction.

**Repair:** every accepted-owner before-use gate reconciles committed durable
history under the runtime lock and the existing interprocess ledger lock before
checking artifact holds. Persisted process-fault holds are refreshed there too.
The append path still releases the ledger lock before synchronous runtime
delivery, preserving lock ordering.

Focused regression:
`test_live_reader_observes_correction_committed_by_another_process` starts with a
live registered reader in process A, appends a valid correction in process B,
and proves A's very next read fails held without restart or re-registration.

### H2 Major 2 — learned-support invalidation dropped targeted requalification work

**Finding:** changed capability support could enter
`REQUALIFICATION_REQUIRED` while the production owner discarded the existing
`TargetedSourceTask` and `C10InvalidationIntent` semantics.

**Repair:** `CapabilitySupportArtifactOwner` now owns a one-capability
`RequalificationLedger` as its state authority. Changed revalidation invokes the
existing `mark_affected_capabilities()` semantics, retaining the exact targeted
source task and C10 intent. The capability-support journal is v2 and persists the
full ledger on HELD, CLEARED, and REQUALIFICATION_REQUIRED states, with v1
read compatibility. Accepted runtime flushes pending C10 intents idempotently to
the run-local Akasha outbox.

### H2 Blocker 2 — stale-replay requalification depended on live support owners

**Finding:** stale replay built its dependency/requalification view only from
currently registered physical owners. If learned support was not live when a
post-remediation stale claim arrived, the process fault could be skipped and a
later/cold support owner could miss `REQUALIFICATION_REQUIRED`.

**Repair:** stale classification supplements live owners with an authenticated,
non-registering capability-support census derived from the accepted B13 v3
source anchors. New process-fault records persist the complete
`RequalificationUpdate`; legacy process-fault rows without that field remain
readable and do not invent missing state. Late or cold support registration
replays the durable update, restores tasks/intents, and remains fail-closed.

### H2 Major 3 — F15 did not prove the learned-support production path

**Finding:** the prior F15 integration witness used only a composition owner and
did not prove retained generation identity, learned-support requalification, or
targeted task/C10 output.

**Repair / proof:**
`test_stale_fault_requalifies_support_loaded_only_after_fault` publishes real
source-qualified accepted support, deliberately leaves the support owner unloaded
during stale classification, and proves all of the following:

- one process fault is created after completed remediation and matching stale
  recurrence;
- the accepted generation remains unchanged;
- late-loaded support is `REQUALIFICATION_REQUIRED` and blocked;
- the exact targeted source task and C10 intent are present;
- the run-local C10 outbox contains exactly one event;
- clearing the process runtime and cold-loading support restores the same debt
  without duplicating the outbox event; and
- independent later actor/time evidence creates no new process fault.

H2 repair preservation ring on M3 Ultra: **32/32 PASS in 21.579s**. The ring
includes capability-support custody, accepted correction runtime, stale replay,
true concurrent writers, crash recovery, and C10 outbox idempotence. The focused
F15 witness re-ran after test-structure cleanup and passed in **1.411s**.

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

**Later #917 authority correction (2026-11-08):** the accepted-cache portion of
this historical remediation was subsequently rejected by fresh EGM. Binding a B14
authority through `AcceptedRuntimeHost` allowed the first caller to supply the
policy/context resolver and left a resolver-time currentness race. The repaired
contract therefore removes C09/B13 production issuance and cache inference from
`AcceptedRuntimeHost`; B14 remains without a production issuer until its genuine
upstream owner exists. This note preserves the earlier evidence without treating
that superseded integration as current authority.

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
4. **Owner replacement distinguishes aliases from re-materialization.** Live
   physical owners with the same logical artifact IDs remain concurrent when
   their immutable nodes and capability ledger state are equivalent. Divergent
   state under the same logical IDs is a new materialization: the older owner is
   marked superseded/fail-closed before its target is retired. Batch-qualified
   motif uses carry distinct artifact IDs and therefore never collide merely
   because they share one retained manifest.
5. **No self-ratification.** Revalidation, remediation and later-evidence
   records remain source/host supplied; the accepted runtime may verify, route,
   persist and hold but may not fabricate evidence that clears its own holds.

## Current verification receipts

The original focused receipts below were produced while the Round-5 remediation
body was being assembled. The final recut has since committed that body, replayed
only the #752/C09 semantic history onto current unified, and revalidated the
affected integration seams. Historical receipts are retained for lineage and are
not presented as proof of a later exact head.

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
- Post-H1 focused repair ring on M3 Ultra:
  - batch-qualified motif-owner custody: **6/6 PASS**;
  - accepted correction runtime, including two simultaneously live equivalent
    owners: **6/6 PASS**;
  - accepted runtime custody: **10/10 PASS**, including a real two-process
    concurrent-writer test and crash-after-ledger-fsync recovery;
  - source-context contracts: **6/6 PASS**;
  - capability-support owner/requalification custody: **6/6 PASS**;
  - accepted stale-replay runtime: **2/2 PASS**;
  - exact-cache authority integration: **2/2 PASS**;
  - production authority/cold-read custody: **13/13 PASS**;
  - A01-backed B11 forward began interactively and produced three real PASSes,
    but the aggregate crossed the interactive threshold and was deliberately
    stopped rather than polled. It is not counted as a completed receipt here.
  - A01-backed Factory persisted-correction witness likewise crossed the
    interactive threshold and was deliberately stopped. It remains pending a
    detached M3 run against the frozen repair candidate.
- Current post-H1 repair integration on unified
  `bb8e83f03e38b64018cfe357addd90a0a6d67297`:
  - `quality:changed`: **PASS** with **0 new changed-file findings**;
  - development structure: **PASS, 0 violations** after moving accepted-run
    correction custody into `_correction/accepted/` and Factory/retention batch
    tests into `runtime/tests/batch/factory/`;
  - governance integrity: **PASS, 0 violations**;
  - legacy-trainer authority checker: **PASS**; checker regressions **7/7 PASS**;
  - BAMF flow control: **PASS**; flow-control regressions **15/15 PASS**;
  - BAMF contract verification: **43/43 PASS**;
  - `git diff --check`: **PASS**;
  - post-refactor M3 preservation ring: **51/51 focused tests PASS** across
    motif ownership, accepted correction dispatch, accepted runtime custody,
    source context, capability support, stale replay, exact-cache authority, and
    production authority. The accepted-runtime subset was rerun again after the
    physical compartment move and remained **16/16 PASS**.
- Final recut on unified
  `58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`:
  - `quality:changed`: **PASS** with four inherited code-smell findings and
    **0 new changed-file findings**.
  - legacy-trainer authority checker: **PASS**; checker regressions **7/7 PASS**.
    The authoritative replay source remains
    `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`;
    Prometheus is stale and is not an adaptation source.
  - BAMF flow control: **PASS**; flow-control regressions **15/15 PASS**.
  - BAMF contract verification: **43/43 PASS**.
  - `git diff --check`: **PASS**.
  - focused accepted-correction / stale-replay / source / exact-cache /
    grouped-runtime / model-contract / model-forward / C02 batch seam:
    **26 passed, 11 skipped, 84 subtests passed**.
- The earlier exact candidate `f72c77171c6e1ba8b0a36a875ce8cd83fc86e2ca`
  produced a detached `verify:leaf` FAIL on an immutable M3 Ultra snapshot
  (`49838d198cae67708ac6d9fd24e779e26b9109b18052ff208059f6877328f35b`).
  All **86 unique failing test identities** from that candidate reproduce on
  pristine consumed unified `53eba37e5c9dd6ad065b1980fa4850c484aaa624`;
  there were **0 candidate-only failing identities**. That receipt is therefore
  retained as inherited-baseline attribution, not as a PASS and not as a #752
  regression. The later unified advance to `58eb36bb...` invalidated it as the
  final-head leaf receipt.
- Exact current code head `a18394d7a7bb5fa301dec2b1f2cc62ff65f1c99d`
  was then run through detached `verify:leaf` on M3 Ultra against unified
  `58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`. The immutable source/snapshot
  digest was
  `1a0bd993a9355ba1b5e2ba1a6c392eddb3d99c04874e7a283dea343bb0b43ce0`;
  the receipt finished **FAIL** with no source mutation. The differential gate
  reported **90 failed, 2785 passed, 187 skipped, 87 errors, and 1313 subtests
  passed**. This is not recorded as a PASS.
- Baseline attribution against pristine current unified used a second immutable
  M3 Ultra snapshot
  (`cab241e5b7019c0af6aebc1dd560c7f3cef156b8d7d01f587d8b744f0610c184`).
  Replaying the exact current red identities with the same xdist shape showed
  the same inherited failure/collection families. Twelve identities whose
  status differed under parallel scheduling were then isolated on both the
  candidate and pristine unified; both produced exactly **3 failed, 2 passed,
  7 errors**. The seven errors are the same missing pinned legacy-parent
  fixture, and the three failures are the same numeric-staircase baseline
  failures. No #752-introduced failing behavior was identified.

The historical Round-5 candidate receipts remain historical evidence only and
do not prove this remediation. Repository-required changed-scope and detached
leaf/premerge validation are recorded below only after they run on the final
repaired integration head.

## Final checkpoint fields

Populate these only after the engineering body is committed, current unified
is consumed at the integration boundary, and the remote feature ref is read
back exactly.

- Repaired code head before evidence-only freeze:
  `7a9a698865942af92c04217064c2e648fb8039cf`
- Consumed unified exact head:
  `76f456776c88a642f79f5a7fa0df01bc729edb04`
- `quality:changed`: `PASS`
- BAMF contracts: `PASS_43_OF_43`
- H2 focused preservation ring: `PASS_32_OF_32`
- detached `verify:leaf`: `NOT_RERUN_AFTER_H2_FAIL`
- detached `verify:premerge`: `NOT_RUN_WHILE_EGM_FAILED`
- EGM: `FAILED_H2_2_BLOCKERS_3_MAJORS_REPAIRED_ENGINEERING_ONLY`
- Final PR: `BLOCKED_PENDING_AUTHORIZED_EGM_PASS`
