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

### C16.2 disposable launch witness and future handoff command

C16.2 proves disposable learning readiness; it does not start the persistent BAMF
learner. Its exact future owner-start command is:

`npm run train -- --human-run --resume --run-dir <accepted-bamf-run>`

Cold resume after interruption uses the same command shape. The parser and current
resume preflight accept this form against accepted B13 custody, but the C16.1a
lifecycle remains neural-inert and returns `READY_TO_RESUME`; C16.3/#545 owns the
persistent production dispatch that follows this handoff.

The C16.2c disposable acceptance witness uses the real accepted owner chain:
accepted B13 custody, C03 teacher selection/provenance, C02/C08/B11 candidate
execution, C05 owner-derived fixed-school retention, and B13 publication/rejection.
It also requires a real damaging disposable candidate to be rejected and durably
recorded without changing accepted parent custody, plus uninterrupted versus
cold-process equivalence of the next bounded update. No target `state.json` is part
of this witness, and no persistent student or persistent optimizer is started.

For the disposable accepted-generation transition only, C16.2c owns a deterministic
test fixture for the still-caller-supplied C03 successor fields: `next_seed` is the
selected visit seed plus one and `cursor` is the taught source row id. Those values
make the witness reproducible; they do **not** claim production teacher-trajectory
authority. The resulting launch-witness receipt records that limitation together
with parent/retained generations, optimizer state digests and steps, selected visit,
C05 decision, Factory/source identities, and the uninterrupted-versus-cold next
update result.

### C16.2c staged verification

Do not run the complete real-source C16.2c module as one qualification command.
Its live checks have different failure boundaries and must remain independently
rerunnable.

Run cheap contract checks first. They cover mature C03 lineage reuse, the future
capability source block, the two-family release/scope contract, and staged receipt
assembly. Reuse the existing C16.1, #992, #993, C03 custody, B13 rejection, and
operator-command receipts while their tested assumptions remain unchanged.

The remaining live evidence has four stages:

1. Run one real C05 rejection witness and verify B13 rejection preserves accepted
   pointer, bundle, optimizer, and cold parent custody.
2. Run one admitted `A.IDENTITY` witness through the same real C03, C02/C08/B11,
   and C05 owner chain. This is the second-family traversal required by the
   first-start negative; it does not need a second accepted publication.
3. Run one accepted B.IDBOOLOPS transition through C03, C02/C08/B11, C05, and B13.
   In that same process, execute the uninterrupted next update and persist the
   accepted run plus warm-stage receipt under `BILQIS_C16_2C_STAGE_ROOT`. Those two
   actions are one irreducible stage because a process restart would make the warm arm
   cold.
4. Start a new process against that same accepted stage root. Execute only the cold
   next update and compare it with the persisted uninterrupted receipt.

Run MLX-heavy stages on `m3-ultra` through SSH from a digest-pinned detached source
snapshot. Use separate isolated attempt roots for rejection, second-family, and the
accepted-plus-cold chain. The cold stage must reuse the accepted stage root. Use the
accepted A01 artifact. Do not poll the remote job from chat. If rejection,
second-family, or accepted-plus-warm fails, preserve that failed root and rerun only
that stage in a fresh attempt root. A cold-stage failure may reuse the unchanged
accepted B13 custody because cold continuation is the behavior under test. Evidence-
only content-addressed sidecars may accumulate without changing that accepted custody.
Do not restart already-passing stages unless their source, Factory, feature, C05, or
B13 custody assumptions changed.

ADR-138 resource containment is part of the launch contract, not an optional operator
check. Set `BILQIS_TEST_WORKERS=1` for every stage. Before detaching, run the cheap
`require_mlx_verification_resources()` preflight from
`c16_2c_resource_preflight.py`; the live test repeats the same gate before foundation
or model loading. For this disposable qualification the preflight requires at least
20% system memory free, at least 10% swap headroom, and no other pytest,
`run_studio_proof.py`, or detached-long-run worker outside the current process
ancestry. These are conservative C16.2c launch thresholds, not a new repository-wide
allocator policy. Each live process then enters the repository
`training_memory_policy(mx)`, which sets the MLX free-buffer cache limit to zero and
clears the cache before and after the stage. If the preflight fails, do not launch or
retry until the host state changes.

The M3 launch must therefore chain the preflight and detached launch, for example:

```text
BILQIS_TEST_WORKERS=1 <complete-python> -c \
  'from bilqis_mlx.runtime.tests.capability.factory.owner.c16_2c_resource_preflight import require_mlx_verification_resources as p; print(p())' \
&& BILQIS_TEST_WORKERS=1 <complete-python> scripts/bamf/detached_long_run.py launch ... -- \
  env BILQIS_TEST_WORKERS=1 BILQIS_A01_ATLAS_BUNDLE=<accepted-a01> \
      BILQIS_C16_2C_STAGE_ROOT=<isolated-stage-root> \
      <complete-python> -m pytest -q <live-module>::<one-node-id>
```

Verify the detached PID/log/receipt/source digest once, then yield. Do not poll it.

The expensive test module is `DETACHED_ONLY`. Invoke its four test node IDs
separately. A cold-stage skip is not acceptance evidence; it means the accepted stage
receipt is absent. The cheap C16.2c helper tests remain suitable for the ordinary
development loop.

The live node IDs are:

- `test_c16_2c_stage_real_rejection_records_rollback_without_parent_mutation`
- `test_c16_2c_stage_second_admitted_family_traverses_source_c03_c05_chain`
- `test_c16_2c_stage_accepts_generation_one_and_records_uninterrupted_next_update`
- `test_c16_2c_stage_cold_next_update_matches_persisted_uninterrupted_stage`

Pass exactly one node ID to pytest for each detached launch. Never qualify #994 by
running the whole live module in one command.
