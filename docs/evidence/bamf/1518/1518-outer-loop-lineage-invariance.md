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
leaves future ordinary cold loads lineage-depth invariant.

## Structural proof

Focused regressions establish:

- cold accepted hydration at generation 5 loads one current numerical payload,
  the same bounded count as shallow lineage;
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
  execution cache rather than rehashing the parameter tree.

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

## What this packet does not claim

It does not claim a new live-trainer wall-clock result. The human trainer remained
untouched by automated verification. The post-repair claim is architectural and
testable: ordinary hot and cold accepted-state proof is bounded by current state,
not lineage depth; cadence restart is projection-plus-tail; and historical replay
is an explicit audit/migration operation.

The observed ~11-second cold selected-source construction remains a distinct
owner. This issue does not relabel that cost as accepted-history currentness.
