# BAMF-0.2 first-student foundation preflight

Issue #543 owns the generation-zero caller boundary used before the human-facing
create, dry-run, and resume commands in #542. Its API is:

`preflight_bamf_foundation(config, admitted_release, new_run_dir) -> LaunchReceipt`

`BamfFoundationConfig` is immutable launch input. It carries the admitted source
run, operator-selected `run_id` and `run_seed`, the loaded semantic graph, a
portable `AtlasArtifactIdentity`, and an explicit `AdamWHyperparameters` record.
The optimizer values have no hidden default. B13 seals the exact supplied values;
B01 still owns parameter and decay geometry, and B12/B13 construct fresh zero
moments and update counts. Historical optimizer state is never migrated.

Preflight accepts only an absent or empty target directory. C16.1c/#950 moves new
generation-zero C09 authority completely outside that target: on Darwin the host
administrator provisions `/etc/entif-ai/bilqis/source-authority-registry.json`
independently of Bilqis. The path is fixed in production; the CLI, config,
environment, package API, and target run directory cannot select it. Runtime may
read and validate the host file but never creates, replaces, repairs, relocates, or
populates it.

During generation-zero preparation B13 snapshots the exact validated host registry
record, digest, and origin `HOST_SYSTEM_V1` into the owner-derived correction
frontier. Publication rereads the fixed host root before pointer installation and
requires exact equality with that prepared binding. Missing, unsafe, malformed, or
drifted host authority therefore fails before a new run becomes current. A copied
registry inside the target run directory has no authority for a new lineage.

Host-root rotation is not supported by #950. Administrators must not rotate the file
concurrently with Bilqis operations; later authority boundaries reread the selected
root and fail closed on drift. Historical pre-#950 lineages retain their recorded
run-local #917 custody semantics and may use the narrowly defined one-time ordinary
retained-successor compatibility anchor. That historical path is derived from
authenticated accepted custody and is never selected by a caller or used by a new
C16.1c generation zero.

Preflight replays the current Factory admission from the source run, resolves the
source-owned Atlas artifact, derives the ordinary Factory teacher projection and B01
generation authority, and enters B13's existing `prepare_initial_generation` /
`publish_initial_generation` transaction. The source run is read-only. The target
receives generation zero at optimizer step `0`; preflight performs no candidate or
training update.

`LaunchReceipt` is observational, not authority. It records the immutable B13 run
identity, published manifest, Factory release, Atlas identity, exact optimizer
hyperparameters, and exact schema versions for material launch inputs and
generation-zero outputs. The persisted B13 bundle remains the source of truth for
the active ABI, source/Factory/teacher provenance, topology, extents, implementation
identity, parameter ledger, optimizer moments/counts, and run seed.

The dashboard snapshot describes the newborn lineage. Admitted grade scope comes
from the Factory execution plan. Optimizer step and visits are `0`, stage is
`READY_FOR_HUMAN_START`, and status is `NOT_STARTED`; predecessor progress is not
copied into the fresh student.

Akasha materialization, low-bit cache, and private-journal intake are not launch
dependencies. The receipt reports no required optional services, and preflight
does not initialize them. `bilqis_mlx.cli` re-exports the immutable config,
receipt, and preflight API for #542; #543 adds no parser flag or command dispatch.

Focused verification:

`python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/test_bamf_first_student.py`
