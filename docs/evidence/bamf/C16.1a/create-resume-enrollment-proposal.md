# C16.1a persistent create/resume enrollment proposal

Status: DESIGN AMENDMENT / EGM-PENDING
Issue: #542 / C16.1a
Reviewed unified base: `2c572202978df9542e379cfb975007cdea3f05ad`
Historical implementation candidate preserved for evidence: `291f7a39cc6f083c222fff604e8a3d95ab98e497`
Pinned EGM: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`

## Why this amendment exists

C16.1a owns the human create/dry-run/resume surface after C16.1b/#543 and
C16.1c/#950 establish generation-zero B13 and C09 custody. The first implementation
attempt treated `--atlas-admission-scope` as a complete `AtlasAdmissionLease` before
generation zero existed. That cannot be a lawful fresh-create contract because the
lease contains `LeaseRunIdentity.initial_generation_digest`, which is derived from
the accepted target generation-zero `BamfRunIdentity.initial_candidate_identity_sha256`.
The human can choose the requested run id, run seed, topology and source-approved
Atlas release, but cannot precompute or select accepted B13 identity.

This amendment changes only the C16.1a/C07 enrollment handshake and its recovery
surface. It does not change #950 trust-root ownership, B13 generation-zero custody,
C07 lease meaning, source-approval signatures, C07 adoption, learner execution,
optimizer ownership, or historical v1 routing.

Classification under `EGM_EXECUTION.md`: **SHARED_CONTRACT**. The affected contract
must pass fresh Design/Structural, Codebase Details and Implementation Readiness
review before production mutation resumes.

## Authority invariants

1. A caller may request Atlas enrollment but never supply accepted B13 identity.
2. A caller never receives or supplies a raw C09 registry or authoritative path.
3. The final `AtlasAdmissionLease.run_identity` is derived only from the accepted
   generation-zero bundle through the existing C07/B13 owner projection.
4. Source approval is authenticated only with the registry reached through an
   accepted-run opaque `SourceAuthorityRuntime`.
5. Generation-zero publication and C07 lease persistence remain two existing durable
   transactions. C16.1a must represent and recover the boundary between them rather
   than claiming one cross-owner atomic transaction.
6. C16.1a never renews or rotates an already accepted C07 lease. A different request
   after an accepted lease exists is a future C07 renewal operation and rejects here.
7. No create, retry, enrollment or resume path enters the learner in C16.1a.
8. `ready_for_training` remains `false` for every C16.1a lifecycle report. The
   lifecycle result may say `READY_TO_CREATE`, `CREATED`, `READY_TO_RESUME` or
   `ENROLLED`; none is authority to start training.
9. Fresh dry-run reports the exact owner-derived `BamfRunIdentity` that the same
   source/topology/seed/optimizer inputs will publish if create proceeds. A caller
   supplied tuple of run id/seed/topology is not a substitute for B13 identity.

## Non-authoritative enrollment request

Add one immutable request record in the C07 contract owner:

```python
@dataclass(frozen=True)
class AtlasAdmissionEnrollmentRequest:
    lease_id: str
    requested_run_id: str
    requested_run_seed: int
    requested_topology_digest: str
    source_approval: AtlasSourceApproval
    resource_ceiling: ResourceCeiling
    requested_at: int
    human_command_sha256: str
    admission_policy: str = field(default="atlas-release", init=False)
    schema_version: str = field(
        default="bilqis.c07.atlas-admission-enrollment-request/v1", init=False)
```

The request intentionally has **no** `LeaseRunIdentity`, initial generation digest,
origin checkpoint, accepted manifest, C09 registry, run path or source-authority
capability. It is human request data, not admission authority.

Exact shape rules:

- `lease_id` and `requested_run_id` are nonempty strings;
- `requested_run_seed` is an integer in the same accepted domain as B13 run seeds;
- `requested_topology_digest` and `human_command_sha256` are lower-case SHA-256;
- `source_approval` and `resource_ceiling` are the existing immutable C07 records;
- `requested_at` is a non-negative integer;
- schema and admission policy are exact literals;
- unknown fields, explicit nulls, malformed nested records and symlink/non-regular
  scope files reject.

`--atlas-admission-scope` remains the CLI flag for compatibility, but its fresh-v2
meaning is this enrollment request schema, not a pre-issued lease. Existing lower
level C07 tests and APIs that consume an actual `AtlasAdmissionLease` remain valid.

## Pre-generation validation

Before any target-run write, a fresh `atlas-release` create parses the enrollment
request and validates only facts already knowable before generation zero:

1. explicit human request is present;
2. request run id equals CLI run id;
3. request run seed equals CLI run seed;
4. request topology digest equals the loaded v2 topology digest;
5. request source approval's Atlas release digest equals the source-qualified Atlas
   identity resolved from `--atlas-release-manifest`;
6. resource/request scalar shape is valid.

The CLI does **not** verify the approval signature itself because that would require
raw source-registry authority. Signature/rights verification remains post-genesis in
the C07 owner after accepted C09 capability exists.

Pinned pre-write errors:

- malformed request file/shape: `BAMF_ATLAS_ENROLLMENT_REQUEST_INVALID`;
- run id mismatch: `BAMF_OPERATOR_ATLAS_REQUEST_RUN_ID_CONFLICT`;
- run seed mismatch: `BAMF_OPERATOR_ATLAS_REQUEST_RUN_SEED_CONFLICT`;
- topology mismatch: `BAMF_OPERATOR_ATLAS_REQUEST_TOPOLOGY_CONFLICT`;
- Atlas release mismatch: `BAMF_OPERATOR_ATLAS_REQUEST_MANIFEST_CONFLICT`.

All of these leave the fresh target absent.

## Exact dry-run B13 identity

C16.1a's `READY_TO_CREATE` contract includes the complete B13
`BamfRunIdentity.to_record()`, including origin checkpoint identity and
`initial_candidate_identity_sha256`. Those values cannot be reconstructed from CLI
fields alone.

Factor the owner preparation already performed inside
`preflight_bamf_foundation(...)` so dry-run and create consume the same deterministic
pre-publication constructor. The owner shape is:

```python
def preview_bamf_foundation_run_identity(
    config: BamfFoundationConfig,
    admitted_release: ExecutableFactoryRelease,
) -> BamfRunIdentity:
    ...
```

The implementation may use a private shared prepared-foundation helper, but the
semantic requirements are fixed:

1. canonicalize and authenticate the existing source run;
2. rederive Factory foundation authority from its persisted State-DAG receipt;
3. resolve source-qualified Atlas feature authority;
4. derive B01 model authority, zero AdamW state, sidecars and fixed-host C09 binding;
5. call the same `prepare_initial_generation(...)` used by create;
6. return only the resulting `candidate.run_identity`; do not create the target,
   save tensors, install a pointer, emit an accepted event, or perform an optimizer
   update.

The preview is allowed to allocate/evaluate the deterministic in-memory generation-
zero tensors required to derive exact candidate identity. `dry-run` means no durable
target mutation and no learner/optimizer step, not a promise that model preparation
allocates no arrays.

Create must use the same owner preparation logic and assert the persisted student's
`run_identity` equals the preview identity for identical inputs. A literal test runs
dry-run then create with the same source/arguments and requires exact identity
equality.

Lifecycle reports add one field:

```text
run_identity: <BamfRunIdentity.to_record()>
```

for `READY_TO_CREATE`, `CREATED` and `READY_TO_RESUME`. Existing top-level `run_id`
and `run_seed` remain convenience projections and must equal this record.

## Accepted-run enrollment owner

Add one C07-owned operation whose caller supplies only the request plus opaque
accepted-run C09 authority:

```python
def enroll_accepted_atlas_lease(
    run_dir: Path,
    request: AtlasAdmissionEnrollmentRequest,
    *,
    source_authority: SourceAuthorityRuntime,
) -> AtlasAdmissionLease:
    ...
```

The owner performs, in order, while preserving existing lock order:

1. authenticate current accepted B13 custody and derive the current
   `BamfRunIdentity` plus existing `_accepted_run_lease_identity(run_dir)`;
2. require request run id, seed and topology to equal that accepted identity;
3. authenticate `source_authority` against the accepted execution cache and obtain
   the registry only inside the C07/C09 owner;
4. call existing `issue_atlas_lease(...)` with the owner-derived
   `LeaseRunIdentity`, request approval/resource/time/command data and the internal
   accepted registry;
5. under the existing Atlas lease writer lock, converge to the exact derived lease:
   - no current reference: persist the immutable lease then the current reference;
   - exact current lease already present: return it idempotently;
   - a different current lease: reject with
     `BAMF_ATLAS_LEASE_EXPLICIT_RENEWAL_REQUIRED`;
6. authenticate readback through the same accepted B13/C09 owner before returning.

Pinned accepted-identity drift error:

- request versus accepted run identity mismatch after publication:
  `BAMF_ATLAS_ENROLLMENT_RUN_IDENTITY_DRIFT`.

The final lease remains the existing `bilqis.c07.atlas-admission-lease/v1`; no lease
schema migration is introduced.

## Fresh create state machine

### Staged create

Unchanged:

`ABSENT -> validate -> publish accepted gen0 -> CREATED(staged)`

No C07 lease exists.

### Atlas-release create

1. Parse/validate the non-authoritative enrollment request before writes.
2. Publish generation zero through existing C16.1b/B13/#950 custody.
3. Construct `AcceptedRuntimeHost(target)` and obtain opaque
   `source_authority()`.
4. Call `enroll_accepted_atlas_lease(...)`.
5. Exact authenticated lease readback succeeds -> report `CREATED` with effective
   policy `atlas-release`, `ready_for_training=false`.

No lifecycle step invokes the learner.

## Interruption and retry contract

The cross-owner boundary has three durable states and no hidden fourth state:

1. **No gen0 pointer.** Fresh create may be retried normally.
2. **Accepted gen0, no C07 current reference.** The run is lawfully `staged`.
   Enrollment may be completed by an explicit human resume-enrollment request.
3. **Accepted gen0 plus valid C07 current reference.** The effective policy is
   `atlas-release`; resume validates/readbacks that lease without caller input.

Because the existing C07 writer publishes immutable lease bytes before the current
reference, an orphan lease file without current reference is non-authoritative and
may be reused only if its exact bytes equal the owner-derived lease. It does not by
itself change effective policy.

If a write/readback exception occurs after the current reference was installed,
the operation must make one same-lock authenticated reconciliation attempt. If the
current lease is the exact owner-derived lease, the operation converges to success.
If readback remains unavailable or inconsistent, fail closed. A later resume with
no scope may authenticate the current reference if it is valid; it never silently
downgrades a present but invalid reference to staged.

## Resume and post-genesis enrollment

Normal resume with no scope remains read-only and derives effective policy only from
accepted custody.

An explicit enrollment retry is allowed only as:

```text
--human-run --resume --admission-policy atlas-release
--atlas-admission-scope <enrollment-request.json>
```

This path:

1. cold-loads accepted B13 custody first;
2. never accepts topology/run/optimizer/Atlas overrides that conflict with saved
   accepted state;
3. parses the request, validates its run id/seed/topology/Atlas release against the
   accepted state, obtains opaque C09 authority from `AcceptedRuntimeHost`, and calls
   `enroll_accepted_atlas_lease`;
4. if no current C07 lease exists, may establish the requested first lease;
5. if the exact lease already exists, converges idempotently;
6. if a different accepted lease exists, rejects as explicit renewal required.

Therefore resume scope is not a general policy override or trust-root selector. It
is a narrowly typed retry/completion surface for the first C07 enrollment after
generation-zero custody exists. `staged -> atlas-release` is permitted only through
this explicit human enrollment path. `atlas-release -> staged` remains forbidden.

## Saved-setting conflict contract

Ordinary resume with omitted values uses accepted saved settings. Explicit values
must exactly match:

- run id;
- run seed;
- topology;
- optimizer hyperparameters;
- Atlas identity;
- effective admission policy.

Literal regressions must cover both run-id mismatch and the reverse policy mismatch
where an accepted `atlas-release` run is resumed with explicit `staged`.

## Training-readiness contract

`ready_for_training` is `false` for all C16.1a reports. The lifecycle reports only
whether create/resume/enrollment validation succeeded. The later owner that actually
starts the persistent learner may introduce its own readiness signal after the C16
acceptance witness and all remaining launch gates are satisfied.

## CLI help compatibility

The parser refactor remains an implementation detail. Every pre-existing operator
argument that moved into a helper must retain its established `--help` description,
default and action semantics. In particular, retention bounds, `--human-run`,
autonomous curriculum, max visits, timing trace, source prefetch workers, flash
mode, stagnation grace and debt-admission help text may not silently disappear.
Add a parser-help regression that checks the affected option descriptions remain
present in `train --help`; do not weaken the operator documentation to match a
regressed parser.

## Required disposable first-start witness

Before human turn-in, one cohesive test must traverse the actual C16.1a command and
then compose existing production owners on the disposable accepted run. It must
prove in one witness:

1. command creates accepted generation zero and performs zero optimizer updates;
2. two differently named grade declarations use the same source-qualified Factory
   progression machinery and yield equivalent source-gold/retention behavior;
3. capability debt is symmetric and a real prerequisite hold comes from capability
   dependency, not grade label;
4. a future differently named capability/grade is held when source rights are held,
   not because the runtime assumes A/B/C;
5. an old B-only cadence field on fresh BAMF state is rejected or ignored, never
   activated;
6. a disposable rejection is recorded against the command-created accepted run and
   the current B13 manifest plus complete serialized parent state remain unchanged;
7. the same accepted run cold-loads with identical retained optimizer identity and
   the next C03 teacher visit selected from accepted custody equals uninterrupted
   selection.

The witness may use existing package-local source/teacher fixtures. It must call the
real C16.1a lifecycle and real B13/C03/C03-source-authority functions; it must not
mock the observed behavior under test or run a real learner.

## Persisted-source recovery witness

At least one happy-path dry-run/create test must not patch
`bamf_lifecycle.source_foundation`. It builds a disposable canonical source run with:

- current State-DAG receipt;
- immutable executable Factory release artifact;
- model-bundle semantic catalog + digest binding;
- exact semantic graph fingerprint.

The test points `BILQIS_STORAGE_ROOT` at that disposable source, traverses the real
`active_run_dir() -> read_current() -> executable release -> semantic catalog`
recovery path, and proves every source-run file byte is unchanged afterward.

## Implementation surface after EGM pass

Production:

- `bilqis_mlx/runtime/_admission/atlas_lease_contracts.py`
  - add immutable non-authoritative enrollment request;
- `bilqis_mlx/runtime/_admission/atlas_admission.py`
  - parse request; add accepted-run enrollment owner; retain existing lease APIs;
- `bilqis_mlx/runtime/_admission/atlas_lease_storage.py`
  - only if needed to expose exact idempotent/readback convergence without changing
    lock order or lease authority;
- `bilqis_mlx/presentation/operator_cli/bamf_lifecycle.py`
  - fresh request validation, post-genesis enrollment, resume-enrollment completion,
    exact preview identity, training-readiness false;
- `bilqis_mlx/runtime/bamf_first_student.py`
  - factor deterministic pre-publication preparation and expose exact run-identity
    preview without target mutation;
- `bilqis_mlx/presentation/operator_cli/command.py` / parser only as required for
  existing flag routing; no new trust-source flag;
- operations docs for exact request and recovery semantics.

Tests:

- request shape/round-trip and caller-no-authority tests;
- fresh staged and atlas-release create/dry-run;
- staged-gen0 -> resume enrollment completion;
- exact enrollment retry convergence;
- existing different lease -> renewal-required rejection;
- interrupted pre-current and post-current reconciliation;
- saved atlas-release -> explicit staged rejection;
- run-id mismatch;
- dry-run exact B13 identity equals subsequent create identity;
- parser-help text preserved across helper extraction;
- cohesive first-start Functional Factory/rollback/cold-resume witness;
- unmocked persisted-source recovery + byte preservation.

Regression owners retained:

- #950 C09 source-authority isolation and host-root tests;
- C07 lease storage/accepted-run binding tests;
- B13 generation-zero and rejection/cold-resume tests;
- C03/A09 grade-neutral source/teacher/prerequisite tests;
- historical v1 routing tests.

## Verification gate after implementation

Run the narrow new request/enrollment tests first, then the existing #542 owner ring.
Before turn-in require:

- focused C16.1a/C07/C09/B13/C03/A09 ring green;
- module-size and smell gates green against reviewed unified;
- governance, BAMF flow-control, error-control and contract verification green;
- `git diff --check` and changed-production `py_compile` green;
- exact `verify:leaf`, with only byte-identical inherited debt allowed;
- fresh post-implementation drift review before premerge/PR.

No real persistent learner or optimizer step is authorized by this proposal.
