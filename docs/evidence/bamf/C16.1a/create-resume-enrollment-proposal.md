# C16.1a persistent create/resume enrollment proposal

Status: DESIGN AMENDMENT / EGM-R4-PENDING
Issue: #542 / C16.1a
Reviewed unified base: `1a1bcbf3c58b0d851e40dbdee847c3fb3c00ec3a`
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

Current reviewed unified now includes #958 / PR #967's C07 **v2** human-authority
epoch. Fresh BAMF v2 enrollment therefore issues `AtlasAdmissionLeaseV2`; the v1
lease/storage path remains historical compatibility and is not reinterpreted.

This amendment changes only the C16.1a/C07 v2 enrollment handshake and its recovery
surface. It does not change #950 trust-root ownership, B13 generation-zero custody,
C07 v2 lease meaning, source-approval signatures, C07 adoption, learner execution,
optimizer ownership, or historical v1 routing.

Classification under `EGM_EXECUTION.md`: **SHARED_CONTRACT**. The affected contract
must pass fresh Design/Structural, Codebase Details and Implementation Readiness
review before production mutation resumes.

## Authority invariants

1. A caller may request Atlas enrollment but never supply accepted B13 identity.
2. A caller never receives or supplies a raw C09 registry or authoritative path.
3. The final `AtlasAdmissionLeaseV2.run_identity` is derived only from the accepted
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
10. Every fresh BAMF v2 create or dry-run, including `staged`, requires the
    source-qualified `--atlas-release-manifest`; staging omits only C07 enrollment,
    not the Atlas feature identity already bound into B13 generation-zero custody.
11. `DashboardMetrics.stage == "READY_FOR_HUMAN_START"` is a historical B13
    descriptive state, not launch authority. C16.1a MUST report
    `ready_for_training=false` alongside it, and consumers MUST treat the explicit
    lifecycle boolean as authoritative for training readiness.

## Alternatives considered

Four viable shapes were evaluated before choosing this amendment:

1. **Always create staged, then require a separate resume-enrollment command.** This
   cleanly separates B13 and C07 but removes the already-requested single-command
   fresh `atlas-release` lifecycle and adds an unnecessary operator round trip.
2. **Have dry-run derive the B13 identity and let the human construct a complete C07
   lease before create.** Rejected because caller-held accepted-run identity can go
   stale between preview and publication and would move authority construction out of
   the accepted B13/C09 owner.
3. **Let staged mode silently choose an Atlas feature identity without the manifest.**
   Rejected because B13 already binds source-qualified `AtlasArtifactIdentity`; the
   manifest is the existing auditable source for that identity on fresh commands.
4. **Chosen: non-authoritative pre-genesis enrollment request plus post-genesis
   owner-derived v2 lease.** This preserves one-command fresh `atlas-release`, keeps
   accepted-run/C09 authority inside C07 after B13 publication, and leaves `staged`
   as the same generation-zero construction without the lease transaction.

## Non-authoritative enrollment request

Add one immutable request record in the C07 contract owner:

```python
@dataclass(frozen=True)
class AtlasAdmissionEnrollmentRequestV2:
    lease_id: str
    requested_run_id: str
    requested_run_seed: int
    requested_topology_digest: str
    source_approval: AtlasSourceApproval
    resource_ceiling: ResourceCeilingV2
    requested_at: str
    human_command_sha256: str
    admission_policy: str = field(default="atlas-release", init=False)
    schema_version: str = field(
        default="bilqis.c07.atlas-admission-enrollment-request/v2", init=False)
```

The request intentionally has **no** `LeaseRunIdentity`, initial generation digest,
origin checkpoint, accepted manifest, C09 registry, run path or source-authority
capability. It is human request data, not admission authority.

The request also does not smuggle the human-run gate into persisted data. Explicit
human intent remains a live operator-boundary fact. The C16.1a caller passes that
fact separately to the C07 enrollment owner, and C07 preserves the current
`issue_atlas_lease_v2(..., human_started=...)` requirement exactly.

Exact shape rules:

- `lease_id` and `requested_run_id` are nonempty strings;
- `requested_run_seed` is an integer in the same accepted domain as B13 run seeds;
- `requested_topology_digest` and `human_command_sha256` are lower-case SHA-256;
- `source_approval` is the existing immutable C07 source approval and
  `resource_ceiling` is exactly `ResourceCeilingV2`;
- `requested_at` is a nonempty string exactly as required by
  `AtlasAdmissionLeaseV2`;
- schema and admission policy are exact literals;
- unknown fields, explicit nulls, malformed nested records and symlink/non-regular
  scope files reject.

The request reader owns one public parse failure surface. Any JSON, schema, unknown
field, explicit-null, or nested `AtlasSourceApproval` / `ResourceCeilingV2`
construction failure is normalized to
`BAMF_ATLAS_ENROLLMENT_REQUEST_INVALID`. This normalization applies only while
deserializing the caller request. Post-genesis signature, rights, accepted-run and
source-authority validation keeps the existing C07/C09 owner errors rather than
being collapsed into the parse error.

`--atlas-admission-scope` remains the CLI flag for compatibility, but its fresh-v2
meaning is this enrollment request schema, not a pre-issued lease. Existing lower
level C07 v1 tests and APIs remain valid historical compatibility; fresh BAMF v2
create/resume uses only the separate v2 lease epoch.

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
    new_run_dir: Path,
) -> BamfRunIdentity:
    ...
```

The implementation may use a private shared prepared-foundation helper, but the
semantic requirements are fixed:

1. canonicalize source and target paths with the same
   `_canonical_disjoint_run_paths(...)` owner guard used by create, so dry-run
   rejects source-overlapping targets exactly as create does;
2. canonicalize and authenticate the existing source run;
3. rederive Factory foundation authority from its persisted State-DAG receipt;
4. resolve source-qualified Atlas feature authority;
5. derive B01 model authority, zero AdamW state, sidecars and fixed-host C09 binding;
6. call the same `prepare_initial_generation(...)` used by create;
7. return only the resulting `candidate.run_identity`; do not create the target,
   save tensors, install a pointer, emit an accepted event, or perform an optimizer
   update.

The preview is allowed to allocate/evaluate the deterministic in-memory generation-
zero tensors required to derive exact candidate identity. `dry-run` means no durable
target mutation and no learner/optimizer step, not a promise that model preparation
allocates no arrays.

Dry-run materializes the same typed `AdamWHyperparameters` used by create before it
constructs `BamfFoundationConfig`; the historical dictionary-only validation helper
is not the input to this owner preview.

Create must use the same owner preparation logic and assert the persisted student's
`run_identity` equals the preview identity for identical inputs. A literal test runs
dry-run then create with the same source/arguments and requires exact identity
equality.

Lifecycle reports add one field:

```text
run_identity: <BamfRunIdentity.to_record()>
```

for `READY_TO_CREATE`, `CREATED`, `READY_TO_RESUME` and `ENROLLED`. Existing top-level `run_id`
and `run_seed` remain convenience projections and must equal this record.

## Accepted-run enrollment owner

Add one C07-owned operation whose caller supplies only the request plus opaque
accepted-run C09 authority:

```python
def enroll_accepted_atlas_lease_v2(
    run_dir: Path,
    request: AtlasAdmissionEnrollmentRequestV2,
    *,
    human_started: bool,
    source_authority: SourceAuthorityRuntime,
) -> AtlasAdmissionLeaseV2:
    ...
```

The owner performs, in order, while preserving existing lock order:

1. require `human_started is True`; this value is supplied directly from the live
   `--human-run` operator invocation and is not inferred from request-file presence;
2. authenticate current accepted B13 custody and derive the current
   `BamfRunIdentity` plus existing `_accepted_run_lease_identity(run_dir)`;
3. require request run id, seed and topology to equal that accepted identity;
4. authenticate `source_authority` against the accepted execution cache and obtain
   the registry only inside the C07/C09 owner;
5. call existing `issue_atlas_lease_v2(...)` with the owner-derived
   `LeaseRunIdentity`, request approval/resource/time/command data and the internal
   accepted registry, passing the same explicit `human_started=True` proof rather
   than weakening or deleting that gate;
6. under the existing Atlas lease writer lock, converge to the exact derived lease:
   - no current reference: persist the immutable lease then the current reference;
   - exact current lease already present: return it idempotently;
   - a different current lease: reject with
     `BAMF_ATLAS_LEASE_V2_EXPLICIT_RENEWAL_REQUIRED`;
7. authenticate readback through the same accepted B13/C09 owner before returning.

The enrollment operation lives in a new cohesive
`bilqis_mlx/runtime/_admission/atlas_enrollment_v2.py` owner module. Request parsing,
accepted-run identity comparison and lease issuance live there rather than growing
the already-large `atlas_admission.py`; durable v2 lease/orphan/reference/readback
and reconciliation mechanics remain exclusively in `atlas_lease_storage_v2.py`.
The established public import surface may
re-export the new owner symbols. `atlas_admission.py` retains the existing frontier,
lease-read and compatibility responsibilities and must not cross the repository's
large-module trigger as a consequence of this amendment.

Pinned accepted-identity drift error:

- request versus accepted run identity mismatch after publication:
  `BAMF_ATLAS_V2_ENROLLMENT_RUN_IDENTITY_DRIFT`.
- accepted B13 feature receipt versus accepted `BamfRunIdentity.initial_release_digest`:
  `BAMF_ATLAS_V2_ACCEPTED_ATLAS_CUSTODY_DRIFT`;
- request source-approval Atlas release versus the accepted B13 Atlas identity:
  `BAMF_ATLAS_V2_ENROLLMENT_ATLAS_RELEASE_DRIFT`.

Error precedence is fixed: accepted B13/Atlas custody is authenticated first;
`BAMF_ATLAS_V2_ACCEPTED_ATLAS_CUSTODY_DRIFT` therefore wins over any request-vs-
accepted mismatch. Only after custody is internally coherent may the request produce
`BAMF_ATLAS_V2_ENROLLMENT_ATLAS_RELEASE_DRIFT`.

The final lease is the reviewed-unified `bilqis.c07.atlas-admission-lease/v2`.
Historical v1 lease semantics and current reference remain untouched; v2 uses its
separate `autonomy/atlas-admission/v2/` custody epoch.

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
4. Call `enroll_accepted_atlas_lease_v2(...)`.
5. Exact authenticated lease readback succeeds -> report `CREATED` with effective
   policy `atlas-release`, `ready_for_training=false`.

No lifecycle step invokes the learner.

## Interruption and retry contract

The cross-owner boundary has four durable states:

1. **No generation-zero artifacts.** Fresh create may begin normally.
2. **Exact sealed generation-zero artifacts, no pointer.** This is an interrupted
   B13 publication, not an ordinary empty target. Recovery has two owner-governed
   cases. If the source Factory is still at the exact original authority, C16.1a may
   reconstruct the same prepared candidate and use existing B13 exact retry. If the
   source Factory has advanced, C16.1a MUST NOT replay current source authority to
   manufacture the old preparation. Instead it invokes a new B13 cold-recovery owner
   that authenticates the already sealed generation-zero bundle, C09 trust seal and
   any persisted acceptance sidecar directly from the target. When exact persisted
   acceptance exists, that owner may install the missing pointer and reconcile the
   outbox without consulting mutable source state. The trust row already commits the
   acceptance digest, so a missing acceptance sidecar may be reconstructed only as
   the exact historical parsed binding record derived from the sealed student and
   checked against that trust-row digest; this never restores or fabricates a live
   `InitialGenerationBinding`. A conflicting or ambiguous B13 artifact rejects. If
   no exact recoverable B13 genesis exists, any other nonempty target remains
   `BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED`. A fresh create never treats an
   arbitrary occupied directory as writable merely because `bamf-state.json` is
   absent.
3. **Accepted gen0 pointer, no C07 current reference.** The run is lawfully
   `staged`. Enrollment may be completed by an explicit human resume-enrollment
   request.
4. **Accepted gen0 plus valid C07 current reference.** The effective policy is
   `atlas-release`; resume validates/readbacks that lease without caller input.

`bamf_first_student` therefore factors deterministic preparation from target-state
handling. The fresh path still requires an empty/absent target. The interrupted
genesis path is admitted only through B13's authenticated exact-retry/cold-recovery
owners; it does not require mutable-source replay when sufficient sealed historical
evidence already exists. A target with an already installed
generation-zero pointer is not a fresh create; the operator must use resume.

The B13 recovery owners are explicit:

```python
def recover_prepared_initial_generation(
    run_dir: Path,
    prepared: PreparedInitialGeneration,
) -> dict | None:
    ...

def recover_sealed_initial_generation(
    run_dir: Path,
    *,
    expected_run_id: str,
    expected_run_seed: int,
    expected_topology_digest: str,
    expected_atlas_artifact: AtlasArtifactIdentity,
    expected_optimizer_hyperparameters_sha256: str,
) -> dict | None:
    ...
```

`recover_prepared_initial_generation` preserves the existing in-memory retry
semantics and may complete an exact missing acceptance sidecar, pointer and outbox as
the current B13 helper already does. `recover_sealed_initial_generation` is the cold
process path and MUST run under B13's existing pointer lock before any mutable-source
Factory replay. It:

1. requires no current pointer and authenticates the stored genesis-trust row,
   including generation, payload hash, manifest digest and acceptance digest;
2. loads exactly the trust-row manifest-bound bundle and compares caller run id,
   seed, topology, Atlas-artifact and optimizer-hyperparameter digest inputs only as
   equality expectations; optimizer mismatch rejects before any sidecar, pointer or
   outbox mutation;
3. runs the existing narrow host/C09 `validate_initial_generation_source_authority`
   check, but never `validate_initial_generation_preparation` or
   `replay_initial_factory_foundation_authority`;
4. reconstructs the **historical binding record** from the sealed student's
   run-identity digest,
   `initial_generation_candidate_identity_digest(student)`,
   `optimizer_hyperparameters_digest(student.optimizer_hyperparameters)`,
   factor-map digest and optimizer step zero; the generic retained-state
   `candidate_identity_digest(...)` is explicitly not valid for this binding field.
   Require the reconstructed binding digest to equal the trust row's
   `acceptance_sha256`, then parse it as historical
   `ParsedInitialGenerationBinding`;
5. builds the recovery pointer solely from trusted bundle/trust values and requires
   `require_initial_generation_trust_root(pointer, student, parsed_binding)` before
   mutation;
6. if the acceptance sidecar is absent, writes exactly the reconstructed canonical
   historical binding through the B13 storage-owner API below; if it exists, requires
   exact bytes; then re-runs `require_published_acceptance`;
7. only after those checks installs the pointer and reconciles the outbox.

This cold path never creates a bundle or trust seal, never creates a live binding,
and never replays current Factory state. Zero or multiple plausible sealed candidates
return `None` or reject as occupied/ambiguous respectively; any mismatch raises the
existing B13 trust/identity/acceptance errors. C16.1a first attempts this
source-independent cold recovery for a nonempty no-pointer target, then may use
prepared retry only when the current source can lawfully reconstruct the exact
original preparation. It never falls through from an occupied target into normal
fresh publication.

The historical-acceptance storage API is pinned and deliberately narrow:

```python
def _write_parsed_initial_generation_acceptance(
    run_dir: Path,
    manifest_sha256: str,
    binding: ParsedInitialGenerationBinding,
    *,
    expected_acceptance_sha256: str,
) -> None:
    ...
```

Owner: `bilqis_mlx/runtime/_custody/bamf_bundle/publication/storage.py`.
The helper accepts only the already-validated historical parsed binding, serializes
exactly `binding.fields`, requires `binding.digest == expected_acceptance_sha256`
before opening a write path, and then reuses the existing `_acceptance_path`,
symlink checks, canonical bytes, exact-byte idempotency, temporary-file + `fsync`,
atomic `os.replace`, and directory-`fsync` semantics of `_write_acceptance`. It must
not accept arbitrary mappings/bytes, call a minting API, add `.to_record()` to
`ParsedInitialGenerationBinding`, or duplicate the durability algorithm in retry
code. `_write_acceptance(...)` may be refactored to delegate to one shared private
canonical-byte primitive, but live-authority and historical-evidence entrypoints
remain type-distinct.

Because the existing C07 writer publishes immutable lease bytes before the current
reference, an orphan lease file without current reference is non-authoritative. The
storage owner must compare the existing file bytes with the exact canonical bytes
that `_durable_json` would write for `asdict(owner_derived_lease)`; typed-object
equality after reparsing is insufficient for this recovery rule. An exact-byte
orphan may be reused. A formatting-different or otherwise byte-different orphan
rejects as immutable drift and does not change effective policy. This makes
`atlas_lease_storage_v2.py` an explicit implementation surface for C16.1a. The v1
storage path is unchanged.

`atlas_lease_storage_v2.py` owns the entire same-lock convergence primitive. The
enrollment owner calls one storage operation and never catches/reimplements
reference/readback reconciliation outside that lock. After the current-reference
write succeeds, the storage owner performs its normal authenticated readback. Only
failures from that post-reference readback stage are
reconcilable. Unsafe path, immutable drift, different-current-lease/renewal,
accepted-run identity, source-authority, signature and rights failures are never
swallowed or converted into reconciliation.

For a post-reference read failure or readback mismatch, while retaining the same
writer lock, perform exactly one reconciliation read: validate the canonical
`current.json` reference fields/digest, require it to name the owner-derived lease,
require the lease file's exact canonical bytes, parse/verify the lease through the
same accepted registry, and require typed equality with the owner-derived lease. If
all checks pass, converge to success. Otherwise raise
`BAMF_ATLAS_LEASE_V2_RECONCILIATION_FAILED` and preserve the durable evidence for a
later cold retry. A later resume with no scope may authenticate a valid current
reference; it never silently downgrades a present but invalid reference to staged.

## Resume and post-genesis enrollment

Normal resume with no scope remains read-only and derives effective policy only from
accepted custody.

The parser keeps the historical `--admission-policy` default of `staged`, but the
operator boundary also preserves the existing `admission_policy_explicit` presence
bit derived from raw argv. Resume inheritance is based on that presence bit, not on
the parsed default value: omitted policy inherits accepted custody, while an
explicit `--admission-policy staged` against an accepted `atlas-release` run is a
conflicting override and rejects.

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
   `enroll_accepted_atlas_lease_v2(..., human_started=args.human_run, ...)`;
4. if no current C07 lease exists, may establish the requested first lease;
5. if the exact lease already exists, converges idempotently;
6. if a different accepted lease exists, rejects as explicit renewal required.

Therefore resume scope is not a general policy override or trust-root selector. It
is a narrowly typed retry/completion surface for the first C07 enrollment after
generation-zero custody exists. `staged -> atlas-release` is permitted only through
this explicit human enrollment path. `atlas-release -> staged` remains forbidden.

The accepted Atlas identity used for resume and enrollment comparison is the
authenticated B13 feature receipt (`read_accepted_generation_feature_receipt`) that
reconstructs `AtlasArtifactIdentity`. The owner also requires its
`source_release_sha256` to equal `BamfRunIdentity.initial_release_digest`; divergence
is accepted-custody drift and rejects before request comparison. CLI input is never
the source of saved Atlas identity.

Successful explicit resume-enrollment returns lifecycle result `ENROLLED`. Its
report has the same complete `run_identity`, generation manifest, topology, Atlas
identity, optimizer hyperparameters and convenience run id/seed projections as
`READY_TO_RESUME`, with `admission_policy="atlas-release"`,
`ready_for_training=false`, and `neural_updates=0`. Normal resume without enrollment
continues to return `READY_TO_RESUME`.

Historical v1 accepted runs remain readable but never acquire an implicit v2 lease.
Resume classification is epoch-aware:

- v2 current reference present, v1 absent -> current v2 `atlas-release` behavior;
- v1 current reference present, v2 absent -> historical v1 `atlas-release` resume is
  read-only compatible and may not use the v2 first-enrollment scope;
- neither reference -> `staged`;
- both v1 and v2 references -> reject `BAMF_ATLAS_AUTHORITY_EPOCH_CONFLICT`.

An explicit v2 first-enrollment request against a run that already has accepted v1
authority rejects `BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT`. C16.1a performs no
automatic migration or coexistence. A future explicit migration owner may define
that transition separately.

This epoch guard is owned by `atlas_enrollment_v2.py`, not only by the CLI. Before
`issue_atlas_lease_v2(...)` or any v2 storage mutation, the public
`enroll_accepted_atlas_lease_v2(...)` owner itself inspects the canonical v1 current
reference path. A symlink/unsafe v1 path retains the v1 storage error; an existing
regular v1 current reference rejects `BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT`.
Likewise, the lifecycle epoch classifier checks both v1 and v2 current references;
both present rejects `BAMF_ATLAS_AUTHORITY_EPOCH_CONFLICT`. Existing low-level C07
v2 fixture/storage tests may continue proving the two storage epochs are physically
separate; C16.1a's owner-level admission contract is the layer that forbids their
simultaneous authority on one accepted BAMF run.

## CLI mode matrix and dispatch ownership

The shared C11/C16 operator contract is exact:

| Mode | Required policy/scope behavior | Mutation |
| --- | --- | --- |
| fresh staged dry-run | `--atlas-release-manifest ...`; policy omitted or explicit `staged`; scope forbidden | none |
| fresh atlas-release dry-run | `--human-run --admission-policy atlas-release --atlas-release-manifest ... --atlas-admission-scope <enrollment-request.json>` | none |
| fresh staged create | `--human-run --atlas-release-manifest ...`; scope forbidden | generation-zero only |
| fresh atlas-release create | `--human-run --admission-policy atlas-release --atlas-release-manifest ... --atlas-admission-scope <enrollment-request.json>` | generation-zero, then first C07 enrollment |
| normal BAMF resume | scope omitted; omitted settings inherit saved custody; explicit settings must match | none in C16.1a |
| first post-genesis enrollment | `--human-run --resume --admission-policy atlas-release --atlas-admission-scope <enrollment-request.json>` | first C07 enrollment only |

Every fresh v2 dry-run/create requires `--atlas-release-manifest` because B13
generation-zero identity always contains the source-qualified Atlas artifact. An
`atlas-release` fresh dry-run additionally requires and validates the enrollment
request even though it does not persist a lease; this is what allows the dry-run to
prove the same request/run/topology/Atlas-release compatibility that create will
consume. A scope with `staged` is always invalid. A fresh `atlas-release` create or
dry-run without scope is always invalid. Normal resume never requires a scope.

Dispatch is pinned before implementation:

1. a fresh command with an explicit `ModelTopologySpecV2` is owned by
   `bamf_lifecycle`;
2. `--resume` against a run directory with `bamf-state.json` is owned by
   `bamf_lifecycle` even when `--model-topology` is omitted, because accepted B13
   custody supplies the saved topology;
3. an interrupted generation-zero publication with no pointer is retried by
   repeating the fresh v2 create command with the same topology/source/seed/Atlas
   manifest **and optimizer** inputs; target-state handling attempts
   source-independent sealed B13 cold recovery before any mutable-source
   reconstruction and never enters the historical learner-resume path;
4. commands with neither a v2 topology nor an accepted BAMF pointer retain the
   historical v1 routing;
5. when `bamf_lifecycle` owns the command, `command._main` returns its lifecycle
   result before `_invoke_learner` can run. `--human-run --resume` does not by itself
   authorize learner entry for a BAMF v2 run in C16.1a.

Presentation target classification is also pinned. The existing `fresh_target()`
helper is split into two responsibilities:

```python
def canonical_target(path: Path) -> Path:
    """Reject symlink/non-directory unsafe shape, but do not reject nonempty dirs."""
    ...

def require_empty_fresh_target(path: Path) -> Path:
    """Historical/fresh-only helper: canonical_target + empty-directory requirement."""
    ...
```

`bamf_lifecycle` uses `canonical_target()` for BAMF v2 create/dry-run routing. For
dry-run, normal empty-target validation still applies because no recovery mutation is
needed. For actual create, an empty target proceeds to ordinary B13 preparation;
a nonempty target with no accepted pointer is passed to the B13 recovery-aware owner,
which alone may classify it as exact sealed interrupted genesis versus arbitrary
occupied state. A nonempty target with an accepted pointer is not create and directs
the operator to resume. Historical v1 callers retain `require_empty_fresh_target()`.
No presentation helper is allowed to decide that arbitrary nonempty content is a
recoverable B13 generation.

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

The existing B13 dashboard value `READY_FOR_HUMAN_START` is retained for historical
schema compatibility and means only: generation zero is accepted and awaits a later
human-controlled boundary. It is explicitly **non-authorizing** and is not a synonym
for `ready_for_training`. A cross-consumer regression must assert that every C16.1a
report carrying a dashboard projection with `stage="READY_FOR_HUMAN_START"` still
has `ready_for_training is False` and cannot reach `_invoke_learner`.

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
real C16.1a lifecycle and real B13/C03/C09-source-authority functions; it must not
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

Production, with required file action:

- **Modify** `bilqis_mlx/runtime/_admission/atlas_lease_contracts.py`
  - add immutable non-authoritative enrollment request;
- **Create** `bilqis_mlx/runtime/_admission/atlas_enrollment_v2.py`
  - own enrollment-request parsing, accepted-run first enrollment, explicit
    human-start propagation, accepted-run/Atlas comparison, v1-authority exclusion
    and issuance; no storage reconciliation logic;
- **Modify** `bilqis_mlx/runtime/_admission/atlas_admission.py`
  - retain existing frontier/lease compatibility responsibilities and re-export the
    bounded enrollment owner without absorbing its implementation;
- **Modify** `bilqis_mlx/runtime/_admission/atlas_lease_storage_v2.py`
  - required: exact `_durable_json` byte comparison for orphan reuse plus bounded
    same-lock post-reference reconciliation as the sole reconciliation owner without
    changing lock order or lease authority;
- **Modify** `bilqis_mlx/presentation/operator_cli/bamf_lifecycle.py`
  - fresh request validation, post-genesis enrollment, resume-enrollment completion,
    exact preview identity, training-readiness false, and recovery-aware nonempty
    target routing before mutable-source reconstruction;
- **Modify** `bilqis_mlx/presentation/operator_cli/bamf_lifecycle_inputs.py`
  - split unsafe-path canonicalization from empty-target enforcement so BAMF v2 can
    route a nonempty/no-pointer target to B13 while historical fresh-only callers
    retain occupied-target rejection;
- **Modify** `bilqis_mlx/runtime/bamf_first_student.py`
  - factor deterministic pre-publication preparation and expose exact run-identity
    preview with source/target disjointness, plus recovery-aware fresh target handling;
- **Modify** `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/__init__.py` and
  **Modify** `bilqis_mlx/runtime/_custody/bamf_bundle/publication/retry.py`
  - expose prepared retry plus source-independent cold recovery for an exact sealed
    unpointed generation zero; reconstruct a missing historical acceptance record
    only from trust-row digest + sealed student, using
    `initial_generation_candidate_identity_digest(student)` and exact optimizer
    digest equality, never from current Factory replay;
- **Modify** `bilqis_mlx/runtime/_custody/bamf_bundle/publication/storage.py`
  - add `_write_parsed_initial_generation_acceptance(...)` as the only historical
    acceptance-sidecar write path, reusing existing canonical/atomic/fsync semantics;
- **Modify** `bilqis_mlx/presentation/operator_cli/command.py` and **Modify**
  `bilqis_mlx/presentation/operator_cli/parser.py` only as required for
  the pinned v2 dispatch/presence-bit routing; no new trust-source flag and no change
  to historical `--admission-policy` default/action semantics;
- **Modify** `docs/tasks/bamf-0.2/children/C11.1.md` and **Modify**
  `docs/architecture/BAMF_0_2.md`
  - align the affected shared operator command contract with the exact scope matrix.

Tests:

- **Modify** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_create_resume.py`;
- **Modify** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_atlas_release_create.py`;
- **Modify** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_resume_admission_policy.py`;
- **Modify** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_preflight.py`;
- **Modify** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_first_start_neutrality.py`;
- **Modify** `bilqis_mlx/runtime/tests/admission/atlas/test_atlas_lease_v2.py`;
- **Modify**
  `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_retry.py`;
- **Modify**
  `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_cold_trust.py`;
- **Modify**
  `bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication_recovery.py`.

Those files own the following required regressions; new test files are not required
unless implementation decomposition makes a new production owner otherwise lack a
mirrored test owner:

- request shape/round-trip and caller-no-authority tests;
- fresh staged and atlas-release create/dry-run;
- staged-gen0 -> resume enrollment completion;
- exact enrollment retry convergence;
- existing different lease -> renewal-required rejection;
- interrupted pre-current and post-current reconciliation;
- accepted Atlas custody drift and request-vs-accepted Atlas mismatch with literal
  pinned error precedence;
- v1 historical accepted-run resume, v1+v2 epoch conflict, and rejection of v2 first
  enrollment on a v1-authorized run;
- B13 cold unpointed recovery after source advance both with persisted acceptance and
  with a missing sidecar reconstructed exactly from trust-row + sealed student;
- interrupted cold recovery with an explicitly changed AdamW setting rejects before
  acceptance/pointer/outbox mutation;
- command-level nonempty/no-pointer interrupted create reaches B13 recovery, while an
  arbitrary occupied target still rejects;
- saved atlas-release -> explicit staged rejection;
- run-id mismatch;
- dry-run exact B13 identity equals subsequent create identity;
- parser-help text preserved across helper extraction;
- cohesive first-start Functional Factory/rollback/cold-resume witness;
- dashboard `READY_FOR_HUMAN_START` remains non-authorizing while lifecycle
  `ready_for_training` is false and learner dispatch is unreachable;
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
