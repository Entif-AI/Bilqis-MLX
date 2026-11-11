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

The low-level fresh preflight owner accepts an absent or empty target and, for an exact
C16.1a fresh-create retry, the two durable B13 pre-seal prefixes or an exact sealed
generation-zero recovery candidate. Arbitrary occupied targets still fail closed;
pointerless `--resume` never invokes this recovery path. C16.1c/#950 moves new
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

### Host-administrator installation and recovery

Provisioning the fixed C09 root is an operating-system administration task, not a
Bilqis command. Derive the registry record from the separately governed C09
key/rights source; Bilqis neither generates those keys nor decides their rights.
Before installation, create any missing administered `entif-ai` / `bilqis`
directories as root, then verify the complete physical
`/private/etc/entif-ai/bilqis` directory chain is UID 0 owned, not group/world writable,
and has no extended ACL ALLOW grant
that gives a non-root principal mutation rights. `/etc` itself must be the standard
UID-0 Darwin symlink whose relative target is exactly `private/etc`.

Install only a complete registry. Create the temporary file inside the already
verified `bilqis` directory, write the canonical registry bytes, `fsync` the file,
then set UID 0 ownership and the approved non-group/world-writable mode/ACL, atomically
rename it to `source-authority-registry.json`, and `fsync` the containing directory.
Do not install through a symlink, a caller-selected path, or a Bilqis runtime helper.
After installation, preserve the exact bytes, canonical record, and digest in the
host backup/recovery system so an accepted lineage can be recovered without changing
its trust root.

Recovery for an existing accepted lineage is deliberately narrow: restore the exact
previously accepted registry bytes through the same ownership, mode, ACL, durable
temporary-file, atomic-rename, and directory-`fsync` checks, or stop. Substituting a
different registry is rotation/migration, even when it contains otherwise valid C09
keys, and is forbidden until a separate governed protocol authorizes that transition.
Never restore or rotate the fixed root concurrently with Bilqis operations.

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

### Human create, Atlas enrollment, and resume

C16.1a/#542 layers the persistent operator lifecycle over this owner API. Fresh
`--dry-run` validates the complete foundation identity and returns
`READY_TO_CREATE` without creating the target. Fresh `--human-run` calls this
preflight and returns `CREATED` after generation zero is current; the operator does
not enter the learner in this leaf.

The default effective admission policy is `staged`. For an explicit
`atlas-release` request, the CLI parses the versioned non-authoritative C07 v2
enrollment request as request data and validates its known run/topology/Atlas fields
before publication. It is not itself a lease or authority. After
generation zero is accepted, it creates `AcceptedRuntimeHost(run_dir)`, obtains the
opaque generation-bound C09 `SourceAuthorityRuntime`, and delegates exact lease
persistence/readback to C07. It never accepts a raw registry or uses the launch
receipt, CLI fields, target path, or lease file as a C09 trust root. A failed
post-genesis lease validation installs no C07 current reference; the accepted
generation zero remains a valid staged run.

Ordinary resume cold-loads the accepted B13 generation and feature receipt, derives saved
run id/seed, topology, Atlas identity and optimizer hyperparameters, and derives
the effective admission policy through authenticated C07 lease readback. Omitted
settings use those saved values. Conflicting explicit overrides reject before
writes, and ordinary resume takes no scope. The one first-enrollment resume form is
explicitly `--human-run --resume --admission-policy atlas-release
--atlas-admission-scope <enrollment-request.json>`; the request remains
non-authoritative and C07 derives authority only from accepted run custody. Both
dry-run and resume/enrollment remain neural-inert here.

If a fresh create is interrupted before the generation-zero pointer is installed, do
not switch to resume. A pointerless target carrying BAMF-v2 lifecycle evidence rejects
resume with `BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY`. Repeat the
original fresh create command with the same run id, seed, topology, complete AdamW
group and Atlas manifest. B13 alone decides whether the target is the exact sealed
genesis that may converge or an occupied/malformed target that must remain untouched.

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
