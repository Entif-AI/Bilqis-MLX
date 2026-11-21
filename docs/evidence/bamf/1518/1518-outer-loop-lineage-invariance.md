# #1518 BAMF outer-loop lineage-invariance evidence

This packet records the bounded repair for #1518 and child architecture issue
#1526. It is not an authorizing production run. Automated verification did not
start, restart, or mutate the human trainer.

## Production observation before the repair

Read-only production observation found a representative four-step visit at about
432.839 seconds total:

- planning/cadence: 217.997 s;
- selected-source materialization: 11.021 s;
- four candidate optimizer steps combined: 6.316 s;
- retention: 66.985 s;
- retention target solver construction: 43.725 s;
- target parent + candidate assessments: 15.462 s.

An adjacent visit spent about 83.5 s validating accepted generation and source
custody before planning. These are pre-repair observations, not post-repair
benchmark claims.

## Corrected authority architecture

Accepted authority is durable state. Ordinary hot use and ordinary cold restart
do not reconstruct it by replaying accepted history.

Each accepted generation receives an immutable `AcceptedAuthorityCheckpoint`.
A dedicated B13-owned protected per-run tip in the external SQLite data plane
advances only by compare-and-swap from the exact authenticated parent checkpoint.
Generic object/reference APIs cannot mint or advance this authority.

The checkpoint binds the current run/generation, manifest, acceptance, pointer,
acceptance file, run identity, topology/extents/implementation, optimizer step,
source/semantic/factory/genesis authority, current feature receipt/artifact, and
the exact parent checkpoint anchor required for successor publication.

Normal cold load validates only the protected current tip/checkpoint, current
immutable BAMF bundle, current acceptance under checkpoint-frozen parent facts,
current accepted feature artifact/commitment, and genuinely live mutable
source/currentness edges. It does not open ancestor BAMF bundles or replay
accepted feature ancestry.

## Publication and crash semantics

Publication is ordered across the SQLite and filesystem atomicity domains:

1. install the immutable child bundle;
2. persist and validate child acceptance;
3. persist the current immutable feature artifact/commitment;
4. store the child accepted-authority checkpoint;
5. CAS the protected B13 tip from the exact parent checkpoint to the child;
6. atomically publish `bamf-state.json`;
7. reconcile the outbox.

A crash after checkpoint creation but before tip advancement leaves an inert
orphan. A crash after tip advancement but before filesystem pointer publication
leaves one recognized recovery state: the protected tip may be exactly one
generation ahead of the pointer, and recovery advances the pointer only to that
exact checkpointed child. Any larger gap, fork, or inconsistent rollback fails
closed.

## Feature authority

Candidate and pre-acceptance feature lineage remains strict. A changed feature map
must be authenticated against its direct predecessor while the G -> G+1
transition is being established.

After acceptance, publication persists a content-addressed current feature
artifact plus `AcceptedFeatureArtifactCommitment`. Ordinary cold consumption
checks the checkpointed current artifact intrinsically and does not require a
predecessor payload. `_accepted_feature_context()` remains only as an explicit
historical audit/migration oracle.

## Cadence authority

Active-grade cadence persists its authenticated projection frontier in the data
plane. Ordinary restart resumes from that projection plus the unseen indexed event
tail. Missing or diverged projection state requires an explicit rebuild; normal
runtime does not silently full-replay terminal history.

## Legacy migration

Missing accepted-authority checkpoint state is visible and fail-closed. Normal
runtime never falls back to historical replay.

`backfill_current_accepted_authority()` is the explicit migration entry point.
It audits the legacy accepted history once, persists the current feature artifact
and an audit receipt, seeds an `AUDIT_BACKFILL` checkpoint/protected tip, and
leaves future ordinary cold loads lineage-depth invariant. The backfill acquires
exclusive BAMF operator custody when called directly and may reuse only a live,
owner-issued same-run/same-thread custody token when invoked from an already-held
operator lock. Active unrelated operator custody remains fail-closed.

## Structural proof

Focused regressions establish:

- cold accepted hydration at generation 5 loads one current numerical payload,
  exactly the same count as generation 1 (`1` payload load in each case);
- current checkpoint feature authentication fails if historical feature replay,
  historical bundle loading, or feature rebuilding is attempted;
- a crash after protected-tip commit but before pointer publication recovers
  forward to the exact child;
- rolling the filesystem pointer back by more than one generation is rejected as
  `BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT`;
- generic references cannot forge the protected tip;
- missing checkpoint authority remains a visible error until explicit backfill;
- cadence cold restart consumes the durable projection frontier and unseen tail;
- accepted execution binding and target-first retention reuse the accepted parent
  execution cache rather than rehashing the parameter tree;
- ordinary A02 vocabulary staging consumes the checkpoint-authenticated current
  feature context and snapshot without historical feature replay or a second Atlas
  snapshot load;
- accepted-authority backfill is idempotent and cannot mutate while another BAMF
  operator owns the run unless the caller presents the exact live custody token.

The old process-local feature-currentness cache and the doctrine that cold restart
should replay accepted history were removed rather than preserved behind a new
wrapper.

## Timing coverage

Visit telemetry exposes `accepted_state_setup_wall_seconds`,
`accepted_state_setup_other_wall_seconds`, `accepted_runtime_host_wall_seconds`,
`accepted_generation_load_wall_seconds`, `accepted_source_context_wall_seconds`,
`accepted_feature_authentication_wall_seconds`, existing
planning/source/candidate/retention substages, accepted publication timing, and
`rejection_wall_seconds`.

No device synchronization was added solely for timing.

## Post-repair disposable production-shaped witness

The human production trainer remained untouched. A disposable GPU-backed profile
used the real source-owned training step, real generation-1 accepted publication,
real C03 teacher advancement, real accepted-runtime cold setup, and the production
C05 retention owner. The notification-aware detached runner snapshotted the source
tree before launch and verified that the source worktree was not mutated during the
run.

Detached receipt:

- label: `1518 generation-1 retention profile v6`;
- source snapshot SHA-256:
  `795a32a2c7aec802e84b930c28e36ccd10ce154359297a014542db98f6b7d3e8`;
- return code: `0`;
- source mutated during detached run: `false`;
- measured accepted visit generation: `1`.

Measured post-repair timings from that disposable production-shaped visit:

- accepted-state setup: `2.370273 s`;
  - accepted runtime host: `0.729007 s`;
  - accepted generation load: `0.001412 s`;
  - accepted source context: `1.263252 s`;
  - accepted feature authentication: `0.376602 s`;
- retention setup: `0.036609 s`;
- retention total: `19.873033 s`;
- retention target solver construction: `0.843849 s`;
- retention target parent assessment: `6.337149 s`;
- retention target candidate assessment: `6.215945 s`;
- candidate training step: `31.978532 s`;
- complete measured attempt: `51.851700 s`.

These values are not presented as a same-machine speedup ratio against the human
trainer baseline. They are a post-repair production-path witness. The structural
lineage-depth claim is established separately by generation-1 versus generation-5
cold hydration performing exactly one accepted payload load each.

For context only, the pre-repair human trainer observation recorded about `83.5 s`
of adjacent accepted-state validation, `66.985 s` of retention, and `43.725 s` of
retention solver construction. The disposable post-repair path is therefore no
longer exhibiting the same order-of-magnitude accepted-history and solver setup
cost, without using the human trainer as a benchmark target.

## Verification receipt

The following focused proof was run on the repaired, already-`origin/main`-integrated
tree before the final repository gate:

- current admission/control-plane ownership ring:
  `42 passed, 3 subtests passed in 21.78s`;
- Atlas vocabulary semantics:
  `12 passed, 2 skipped, 3 subtests passed in 0.52s`;
- cadence projection/replay/recovery after structural split:
  `18 passed in 0.54s`;
- accepted hydration/foundation/recovery/migration on the final repaired tree:
  `14 passed in 8.06s`;
- checkpoint feature authority:
  `2 passed`;
- accepted solver/mentor reuse:
  `14 passed`;
- #1504 direct throughput regressions:
  `4 passed`;
- source prefetch/reuse:
  `20 passed, 9 subtests passed`;
- real gated A02 production staging witness:
  `5 passed in 54.98s`;
- exact motif/C03 teacher-successor custody proofs used by the generation-1
  disposable witness:
  `1 passed in 0.84s` and `1 passed in 1.29s`.

The final repository gate was intentionally closed incrementally rather than
re-running already-green suites. Detached `verify:leaf` v4 had already passed
structure, governance, changed-file smell, legacy-trainer checks,
invariant-transfer checks, flow-control checks, and `bamf:test` with `491/491`
passing. Its only failure was `bamf:security:test`, where four Electron files
could not load the declared `ajv@8.20.0` runtime because the detached source
snapshot omitted ignored `node_modules` while rebinding only `.venv`.

The detached runner now exposes both ignored local runtimes to its immutable
source snapshot without copying them. Verification of that closeout delta was:

- detached-runner source-isolation regression tests: `7 passed`;
- exact four Electron files that failed in v4: `18/18 passed`;
- complete `bamf:security:test`: `73/73` Node tests plus `10/10` Python
  `test_electron_bridge` tests passed.

No second `verify:leaf` was run after this runner-only repair because doing so
would have repeated the already-green 491-test BAMF suite and repository quality
checks without an implementation change in those owners.

Legacy accepted runs created before the durable B13 checkpoint existed are
handled at the explicit human resume boundary. If and only if a mutating
`--human-run --resume` encounters
`BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED`, the operator boundary acquires
exclusive BAMF operator custody, performs the one-time audited
`AUDIT_BACKFILL`, releases that custody, and retries the current accepted load
once. Dry-run and non-human paths remain non-mutating and fail closed, and no
other authority error is eligible for this migration path. Focused proofs cover
legacy human resume, dry-run non-mutation, and the already-current checkpoint
path (`3 passed`), while the underlying migration owner test remains green
(`1 passed`).

The same human resume boundary now owns the one-time cadence projection
migration required by pre-projection runs. Ordinary resume first checks the
incremental cadence projection. If and only if it encounters
`BAMF_ACTIVE_GRADE_CADENCE_PROJECTION_REBUILD_REQUIRED`, a mutating human
resume acquires exclusive operator custody, performs the explicit authenticated
history rebuild once, releases custody, and rechecks the incremental projection.
Dry-run remains non-mutating and reports the rebuild requirement. No other
curriculum error is eligible for this recovery path.

## Tensor-thin historical custody invariant

The storage lifecycle now intentionally separates executable current state from
authenticated historical state. Current executable custody still requires the
current tensor payload object. Accepted historical custody requires immutable
manifest/node identity, acceptance, sidecars, run/lineage metadata, optimizer
metadata, and tensor binding identity, but not the historical tensor payload
bytes themselves.

This contract was locked by a fail-before regression that created an accepted
generation chain, ran the current file-GC policy, and confirmed that the parent
tensor object had been reclaimed while the current tensor remained present.
Before the repair, current acceptance authentication reopened the parent with
full bundle custody and failed with
`SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID` /
`DATA_PLANE_BUNDLE_PAYLOAD_DRIFT`. After the repair, the same accepted history
authenticates through tensor-thin historical custody without restoring blanket
historical tensor retention.

A complementary current-custody regression deletes the current tensor object
and proves `load_bamf_bundle()` still fails closed with
`DATA_PLANE_BUNDLE_PAYLOAD_DRIFT`. The existing storage-lifecycle witness also
remains green: accepted ancestry does not pin every historical tensor.

Metadata-only ancestry readers were migrated across cadence replay, Atlas
accepted-factory and obligation discovery, generated-grade ancestry and
correction replay, owner projection, C09 capability-support history, historical
Factory authority, and profile retry. In the searched startup/history families,
the only remaining full bundle load is the deliberate current-tip C09 execution
digest that hashes live executable parameters.

The implementation landed at
`c668acff766d8774c0a71c8ad1385d5ba7d44529`. Focused verification on the
invalidated owners was `26 passed in 8.89s`; staged anti-monolith reported
`0 violations`, staged smell audit reported `0 findings`, and
`git diff --check` was clean. Automated verification did not launch or mutate
the sovereign human trainer.

The BAMF terminal cockpit was also repaired at this cold-resume boundary. Its
live trainer observation is persisted on a one-second heartbeat, but the screen
previously reread that file only when an unrelated progress/event callback
caused a draw. The human trainer now runs a display-only 0.5-second redraw loop
under a reentrant board lock; display refresh never owns or mutates neural
state. On board construction, longitudinal exam/graduation evidence is restored
from the complete journal while visible tables remain bounded, so old complete
whole-student exams can populate `EXAM`, `STUDENT LATEST`, `STUDENT BEST`, and
lifetime graduation data even when they fall outside the recent display window.
At human resume, execution-local counters are reset and live BAMF observations
drive current-session visits, attempted steps, retained visits, RTN%, ST/M and
R/H without conflating prior-session history. Focused cadence/dashboard/renderer
verification passed 40 tests across the directly affected owners.

After the user's sequencing correction, `origin/main` was reconciled before the
final expensive throughput witness. The integrated main head is
`0ab5f893d4653e113440160851eeb24627fc0d9a` and the local integration merge is
`5631e16f3920ae0f2c308c0a9a17f7998948817b`. The integration-invalidated seam
was rerun only once after that merge: `10 passed in 0.89s`.

## Post-main six-step learning-first operator witness

The final throughput authority for this patchset is a disposable, non-authorizing
production operator-path witness through `prepare_bamf_visit(..., steps_per_visit=6)`.
It did not publish, did not mutate the human run, and used `strict_evidence=false`.
The detached runner again verified that the source worktree was not mutated.

Detached receipt:

- label: `1532 real operator six-step learning-first v5 post-main-reconcile`;
- detached schema: `bilqis.bamf.detached-long-run/v2`;
- source snapshot SHA-256:
  `83d00f2e87825cb5227a0739e796d8c49df3558f813a09ecbc56e4059c75c8d9`;
- return code: `0`;
- source mutated during detached run: `false`;
- operator status: `REJECTED` after a lawful completed six-step candidate visit;
- selected capability: `A.EDGE`;
- candidate update steps: `6`.

Because the machine's declared legacy trainer current pointer referenced a data-plane
node unavailable both in the isolated witness plane and through the host default
path, the witness explicitly substituted the repository's deterministic C03 bootstrap
fixture. It also used the production-shaped `COMBINED_REGISTRY` plus the matching
fixture `owner:c06` signer so disposable C09/C06 authority was internally coherent.
Those substitutions are disclosed in the witness payload. They are scaffolding for a
non-authorizing throughput measurement, not claims of live legacy-trainer authority.

Measured operator-path timings:

- accepted-state setup: `0.326840 s`;
- planning: `40.966371 s`;
- selected-source materialization: `10.020139 s`;
- six candidate optimizer steps combined: `4.856691 s`;
  - step walls: `0.602360`, `0.859840`, `0.857885`, `0.896890`, `0.773753`,
    `0.865963 s`;
- retention total: `18.859068 s`;
  - target preparation: `5.527459 s`;
  - parent target assessment: `5.975979 s`;
  - candidate target assessment: `6.052372 s`;
  - target solver: `0.777300 s`;
- target evaluation aggregate: `12.025718 s`;
- complete timed visit: `75.077155 s`;
- total process wall including disposable setup: `101.907906 s`.

This clears the issue's explicit under-two-minute six-step requirement. It does not
meet the under-one-minute ideal. The remaining wall is dominated by operator
orchestration, especially planning, source materialization, and retention. The neural
candidate path is no longer the dominant owner: all six production-path candidate
steps are subsecond and their combined wall is under five seconds. For comparison,
the earlier #1504 production operator witness reported roughly `0.84-1.00 s` candidate
steps, so the current candidate kernel is not exhibiting the regression that motivated
this repair.

The separate `222.863 s` six-step C05 component witness is not operator throughput
authority. It repeatedly invoked the lower-level direct candidate-training horizon and
bypassed production operator prepared-source reuse; it remains useful component
correctness evidence only.

## What this packet does not claim

It does not claim a controlled apples-to-apples speedup ratio against the human
trainer or a live human-run benchmark. The human trainer remained untouched by
automated verification. The post-repair claim is architectural plus disposable
production-path evidence: ordinary hot and cold accepted-state proof is bounded by
current state rather than lineage depth; cadence restart is projection-plus-tail;
retention consumes current accepted execution state; historical replay is explicit;
and a six-step learning-first operator visit now completes inside the required
under-two-minute envelope.

The remaining performance owners are planning (~41 s), selected-source materialization
(~10 s), and retention (~19 s). They are not relabeled as accepted-history currentness
or neural-training cost.
