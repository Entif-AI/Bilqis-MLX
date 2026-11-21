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

Immediately before freezing this packet, `git fetch origin main` confirmed
`origin/main` remained at
`38813530c3fc4b803f7cf4b8b1e800b978f49d74`, which is already integrated by merge
commit `0623b992eff7052a8331b6ae6bfb91540272d468`.

## What this packet does not claim

It does not claim a new live-trainer wall-clock result or a controlled apples-to-
apples speedup ratio against the pre-repair human trainer. The human trainer
remained untouched by automated verification. The post-repair claim is both
architectural and production-path tested: ordinary hot and cold accepted-state
proof is bounded by current state rather than lineage depth; cadence restart is
projection-plus-tail; retention consumes current accepted execution state; and
historical replay is an explicit audit/rebuild/migration operation.

The observed ~11-second cold selected-source construction remains a distinct
owner. This issue does not relabel that cost as accepted-history currentness.
