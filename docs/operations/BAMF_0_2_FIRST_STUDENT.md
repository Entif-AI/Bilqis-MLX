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

### C16.2c bounded verification under ADR-141

C16.2c does not use a full-model real-source pytest run as a leaf or turn-in gate.
The historical four-node live module is retained only as provenance and implementation
reference. ADR-141 retires it from executable qualification because one isolated node
ran for more than fourteen hours without producing a result. Do not launch those
historical nodes again as tests.

The over-budget run was not waiting on useful learner feedback. A process sample showed
the dominant work in canonical JSON encoding, `bytes.hex()`, and SHA-256 over large
model and optimizer state. The run was terminated as incomplete and over-budget. Its
partial receipt and sample remain evidence; they are neither PASS nor product failure.

Close C16.2c with claim-specific bounded proof:

1. Reuse exact-head C16.1, #992, #993, C03 custody, C05 fixed-school, B13 publication
   and rejection receipts while their tested assumptions remain unchanged.
2. Run the cheap C16.2c contract regressions for mature C03 lineage reuse, source
   blocking of non-admitted capabilities, two-family release/scope equivalence, and
   staged receipt composition.
3. Use existing bounded cold-resume and rejection-custody regressions to prove pointer,
   parent, optimizer, and owner-visible continuation invariants. Do not rebuild a
   full model merely to re-prove those owners together.
4. Add a new integration check only when its expected wall-clock duration is known and
   below two hours. Prefer seconds-to-minutes checks. Convert any discovered defect
   into a cheap deterministic regression before another attempt.

A whole-system learner exercise that cannot satisfy ADR-141 is not a test. Defer it
until the system is assembled and the human operator explicitly starts a non-test run
with live dashboard visibility. That run is exploratory operational diagnosis, not a
hidden prerequisite for #994 or #544. It may reveal behavior that no assertion suite
knew to ask about.

The future owner-start command remains:

`npm run train -- --human-run --resume --run-dir <accepted-bamf-run>`

C16.3/#545 still owns persistent production dispatch. C16.2 remains neural-inert
outside bounded disposable checks.
