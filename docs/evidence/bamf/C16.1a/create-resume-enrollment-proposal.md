# C16.1a persistent create/resume enrollment proposal

Status: DESIGN AMENDMENT / EGM-R12-PENDING
Issue: #542 / C16.1a
Reviewed unified base: `905018b0ece7613843570dc2c2e72a74dae4e91d`
Historical implementation candidate preserved for evidence: `291f7a39cc6f083c222fff604e8a3d95ab98e497`
Pinned EGM: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`

R5 review record: the frozen R5 proposal at `703b913c2dc6ff7e86b38f62e55dc9712f33563c`
failed fresh independent review against reviewed unified
`905018b0ece7613843570dc2c2e72a74dae4e91d`: Structural **0 Blockers / 2 Majors /
0 Nits**; Codebase Details **1 Blocker / 1 Major / 0 Nits**; Implementation
Readiness **0 Blockers / 3 Majors / 4 Nits**. R6 repairs that complete material set.
The later local implementation commits remain preserved historical evidence only and
do not authorize implementation before R6 itself clears a fresh `0 Blockers / 0
Majors` gate.

R6 review record: the frozen R6 proposal at
`de0bfa0355b2960088f95a12d9a94a39bf6662a9` / SHA-256
`82a24fd765aa20f036668db911c3b9d867f57cecc621a766fdc353c41c030763` received
Structural **0 Blockers / 1 Major / 0 Nits**, Codebase Details **0 Blockers / 0
Majors / 0 Nits**, and Implementation Readiness **0 Blockers / 0 Majors / 0 Nits**.
The sole material R6 finding was that low-level v1/v2 fixture writers were not
mechanically excluded from accepted B13 custody and could bypass the proposed shared
accepted-run epoch invariant. R7 repairs that localized bypass without introducing a
new accepted-run renewal surface. Production mutation remains forbidden until this
R7 revision is frozen and freshly clears `0 Blockers / 0 Majors` review.

Late R6 readiness correction: a second independent readiness lens returned **0
Blockers / 3 Majors / 2 Nits** after R7 had already been frozen. Those findings remain
authoritative historical review evidence rather than being discarded. R7 repaired the
shared low-level v1/v2 fixture-writer backdoor, but did not yet freeze three additional
operator/proof details: raw v2-intent interception when topology is omitted, one
top-level fresh validation precedence, and disposable Data Plane isolation for the
persisted-source witness. It also left ambiguous whether creation of the shared epoch
lock counted as mutation during validation-only rejection. R8 repairs that remaining
set. Production mutation remains forbidden.

R7 review record: the frozen R7 proposal at
`8c616abce9da33674cb5958ee4ae4b2c21f5e558` / SHA-256
`d973348c893739fdd811a6dd2e0a630d9c0c9c30313f68f63a36ad662b394593` received
Structural **0 Blockers / 1 Major / 0 Nits**, Codebase Details **0 Blockers / 0
Majors / 0 Nits**, and Implementation Readiness **0 Blockers / 0 Majors / 0 Nits**.
The sole fresh R7 Major was a pre-marker TOCTOU race: generic fixture mutation could
pass the custody-marker guard after B13's last empty-root check but before B13 created
its first recognized custody marker. R8 therefore serializes the root claim itself,
not merely the marker check. This result also independently confirms the late R6
readiness concerns must remain repaired in R8 even though the fresh R7 readiness lens
did not rediscover them.

R8 review correction: the frozen R8 proposal at
`c8b655a1dfc910fae6edd038d7795fed7e5d6407` / SHA-256
`8a9b6578da356b44bd98a22aad8b488a001a293cb315d686f7b2aa76f2d0cf30` passed
Implementation Readiness at **0 Blockers / 0 Majors / 0 Nits**. Structural returned
**0 Blockers / 1 Major / 0 Nits**; Codebase Details returned **0 Blockers / 2 Majors /
0 Nits**. Both independent lenses found the same filesystem-identity defect: R8 keyed
the root claim and path disjointness by resolved path text, which is not unique on the
actual case-insensitive macOS host. Codebase Details additionally found that exact raw
token scans for explicitness miss argparse-accepted long-option abbreviations. R9
removes target-path-text identity from locking/disjointness and makes option
explicitness parser-owned, while preserving historical abbreviation behavior.

R9 review record: the frozen R9 proposal at
`7908ac1e80f711b3dca44ea6dc3c2ff6c1ae2581` / SHA-256
`43c4a21f62bea85e027c780b2595dc193f942bb1fb70c5ee26727302d6aa2d11`
received Design/Structural **0 Blockers / 1 Major / 0 Nits**, Codebase Details
**0 Blockers / 1 Major / 0 Nits**, and Implementation Readiness **0 Blockers / 3
Majors / 1 Nit**. The material set is: the fixed
`.bamf-root-claim.lock` child name can collide with a legal run-directory name;
the design did not pin the shared claim helper's failure surface; the regression
contract incorrectly demanded a shorter argparse abbreviation for both
`--adam-beta1` and `--adam-beta2`, which have no shorter unambiguous spelling; and
sealed-genesis ambiguity did not have a literal error/precedence contract. The
Codebase Details lens additionally proved that creating a new direct module under
`bilqis_mlx/runtime/` would make that directory hit the repository's mandatory
`>=18` direct-code-file structural interruption threshold. The readiness Nit also
exposed misleading historical `--human-run` help text now that
C16.1a uses the flag for neural-inert create/enrollment mutation. R10 repairs the
complete known material set by using a namespace-free physical-parent directory
flock, pinning claim/recovery failures and precedence, making abbreviation coverage
conditional on an abbreviation actually existing, placing the neutral claim owner
in a small dedicated `runtime/_coordination/` package rather than the crowded
runtime root, and pinning truthful `--human-run` help semantics. Production
mutation remains forbidden until R10
freshly clears **0 Blockers / 0 Majors** across the required affected-scope lenses.

R10 review record: the frozen R10 proposal at
`5689e0fdfa0f219c818ea1039d1070e3b9152647` / SHA-256
`273056ae8319cbe4aabcfa37e5e017ee1b9e328b920e843415cef6453b5dbf53`
received Design/Structural **0 Blockers / 1 Major / 0 Nits**, Codebase Details
**0 Blockers / 2 Majors / 0 Nits**, and Implementation Readiness **0 Blockers / 4
Majors / 0 Nits**. The material union is five seams: interrupted no-pointer
`--resume` was allowed to enter a recovery classification whose only concrete owner
could mutate custody even though the command contract says resume must reject; the new
coordination owner lacked a mirrored package-local unit test; the proposed
multi-candidate cold-recovery ambiguity cannot exist under the reviewed Data Plane's
one immutable genesis-trust row per run id; the shared claim API did not pin
acquire/body/release precedence or post-mutation release failure; and explicit
resume-enrollment had competing validation-order descriptions. R11 removes the
invented multi-candidate state, makes interrupted no-pointer resume a read-only
marker-level rejection, pins one ten-step enrollment order, specifies the exact
namespace-free directory-fd claim API and release semantics, and adds the package-local
coordination test owner. Production mutation remains forbidden until R11 freshly
clears **0 Blockers / 0 Majors** across all three required lenses.

R11 review record: the frozen R11 proposal at
`8e934ad128a4097d771eeb4f8ffbf35414390468` / SHA-256
`e884f5c8557e4a3bb9a6ce1905f39376921365f2c04d3aad5659d2436dbcc666`
received Design/Structural **0 Blockers / 1 Major / 0 Nits**, Codebase Details
**0 Blockers / 2 Majors / 0 Nits**, and Implementation Readiness **0 Blockers / 3
Majors / 0 Nits**. The material union is six seams. Design found that the
read-only interrupted-resume marker set omitted B13's durable `.bamf-staging`
pre-pointer residue. Codebase found that fully specified exact-identity dry-run
necessarily crosses the MLX-backed B13 preparation path while the reviewed base also
has an early-invalid no-MLX inspection regression, and that the new root-claim tests
did not exercise either `create_parent` branch or the promised fsync durability.
Readiness found ambiguous enrollment/lock ownership, an under-specified
body-error-plus-release-error representation, and missing within-step precedence for
mixed resume/enrollment mismatches. R12 repairs all six while preserving the complete
R5-R11 safety contract. Production mutation remains forbidden until R12 freshly clears
**0 Blockers / 0 Majors** across all three required lenses.

R12 review record: the frozen R12 proposal at
`97c9e15f8ecb94315cd1066581de854496bccb8d` / SHA-256
`7006ce2962fc20e180900a66b4bc568b996fd8a72aa1665ebe1773792d4fff34`
received Design/Structural **0 Blockers / 1 Major / 0 Nits**, Codebase Details
**1 Blocker / 0 Majors / 0 Nits**, and Implementation Readiness **0 Blockers / 1
Major / 0 Nits**. The material union is three seams. Design found that the claimed
stage-root-only pre-seal residue contradicts the real B13 owner order because
`_pointer_lock` persistently creates `.bamf-pointer.lock` before `_stage()`. Codebase
found that `.bamf-staging/` was not crash-durable at the point R12 relied on it as the
sole BAMF-v2 pre-pointer marker because `_stage()` did not fsync the run root and
stage-child cleanup did not fsync the staging parent. Readiness found that the promised
C07 epoch-before-C09 error precedence was impossible with the frozen call order because
`AcceptedRuntimeHost` provisions/validates C09 authority before the enrollment owner
could run its epoch classifier. R13 repairs all three: it pins the exact safe
`.bamf-pointer.lock` + empty `.bamf-staging/` residue produced by the real B13 owner
sequence, makes staging-root creation and retained-root child cleanup explicitly
durable, and exposes one C07-owned read-only epoch precheck that must run before
`AcceptedRuntimeHost` construction and is reused under the shared epoch lock. Production
mutation remains forbidden until R13 freshly clears **0 Blockers / 0 Majors** across
all three required lenses.

R13 did **not** clear the gate. Before the replacement independent reviewers could
complete, local reconciliation found one internal ordering contradiction in the frozen
R13 text: the accepted-run contract required the C07 read-only epoch precheck before
any `AcceptedRuntimeHost` / C09 capability construction, and explicit resume-enrollment
followed that order, but the atlas-release **fresh-create** subsection still said to
construct `AcceptedRuntimeHost` immediately after generation-zero publication and only
then call enrollment. That would reintroduce the same C09-before-C07 precedence seam on
the fresh-create route. Several revived reviewer chats also lost their prior isolated
worktree allocation (`WORKTREE_OWNER_UNAVAILABLE` / browser handoff failure), so no
substantive R13 pass is inferred from incomplete reviews. R14 repairs the fresh-create
ordering explicitly: after accepted generation-zero publication it runs the same
C07-owned read-only epoch precheck, then constructs the C09 host, then enters accepted
enrollment; the mandatory under-lock epoch recheck remains unchanged. Production
mutation remains forbidden until R14 freshly clears **0 Blockers / 0 Majors** across
all three required lenses.

## Why this amendment exists

C16.1a owns the human create/dry-run/resume surface. The staged launch path consumes
C16.1b/#543 generation-zero B13 custody directly; C16.1c/#950 is additionally
required only for the `atlas-release` enrollment path that consumes accepted C09
source authority. The first implementation
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
human intent remains a live operator-boundary fact only when an operation may issue
or persist authority. Read-only dry-run may parse and validate this request without
asserting `--human-run`. Actual create and resume-enrollment pass the live operator
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

### Canonical foundation-input contract

R6 freezes the previously missing operator source for every mandatory
`BamfFoundationConfig` field. The production `train` parser owns these BAMF-v2
foundation arguments:

```text
--run-id <nonempty-string>
--run-seed <integer >= 0>
--learning-rate <finite > 0>
--adam-beta1 <finite 0 <= x < 1>
--adam-beta2 <finite 0 <= x < 1>
--adam-eps <finite > 0>
--weight-decay <finite >= 0>
```

For **every fresh BAMF-v2 dry-run or create**, `--run-id`, `--run-seed` and all five
AdamW flags are explicit required operator inputs. C16.1a does not silently consume
the architecture document's `run_seed=0` default and does not invent optimizer
defaults. Explicit `--run-seed 0` is valid. The five optimizer flags are one atomic
input group and materialize exactly one typed `AdamWHyperparameters` before B13
preview/preparation.

Fresh input failures are pinned:

- missing/empty run id, missing seed, or negative seed:
  `BAMF_OPERATOR_FOUNDATION_IDENTITY_REQUIRED`;
- none of the five optimizer fields supplied:
  `BAMF_OPERATOR_FOUNDATION_OPTIMIZER_REQUIRED`;
- only a proper subset supplied:
  `BAMF_OPERATOR_FOUNDATION_OPTIMIZER_INCOMPLETE`;
- non-finite or out-of-domain optimizer value:
  `BAMF_OPERATOR_FOUNDATION_OPTIMIZER_INVALID`.

For **accepted BAMF-v2 resume**, omitted foundation values are not defaults: they mean
"use accepted saved custody." `--run-id` and `--run-seed` are independently optional
equality assertions. The five optimizer flags are optional only as one all-or-none
group; any supplied subset rejects as incomplete before mutation. If the complete
group is supplied it is materialized and compared exactly with the accepted saved
optimizer hyperparameters. The topology and Atlas-manifest flags retain the same
omitted-versus-explicit equality semantics. Pinned resume conflicts are:

- run id: `BAMF_OPERATOR_RESUME_RUN_ID_CONFLICT`;
- run seed: `BAMF_OPERATOR_RESUME_RUN_SEED_CONFLICT`;
- topology: `BAMF_OPERATOR_RESUME_TOPOLOGY_CONFLICT`;
- optimizer group: `BAMF_OPERATOR_RESUME_OPTIMIZER_CONFLICT`;
- Atlas identity: `BAMF_OPERATOR_RESUME_ATLAS_MANIFEST_CONFLICT`.

Mixed explicit resume mismatches have the same literal precedence as that list:
run id -> run seed -> topology -> optimizer group -> Atlas identity. Each comparison
short-circuits before the next, so a command that mismatches more than one saved field
has one deterministic first error.

An interrupted no-pointer generation-zero retry is still a **fresh create command**,
not accepted resume. The operator must repeat the same explicit run id, seed, complete
optimizer group, topology and Atlas manifest so B13 cold recovery can use them only
as equality expectations against sealed custody. Parser tests must prove fresh
requiredness, optimizer all-or-none behavior, valid explicit seed zero, and resume
omission/presence semantics. No historical implementation candidate supplies any of
these semantics by implication.

### Fresh-v2 ownership and validation precedence

The seven foundation arguments above are BAMF-v2-only operator intent. On a **fresh**
command, parser-observed explicit use of **any one** of `--run-id`, `--run-seed`,
`--learning-rate`, `--adam-beta1`, `--adam-beta2`, `--adam-eps`, or
`--weight-decay` transfers command ownership to `bamf_lifecycle` before historical
learner dispatch. R9 does **not** infer explicitness by rescanning raw token text,
because the historical parser keeps argparse long-option abbreviation enabled. A
private parser `Action` owns explicitness: every one of the seven foundation options
uses an action that stores its already-type-converted value and sets the parser-owned
boolean `bamf_v2_foundation_explicit=True`. The parser default is false. The action is
invoked equally for the full option name, `--flag=value`, or any shorter
unambiguous argparse abbreviation that actually exists, such as `--run-i`. The
regression contract therefore exercises full-name and equals-form spelling for all
seven options and one shorter unambiguous abbreviation only for options for which
argparse exposes one. `--adam-beta1` and `--adam-beta2` intentionally have no
shorter unambiguous abbreviation because their names differ only at the final
character; their full names are the shortest accepted unique spellings. No alias is
invented merely to manufacture an abbreviation test. Native argparse
scalar-conversion failures remain ordinary parse failures
and therefore also occur before learner dispatch. Once lifecycle-owned
foundation values are otherwise valid, a missing, unreadable, or non-v2
`--model-topology` rejects as `BAMF_OPERATOR_V2_TOPOLOGY_REQUIRED`; it can never fall
through to `_invoke_learner`. Historical commands that contain none of these seven
v2-only options retain their existing routing unless another already-pinned BAMF-v2
signal owns them (accepted `bamf-state.json`, interrupted v2 custody, or an explicitly
loaded `ModelTopologySpecV2`).

For fresh BAMF-v2 dry-run/create, validation order is normative and shared by both
modes. The first failing step wins:

1. parser-observed v2-intent interception and foundation identity presence/domain (`run_id`,
   `run_seed`);
2. AdamW group requiredness/completeness/domain;
3. `--model-topology` presence, load, and exact `ModelTopologySpecV2` type;
4. `--atlas-release-manifest` presence and source-qualified Atlas identity resolution;
5. admission-policy/scope shape, including scope-file parse/schema validation when
   policy is `atlas-release` and scope-forbidden rejection when policy is `staged`;
6. fresh request-versus-run/topology/Atlas compatibility and, for mutating create,
   the explicit human-start gate;
7. source/target canonical disjointness in both ancestry directions;
8. target path shape and absent/empty/interrupted-genesis classification;
9. B13 preview/preparation and any deeper owner validation.

No later step may be evaluated merely to choose a more specific error. Literal
mixed-invalid regressions freeze representative precedence edges: incomplete optimizer
beats missing topology; invalid/non-v2 topology beats missing Atlas manifest; invalid
Atlas manifest beats invalid scope; invalid scope beats overlapping target; and an
overlapping target beats occupied-target classification. Every such rejection proves
`_invoke_learner` unreachable.

Before any target-run write, a fresh `atlas-release` create parses the enrollment
request and validates only facts already knowable before generation zero. A fresh
`atlas-release` dry-run performs the same request/run/topology/Atlas compatibility
checks but does not require or synthesize live human-start authority:

1. for mutating create only, explicit `--human-run` is present; dry-run skips this
   authority gate because it performs no durable mutation;
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

If the target was absent, all of these leave it absent. If the caller supplied an
existing empty directory, all entries and file bytes remain unchanged; validation
never creates a marker merely to classify that directory.

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

1. classify source and target with the same
   `_canonical_disjoint_run_paths(...)` owner guard used by create. R9 defines
   disjointness by **filesystem identity**, not resolved-path text. Existing source and
   target directories compare `(st_dev, st_ino)` identities directly; ancestry is
   detected by walking the existing directory chain and comparing those identities.
   For an absent target leaf, its deepest existing physical parent is walked before
   the leaf is admitted. Reject physical target==source, source inside target, **or
   target inside source**, including case/Unicode-normalization aliases on a
   case-insensitive filesystem. Dry-run, fresh create and interrupted-genesis recovery
   therefore reject either direction of physical source/target ancestry before target
   mutation;
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

This deliberately refines, rather than silently deletes, the reviewed-base no-MLX
inspection behavior. **Early-invalid configuration inspection remains MLX-free**:
parser/foundation/topology/manifest/scope/path-shape failures that can be decided
before exact B13 preparation must still return their pinned error even when every
`mlx` import is blocked, and must leave source/target bytes unchanged. A **fully
specified valid BAMF-v2 dry-run** is different: because its public result includes the
exact B13 candidate/run identity, it is allowed to import MLX and allocate the same
deterministic unbound generation-zero state as create. If MLX is unavailable after all
cheap validation succeeds, the command fails as an environment/preparation failure;
it does not substitute an approximate identity or fall back to the historical learner.
The existing no-MLX regression is therefore retained as an early-validation
compatibility witness, and a separate valid exact-preview regression runs with MLX
available and proves zero target writes and zero optimizer steps.

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

Add one C07-owned read-only epoch precheck plus one enrollment operation. The
precheck exists so current v1/v2 epoch authority is classified before C09 capability
provisioning can itself fail; presentation may call it, but the classification logic
and error ownership remain C07:

```python
def require_accepted_atlas_epoch_available_v2(run_dir: Path) -> None:
    """Read-only current-epoch classifier; creates no synchronization state."""
    ...
```

The enrollment caller then supplies the request plus opaque accepted-run C09
authority:

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

The command path and owner perform, in order, while preserving existing lock order:

1. require `human_started is True`; this value is supplied directly from the live
   `--human-run` operator invocation and is not inferred from request-file presence;
2. authenticate current accepted B13 custody and derive the current
   `BamfRunIdentity` plus existing `_accepted_run_lease_identity(run_dir)`;
3. before `AcceptedRuntimeHost` or any `SourceAuthorityRuntime` is constructed, call
   the C07-owned `require_accepted_atlas_epoch_available_v2(run_dir)` read-only
   classifier: pre-existing dual current authority rejects
   `BAMF_ATLAS_AUTHORITY_EPOCH_CONFLICT`; v1-only current authority rejects
   `BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT`; neither case creates
   `authority-epoch.lock`, provisions C09 authority or creates any other target state;
4. construct `AcceptedRuntimeHost(run_dir)` and obtain its opaque
   `SourceAuthorityRuntime`; only after the epoch precheck may C09 capability/cache
   validation run;
5. compare request identity in one fixed suborder: first compare the run-id/seed/
   topology tuple and reject `BAMF_ATLAS_V2_ENROLLMENT_RUN_IDENTITY_DRIFT` if any
   member differs; only if that tuple matches compare source Atlas release and reject
   `BAMF_ATLAS_V2_ENROLLMENT_ATLAS_RELEASE_DRIFT` on mismatch;
6. authenticate `source_authority` against the accepted execution cache and obtain
   the registry only inside the C07/C09 owner;
7. call existing `issue_atlas_lease_v2(...)` with the owner-derived
   `LeaseRunIdentity`, request approval/resource/time/command data and the internal
   accepted registry, passing the same explicit `human_started=True` proof rather
   than weakening or deleting that gate;
8. enter the accepted-run mutation transaction, acquire/create the shared cross-epoch
   authority lock, **repeat the same C07-owned epoch classifier while holding it**,
   then acquire
   the v2 epoch-local writer lock and converge to the exact derived lease:
   - no current reference: persist the immutable lease then the current reference;
   - exact current lease already present: return it idempotently;
   - a different current lease: reject with
     `BAMF_ATLAS_LEASE_V2_EXPLICIT_RENEWAL_REQUIRED`;
9. authenticate readback through the same accepted B13/C09 owner before returning.

The pre-C09 and under-lock epoch checks are one C07-owned classifier with two call
sites, not parallel presentation logic. Presentation only invokes the exported
read-only precheck before constructing the C09 host; it never decides v1/v2 authority
precedence and never acquires either epoch lock. This ordering is literal: in a
mixed-invalid accepted run with pre-existing v1/dual authority and broken C09
cache/capability state, the C07 epoch error wins before any C09 error.

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
3. Call C07-owned `require_accepted_atlas_epoch_available_v2(target)` **before** any
   `AcceptedRuntimeHost` / C09 capability construction. This is the same read-only
   epoch precheck required by explicit resume-enrollment; a concurrent v1/dual
   authority winner therefore fails with the pinned C07 epoch error before any C09
   provisioning or accepted-enrollment mutation.
4. Construct `AcceptedRuntimeHost(target)` and obtain opaque
   `source_authority()`.
5. Call `enroll_accepted_atlas_lease_v2(...)`.
6. Exact authenticated lease readback succeeds -> report `CREATED` with effective
   policy `atlas-release`, `ready_for_training=false`.

No lifecycle step invokes the learner.

## Interruption and retry contract

The cross-owner boundary has four **nominal valid** durable states:

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
   `InitialGenerationBinding`. A conflicting B13 artifact retains its existing
   B13 trust/identity/acceptance error. The cold-recovery candidate universe is not
   discovered by scanning `bamf-bundles/`: the reviewed Data Plane has exactly one
   immutable `bamf_genesis_trust` row per `run_id` and a unique
   `manifest_sha256`. Therefore `_stored_trust(expected_run_id)` is the sole
   candidate selector and, when present, its committed manifest is the only bundle
   cold recovery is allowed to authenticate. If
   no exact recoverable B13 genesis exists, any other nonempty target remains
   `BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED`. A fresh create never treats an
   arbitrary occupied directory as writable merely because `bamf-state.json` is
   absent.
3. **Accepted gen0 pointer, no C07 current reference.** The run is lawfully
   `staged`. Enrollment may be completed by an explicit human resume-enrollment
   request.
4. **Accepted gen0 plus valid C07 current reference.** The effective policy is
   `atlas-release`; resume validates/readbacks that lease without caller input.

There is also one bounded **pre-seal crash residue**, not a fifth valid lifecycle
state: a real run directory containing exactly B13's benign persistent synchronization
file `.bamf-pointer.lock` plus a real, empty `.bamf-staging/` directory, with no B13
pointer, bundle, acceptance, genesis-trust row, C07 authority, or other entry. The
pointer lock must be a real regular file, never a symlink or non-file. This is the
actual reviewed B13 owner sequence: generation-zero retry acquires/creates the
persistent pointer lock before `_stage()` creates the staging root.

The staging root is promoted to an explicit durable lifecycle marker. On first
creation, B13 `_stage()` must fsync the new staging directory and then the run root
**before any generation-specific staging work begins**. Every path that removes a
generation-specific stage child while retaining `.bamf-staging/` must fsync that
staging parent after removal. Therefore a crash after stage-root publication can
reliably leave the exact recoverable lock+empty-stage residue rather than relying on
an un-fsynced directory entry.

- `--resume` treats any present/symlinked `.bamf-staging` marker as BAMF-v2
  lifecycle evidence and never falls through to the historical learner. A real
  directory marker rejects
  `BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY`; an unsafe
  symlink/non-directory marker preserves the B13 unsafe-entry error.
- A repeated **fresh create**, under the shared run-root claim and only after all
  pre-write equality/configuration validation succeeds, may reclaim the exact
  lock+stage residue by requiring `.bamf-pointer.lock` to be a real regular file and
  `.bamf-staging` to be a real empty directory, calling `rmdir()` on the staging
  directory only, fsyncing the run root, then re-running the final target classifier.
  That final classifier treats the safe persistent `.bamf-pointer.lock` as B13
  synchronization residue rather than arbitrary user content; no other sibling is
  permitted.
- It never recursively deletes staging contents. A nonempty stage root, a target with
  any sibling entry other than the safe regular `.bamf-pointer.lock`, any unsafe
  pointer-lock shape, or any unsafe stage marker rejects
  `BAMF_FIRST_STUDENT_PRESEAL_STAGING_RESIDUE` (or the owning B13 unsafe-entry error
  for symlink/non-directory shape) and requires operator reconciliation. No trust row
  means cold sealed-genesis recovery is not attempted for this state.

A present C07 current reference whose authenticated readback or exact reconciliation
fails is a separate durable **invalid authority** condition, not a fifth normal
lifecycle state. It always fails closed and is never reclassified as `staged`,
absence, or authority to mint a replacement lease.

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
and never replays current Factory state. Candidate selection is deterministic:
`_stored_trust(expected_run_id)` is read under the existing Data Plane lock. If no
row exists, cold recovery returns `None`. If a row exists, it is authenticated
before any bundle/sidecar/pointer mutation; malformed, drifted, contradictory, or
missing row-referenced evidence raises the existing B13 trust/identity/acceptance or
Data Plane error at the first numbered authentication step above. No directory scan,
lexical sort, heuristic selection, or fallback candidate is permitted. Therefore a
mixed target cannot create a second “plausible” cold-recovery candidate: extra
unreferenced bundles are not candidates and do not outrank the trust-row-bound
authentication result. Only a nonempty no-pointer target with **no trust row for the
expected run id**, no exact prepared retry, and no independently recognized malformed
B13 custody condition falls through to
`BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED`. A command-level `--resume` with
recognized interrupted BAMF-v2 custody but no accepted pointer never performs this
fresh-create recovery implicitly; it rejects
`BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY` and directs the operator
to repeat the original create command with the equality inputs. C16.1a first attempts this
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
The helper accepts only the already-validated historical parsed binding and requires
`binding.digest == expected_acceptance_sha256` before opening a write path. It then
reconstructs exactly the canonical persisted record that the existing
`InitialGenerationBinding.from_record(...)` reader requires:

```python
record = {**binding.fields, "binding_sha256": binding.digest}
```

The checksum field is storage framing for already-verified historical evidence. It
is not added to `ParsedInitialGenerationBinding.fields` and does not recreate a live
`InitialGenerationBinding`. The helper then reuses the existing `_acceptance_path`,
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

The parser keeps the historical `--admission-policy` default of `staged`. The
reviewed unified base does not yet preserve option presence, so C16.1a introduces a
parser-owned `admission_policy_explicit` bit. The `--admission-policy` option uses the
same private explicit-store action pattern as the v2 foundation flags: its parser
default is false, and any argparse-recognized explicit spelling, including an
unambiguous long-option abbreviation, sets the bit true while storing the parsed
policy value. No caller may inject this bit independently and no raw-token rescan may
redefine it. Historical argparse abbreviation behavior remains unchanged. Resume
inheritance is based on that presence bit, not on
the parsed default value: omitted policy inherits accepted custody, while an
explicit `--admission-policy staged` against an accepted `atlas-release` run is a
conflicting override and rejects.

An explicit enrollment retry is allowed only as:

```text
--human-run --resume --admission-policy atlas-release
--atlas-admission-scope <enrollment-request.json>
```

This path has one normative validation order. The first failing step wins. Presentation
owns steps 1-6 and they are read-only; the accepted C07 owner then owns steps 7-11:

1. require the exact command shape above, including parser-owned explicit
   `atlas-release` policy and scope presence;
2. parse the enrollment scope for syntax/schema safety;
3. cold-load and authenticate accepted B13 pointer, student/run identity, optimizer
   settings and accepted Atlas feature receipt; invalid/drifted custody fails here;
4. compare any explicit run/topology/optimizer/Atlas CLI equality assertions with the
   accepted state in the already pinned order run id -> run seed -> topology ->
   optimizer group -> Atlas identity; the first mismatch short-circuits;
5. call C07-owned `require_accepted_atlas_epoch_available_v2(target)` before any C09
   host/capability provisioning; pre-existing dual/v1 authority therefore wins over
   any mixed-invalid C09 cache/capability condition and this precheck creates no lock
   or target state;
6. construct `AcceptedRuntimeHost(target)` and obtain its opaque
   `SourceAuthorityRuntime` capability **without presentation validating the request
   approval/signature/rights itself**;
7. call `enroll_accepted_atlas_lease_v2(...)`; inside that owner, repeat accepted B13
   custody authentication;
8. still inside that owner, compare request run-id/seed/topology as one run-identity
   tuple first; only if it matches compare Atlas release, so
   `BAMF_ATLAS_V2_ENROLLMENT_RUN_IDENTITY_DRIFT` wins over
   `BAMF_ATLAS_V2_ENROLLMENT_ATLAS_RELEASE_DRIFT` when both are wrong;
9. still inside that owner, authenticate the opaque C09 capability, validate
   source approval/signature/rights, construct the owner-derived proposed v2 lease and
   validate every remaining non-mutating precondition;
10. only now enter the accepted-run mutation transaction, acquire/create the shared
   epoch lock, repeat the same epoch classifier under lock, acquire the epoch-local
   v2 writer lock, and persist/converge through the accepted persistence owner;
11. exact existing lease converges idempotently; absent lease may establish the first
    accepted v2 lease; different accepted v2 lease rejects as explicit renewal
    required.

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

R6 makes epoch exclusion a **shared C07 mutation invariant**, not a one-sided v2
caller check. The two immutable lease histories remain physically separate, but every
accepted-run mutation that may install or replace a v1 or v2 `current.json` is
serialized by one cross-epoch authority lock owned under the existing
`autonomy/atlas-admission/` root at
`autonomy/atlas-admission/authority-epoch.lock`. The lock file is a no-follow regular
file with the same host-local `flock` discipline as the existing writers. Lock order
is fixed: cross-epoch authority lock first, then the epoch-specific v1 or v2 writer
lock. No caller may acquire them in the reverse order.

While holding that cross-epoch lock:

- accepted v2 first enrollment checks canonical v1 current authority before v2
  current-reference mutation; a regular v1 current rejects
  `BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT`;
- accepted v1 persistence checks canonical v2 current authority before v1
  current-reference mutation; a regular v2 current rejects
  `BAMF_ATLAS_V1_SUCCESSOR_AUTHORITY_PRESENT`;
- unsafe/symlink current-reference paths retain the owning epoch's storage/path error;
- if both current references already exist on entry, no writer attempts repair and
  the owner reports `BAMF_ATLAS_AUTHORITY_EPOCH_CONFLICT`.

This changes accepted-run mutation admission only. Historical v1 read compatibility,
immutable v1 lease bytes, v1 renewal history, and physically separate v2 storage are
preserved. Low-level fixture storage remains usable only on roots that are provably
not run custody. R7 makes that statement mechanical: the shared v1 `_store(...)`
fixture guard and the v2 fixture storage entrypoint reject before creating any
directory, lock, immutable lease, renewal edge or current reference when the root
contains or symlinks **any** recognized run-custody marker:

```text
state.json
bundles
generations
bamf-state.json
bamf-bundles
bamf-acceptance
.bamf-staging
```

R12 closes the remaining **pre-marker race** without reserving a child filename.
Marker inspection alone is insufficient
because B13 may have claimed a fresh root after its final empty-directory check but
before `bamf-bundles` or `bamf-state.json` exists. B13 mutating create/recovery and
generic C07 fixture mutation therefore share one host-local **run-root claim lock**
that lives outside the target namespace. The lock is deliberately **not keyed by
target path text and creates no filesystem child at all**. The helper resolves and
opens the target's physical parent directory with `O_DIRECTORY|O_NOFOLLOW`, verifies
the opened descriptor is a directory, and applies host-local `flock(LOCK_EX)`
directly to that physical-parent directory descriptor. All candidate
run roots beneath one physical parent therefore share one short-lived claim mutex
without reserving any legal run-directory basename.
This is intentionally coarser than per-target locking: it trades a small amount of
same-parent create concurrency for filesystem-identity correctness across case and
Unicode-normalization aliases on macOS/APFS.

The parent itself is resolved and opened as a real directory before lock acquisition;
the helper never derives lock identity from the caller's string spelling. Different
path aliases that resolve through the same physical parent therefore lock the same
directory inode. If the target parent does not yet exist, B13 calls the shared helper
with `create_parent=True`; parent-chain creation/fsync is therefore part of claim
acquisition and still occurs before target creation or classification. Generic fixture
mutation calls the same helper with `create_parent=False`, still requires its root
parent to exist as a safe directory, and never creates a missing fixture parent merely
to lock it.

The shared API is exact:

```python
@contextmanager
def run_root_claim(target: Path, *, create_parent: bool) -> Iterator[None]:
    ...
```

`target` is the candidate run root, not its parent. The helper **never creates
`target`**. When `create_parent=True`, used only by B13 fresh create/recovery, it
may create the missing `target.parent` chain, fsync each newly created directory plus
the nearest pre-existing ancestor, and then continue. When `create_parent=False`,
required for generic C07 fixture mutation, a missing parent is a claim-acquisition
failure and nothing is created. The helper then resolves `target.parent` strictly to
its physical directory, opens that resolved directory with
`O_RDONLY|O_DIRECTORY|O_NOFOLLOW` where supported, verifies the opened
`fstat` is a directory, takes blocking `flock(LOCK_EX)`, yields exactly `None`,
then releases and closes the descriptor.

Acquire-phase failures before `yield` have one literal surface:
`BAMF_RUN_ROOT_CLAIM_UNAVAILABLE`. This includes strict parent resolution,
open/fstat/type validation, and lock acquisition. It occurs before protected target
classification/mutation. B13 and C07 propagate it unchanged.

Release-phase failures are different because the protected body may already have
mutated durable state. If the body completed successfully but `LOCK_UN` or descriptor
close reports failure, raise `BAMF_RUN_ROOT_CLAIM_RELEASE_FAILED`. That error means
**postcondition unknown, reconcile before retry**; it never implies rollback and must
not trigger automatic replay. If the protected body itself raised an exception and
release also fails, preserve the body exception as the primary semantic failure,
attempt descriptor close, and add exactly one Python exception note to that original
exception:
`BAMF_RUN_ROOT_CLAIM_RELEASE_FAILED:<unlock|close>`.
Then re-raise the same body-exception instance. Do not chain or replace it with a
claim-release exception. If unlock and close both fail, the note records `unlock`,
the first release-phase failure; close is still attempted. A clean
release returns normally. Path disjointness and caller-input validation that occur
before claim acquisition retain their earlier pinned errors.

Lock coverage is exact:

- B13 fresh create/recovery acquires the run-root claim **before its final target
  emptiness/recovery classification** with `create_parent=True` and holds it through generation-zero
  publication/recovery until either an accepted B13 custody marker exists or the
  operation has failed without acceptance;
- generic v1/v2 fixture persist/renew acquires the same run-root claim before the
  recognized-custody-marker guard with `create_parent=False` and holds it through
  the complete fixture mutation;
- accepted v1/v2 persistence on an already accepted B13 run does not need the root
  claim; it uses the separately pinned shared epoch lock because the B13 root claim is
  no longer contested once accepted custody exists.

This yields a deterministic race result even when the two callers spell the same
physical parent/target with different case or Unicode normalization. If a fixture
writer wins the claim first,
its Atlas fixture content makes the target nonempty and B13 subsequently rejects fresh
creation rather than accepting mixed custody. If B13 wins first, the fixture writer
waits, then observes accepted/interrupted B13 custody and rejects before Atlas fixture
mutation. Adding more marker names is not relied upon for this guarantee.

Lock order is disjoint and fixed: root-claim -> B13 pointer lock for initial
publication/recovery; root-claim -> epoch-local fixture writer lock for generic fixture
mutation; shared accepted-run epoch lock -> epoch-local accepted writer lock for later
accepted C07 persistence. No path acquires these in reverse order.

The first three retain historical saved-run protection; the last three are the B13
custody family relevant here. A B13 root therefore cannot call
`persist_atlas_lease(...)`, `renew_atlas_lease(...)`,
`persist_atlas_lease_v2(...)`, or `renew_atlas_lease_v2(...)` through the fixture
boundary at all. C16.1a does **not** create a new accepted-run renewal API for either
epoch. Historical renewal artifacts remain readable, and any future accepted-run
renewal must be introduced by its owning C07 work through a separately named
accepted-run owner that takes the same shared epoch lock. The accepted persistence
APIs used here bypass fixture authority only after independent B13
identity/source-authority replay and then take the shared epoch lock.
Fixture roots without any custody marker may still deliberately host v1 and v2
fixtures side by side for compatibility tests; those fixture refs carry no accepted
run authority.

Implementation ownership is exact. `atlas_lease_storage.py` exposes one internal
`_reject_fixture_run_custody(root)` helper containing the marker set above. Historical
v1 `_store(..., fixture_authority=True)` calls it before directory creation. Generic
v2 `persist_atlas_lease_v2(...)` and `renew_atlas_lease_v2(...)` call the same helper
**before** acquiring `_atlas_lease_v2_lock`; `_store_v2(...)` remains the storage/path
owner and is not reclassified as accepted-run authority. This avoids making the v2
reader unusable on accepted runs while still making every generic v2 writer
mechanically fixture-only. The accepted v1/v2 persistence paths bypass the fixture
guard only through their separately named accepted-run APIs after B13/C09 replay and
the shared epoch lock. No boolean flag exposed to presentation code can select that
bypass.

Request parsing has deterministic precedence without creating synchronization state
for validation-only failures. The complete explicit resume-enrollment order is the
eleven-step sequence above. In particular, scope syntax/schema parsing precedes
accepted custody load; presentation-level custody and explicit saved-setting equality
precede the **C07-owned read-only epoch precheck**, and that precheck precedes
construction of the opaque C09 capability. The accepted C07 enrollment owner then
re-authenticates custody and owns request comparison, C09 validation and the final
under-lock epoch recheck. Pre-existing dual authority reports
`BAMF_ATLAS_AUTHORITY_EPOCH_CONFLICT`; v1-only authority reports
`BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT`, including when C09 state is independently
invalid. A request that fails this precheck or any subsequent
request/custody/signature validation creates no `authority-epoch.lock` and no other
target artifact merely to reject.

Only after all non-mutating enrollment validation succeeds does the accepted-run
writer enter its mutation transaction. It acquires/creates the shared epoch lock,
then **repeats the epoch classification while holding that lock** before acquiring the
epoch-local writer lock or writing any lease/current authority. A concurrent other-
epoch winner discovered by this mandatory under-lock recheck rejects with the same
epoch error before lease/current mutation. The lock file itself is synchronization
state created only after the command has passed validation and entered the authorized
mutation transaction; it is not an accepted lease/current authority artifact.

Required regressions cover sequential v1->v2 and v2->v1 attempts plus a synchronized
concurrent race. Exactly one epoch may win; the losing writer must reject before its
other-epoch `current.json` becomes authoritative. Existing low-level C07 v2
fixture/storage tests may continue proving the epochs' immutable histories are
physically separate on a marker-free fixture root. A separate negative regression
builds an accepted B13 generation-zero root and calls each low-level v1/v2
persist/renew entrypoint directly; each must reject as fixture authority forbidden
before any Atlas storage mutation, proving the fixture API cannot bypass the shared
accepted-run epoch invariant. Validation-only request mismatches also snapshot the
target before/after and prove no epoch-lock artifact is created.

A separate synchronized race starts B13 fresh generation-zero publication and a
generic v1 or v2 fixture writer against the same initially empty target. The test
forces the interleaving around B13's final empty-root check and proves the only legal
outcomes are: B13 accepted and fixture rejected with no Atlas fixture current, or
fixture committed and B13 rejected as occupied with no accepted B13 pointer. It must
never observe accepted B13 custody coexisting with fixture-created C07 current
authority. On case-insensitive hosts, the same regression repeats with distinct case
spellings of the parent/leaf that resolve to the same physical target; where the host
filesystem exposes Unicode-normalization aliases, an additional composed/decomposed
leaf spelling is exercised. The platform-conditional alias checks are evidence for
filesystem identity, not a portability assumption baked into the production key.

## CLI mode matrix and dispatch ownership

The shared C11/C16 operator contract is exact:

| Mode | Required identity/optimizer + policy/scope behavior | Mutation |
| --- | --- | --- |
| fresh staged dry-run | explicit `--run-id`, `--run-seed`, complete five-field AdamW group, `--model-topology`, `--atlas-release-manifest`; policy omitted or explicit `staged`; scope forbidden | none |
| fresh atlas-release dry-run | same explicit foundation inputs plus `--admission-policy atlas-release --atlas-admission-scope <enrollment-request.json>` | none |
| fresh staged create | same explicit foundation inputs plus `--human-run`; scope forbidden | generation-zero only |
| fresh atlas-release create | same explicit foundation inputs plus `--human-run --admission-policy atlas-release --atlas-admission-scope <enrollment-request.json>` | generation-zero, then first C07 enrollment |
| normal BAMF resume | scope omitted; run id/seed/topology/Atlas/policy omitted means accepted saved custody; complete optimizer group omitted means accepted saved optimizer; any explicit value/group must match | none in C16.1a |
| first post-genesis enrollment | `--human-run --resume --admission-policy atlas-release --atlas-admission-scope <enrollment-request.json>`; other omitted settings come from accepted custody and any explicit equality assertion must match | first C07 enrollment only |

Every fresh v2 dry-run/create requires `--atlas-release-manifest` because B13
generation-zero identity always contains the source-qualified Atlas artifact. An
`atlas-release` fresh dry-run additionally requires and validates the enrollment
request even though it does not persist a lease; this is what allows the dry-run to
prove the same request/run/topology/Atlas-release compatibility that create will
consume. It does not require `--human-run`, because it issues no authority and makes
no durable target mutation. A scope with `staged` is always invalid. A fresh `atlas-release` create or
dry-run without scope is always invalid. Normal resume never requires a scope.

Dispatch is pinned before implementation:

1. a fresh command whose parser-owned `bamf_v2_foundation_explicit` bit is true is
   intercepted by `bamf_lifecycle` before historical learner routing; if its topology
   is missing, unreadable, or not `ModelTopologySpecV2`, it rejects
   `BAMF_OPERATOR_V2_TOPOLOGY_REQUIRED` rather than falling through;
2. a fresh command with an explicit successfully loaded `ModelTopologySpecV2` is
   owned by `bamf_lifecycle` even if the foundation group is incomplete, so lifecycle
   validation reports the pinned foundation error rather than historical learner
   behavior;
3. `--resume` against a run directory with `bamf-state.json` is owned by
   `bamf_lifecycle` even when `--model-topology` is omitted, because accepted B13
   custody supplies the saved topology;
4. `--resume` against a target with no pointer but with BAMF-v2 genesis custody or
   pre-seal artifacts (genesis-trust row, `.bamf-staging`, generation-zero
   bundle/acceptance evidence, or the v2 BAMF bundle directory shape) is intercepted
   before historical learner routing.
   This command path is **classification-only and non-mutating**: marker presence is
   sufficient to reject
   `BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY` before any B13
   prepared/cold-recovery owner, acceptance-sidecar writer, pointer writer, outbox
   reconciliation or mutable-source replay is invoked. The operator must repeat the
   original fresh create command with the equality inputs. It can never reach
   `_invoke_learner` merely because `bamf-state.json` is absent;
5. an interrupted generation-zero publication with no pointer is retried by
   repeating the fresh v2 create command with the same topology/source/seed/Atlas
   manifest **and optimizer** inputs; target-state handling attempts
   source-independent sealed B13 cold recovery before any mutable-source
   reconstruction and never enters the historical learner-resume path;
6. commands with no v2-only foundation argument, no v2 topology, no accepted BAMF
   pointer, and no BAMF-v2 custody artifacts retain the
   historical v1 routing;
7. when `bamf_lifecycle` owns the command, `command._main` returns its lifecycle
   result before `_invoke_learner` can run. `--human-run --resume` does not by itself
   authorize learner entry for a BAMF v2 run in C16.1a.

Target classification is pinned against the reviewed unified owner. At `905018b0`,
the existing fresh-only helper is
`bilqis_mlx/runtime/_bamf_first_student_support.py:_fresh_run_dir`; there is no
pre-existing presentation `fresh_target()` helper. C16.1a factors that runtime path
owner into two responsibilities and lets the new presentation lifecycle consume the
non-mutating classifier instead of creating a second target-path authority:

```python
def _canonical_run_dir_shape(path: Path) -> Path:
    """Reject symlink/non-directory unsafe shape, but do not reject nonempty dirs."""
    ...

def _fresh_run_dir(path: Path) -> Path:
    """Existing fresh-only helper: canonical shape + empty-directory requirement."""
    ...
```

`bamf_lifecycle` uses `_canonical_run_dir_shape()` for BAMF v2 create/dry-run
routing. For
dry-run, normal empty-target validation still applies because no recovery mutation is
needed. For actual create, an empty target proceeds to ordinary B13 preparation;
a nonempty target with no accepted pointer is passed to the B13 recovery-aware owner,
which alone may classify it as exact sealed interrupted genesis versus arbitrary
occupied state. A nonempty target with an accepted pointer is not create and directs
the operator to resume. Existing fresh B13 callers retain `_fresh_run_dir()`.
No presentation helper is allowed to decide that arbitrary nonempty content is a
recoverable B13 generation.

Before this target-state branch, `_canonical_disjoint_run_paths(source, target)` is
always evaluated and now rejects ancestry in **both directions**. A BAMF-looking
nonempty target that is an ancestor of the source is therefore rejected as
`BAMF_FIRST_STUDENT_TARGET_OVERLAPS_SOURCE` and cannot reach B13 recovery. A literal
regression snapshots that ancestor tree and proves zero mutation.

## Saved-setting conflict contract

Ordinary resume with omitted values uses accepted saved settings. Explicit values
must exactly match:

- run id;
- run seed;
- topology;
- optimizer hyperparameters;
- Atlas identity;
- effective admission policy.

Literal regressions must cover run-id, run-seed, topology, complete
optimizer-hyperparameter group and Atlas-identity mismatches, plus the reverse policy
mismatch where an accepted `atlas-release` run is resumed with explicit `staged`.
Every mismatch rejects before mutation or learner dispatch. An incomplete optimizer
override group rejects before equality comparison.

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
argument that moved into a helper must retain its established default and action
semantics. Existing help text is retained except where this issue makes the old text
factually false. In particular, `--human-run` is updated to the pinned truthful
description:

`Explicit human authorization for mutating operator actions; legacy learner paths may perform optimizer steps, while BAMF v2 create/enrollment remains neural-inert.`

Retention bounds,
autonomous curriculum, max visits, timing trace, source prefetch workers, flash
mode, stagnation grace and debt-admission help text may not silently disappear.
Add a parser-help regression that checks the affected option descriptions remain
present in `train --help` and that `--human-run` uses the exact wording above; do
not weaken the operator documentation to match a regressed parser.

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
   selection;
8. the same cohesive witness includes one **positive developmental evidence** result
   from an existing source-qualified package-local fixture: either acquired taught
   behavior or retained taught behavior is observed and the witness records which
   evidence kind satisfied the gate. This is evidence about the admitted
   Factory/teacher/retention path, not permission to run a fresh real learner and not
   a requirement that generation zero itself improve.

The witness may use existing package-local source/teacher fixtures. It must call the
real C16.1a lifecycle and real B13/C03/C09-source-authority functions; it must not
mock the observed behavior under test or run a real learner.

## Persisted-source recovery witness

Both one happy-path **dry-run** and one happy-path **create** test must not patch
`bamf_lifecycle.source_foundation`. Each builds or reuses a disposable canonical
source run with:

- current State-DAG receipt;
- immutable executable Factory release artifact;
- model-bundle semantic catalog + digest binding;
- exact semantic graph fingerprint.

Each test points `BILQIS_STORAGE_ROOT` at that disposable source **and** points
`BILQIS_DATA_PLANE` at a disposable test-local Data Plane created for that witness.
No source-recovery test may read or write the workstation-global State-DAG SQLite or
other ambient Data Plane state. The witness traverses the real
`active_run_dir() -> read_current() -> executable release -> semantic catalog`
recovery path, snapshots every source-run directory entry and file byte before the
command, and proves the entire source tree is unchanged afterward. The create test may
mutate only its disjoint target run and its test-local Data Plane; the dry-run may
perform no target mutation. Test teardown removes both disposable roots.

## Required post-genesis enrollment-failure witness

The two-transaction boundary is tested literally. One fresh `atlas-release` create
uses valid pre-generation inputs, successfully publishes accepted B13 generation
zero, then injects a real-owner C07/C09 enrollment failure such as signature, rights,
or source-authority rejection **after** generation-zero acceptance. The witness must
prove all of the following in one disposable run:

1. the accepted B13 pointer, bundle and generation-zero acceptance remain exact and
   readable; C16.1a never rolls back lawful generation zero merely because first C07
   enrollment failed;
2. no authoritative v2 `current.json` or accepted v2 lease is minted by the failed
   transaction and no learner/optimizer dispatch occurs;
3. a subsequent no-scope resume classifies the run as `staged`;
4. after correcting only the C07/C09 enrollment input/authority, explicit
   `--human-run --resume --admission-policy atlas-release --atlas-admission-scope ...`
   converges to one exact v2 lease without republishing generation zero.

This test uses the real B13/C07/C09 owner boundary. It may use package-local signing
and authority fixtures but must not replace the enrollment operation with a mocked
success/failure return value.

## Implementation surface after EGM pass

Production, with required file action:

- **Create** `bilqis_mlx/runtime/_coordination/__init__.py` and
  **Create** `bilqis_mlx/runtime/_coordination/run_root_claim.py`
  - own the neutral host-local run-root claim by applying `flock` directly to an
    opened physical target-parent directory descriptor; expose only a bounded context
    manager usable by B13 fresh publication/recovery and C07 generic fixture mutation;
    create no child lock path, deliberately use no target-path-text hash, expose
    exactly `run_root_claim(target: Path, *, create_parent: bool) -> Iterator[None]`,
    where only B13 may pass true and the helper never creates the target; distinguish pre-yield
    `BAMF_RUN_ROOT_CLAIM_UNAVAILABLE` from post-body
    `BAMF_RUN_ROOT_CLAIM_RELEASE_FAILED`, and carry no
    semantic or admission authority; the dedicated package keeps the reviewed
    `bilqis_mlx/runtime/` directory below its mandatory 18-direct-code-file trigger
    and is not a broader runtime reorganization;
- **Modify** `bilqis_mlx/runtime/_admission/atlas_lease_contracts.py`
  - add immutable non-authoritative enrollment request;
- **Create** `bilqis_mlx/runtime/_admission/atlas_enrollment_v2.py`
  - own enrollment-request parsing, accepted-run first enrollment, explicit
    human-start propagation, accepted-run/Atlas comparison, v1-authority exclusion
    and issuance; no storage reconciliation logic;
- **Modify** `bilqis_mlx/runtime/_admission/atlas_admission.py`
  - retain existing frontier/lease compatibility responsibilities, re-export the
    bounded enrollment owner without absorbing its implementation, and make accepted
    v1 persistence participate in the shared cross-epoch authority lock with
    reciprocal v2-current exclusion; keep generic v1 renewal fixture-only on B13
    custody rather than inventing a new accepted renewal surface here;
- **Modify** `bilqis_mlx/runtime/_admission/atlas_lease_storage.py`
  - own the shared cross-epoch authority lock/path safety primitive used before any
    accepted v1/v2 current-reference mutation; preserve the existing v1 writer lock as
    the second lock for v1 storage; expand the fixture-authority saved-run guard to the
    exact legacy+B13 custody marker set pinned above before any fixture mutation;
    generic v1 fixture persist/renew takes the neutral run-root claim before that guard
    and holds it through the epoch-local fixture writer transaction;
- **Modify** `bilqis_mlx/runtime/_admission/atlas_lease_v2.py`
  - make accepted v2 persistence acquire the shared cross-epoch authority lock before
    the existing v2 writer lock and enforce reciprocal v1-current exclusion;
    ensure generic fixture persistence/renewal consumes the same custody-marker
    rejection before it can reach v2 storage; generic v2 persist/renew takes the same
    neutral run-root claim before the guard and holds it through the v2 fixture writer
    transaction; do not introduce accepted v2 renewal in C16.1a;
- **Modify** `bilqis_mlx/runtime/_admission/atlas_lease_storage_v2.py`
  - required: exact `_durable_json` byte comparison for orphan reuse plus bounded
    same-lock post-reference reconciliation as the sole v2 storage reconciliation
    owner; retain the epoch-specific lock as the second lock beneath the new shared
    authority lock;
- **Create** `bilqis_mlx/presentation/operator_cli/bamf_lifecycle.py`
  - fresh request validation, post-genesis enrollment, resume-enrollment completion,
    exact preview identity, training-readiness false, and recovery-aware nonempty
    target routing before mutable-source reconstruction;
- **Create** `bilqis_mlx/presentation/operator_cli/bamf_lifecycle_inputs.py`
  - own CLI-only source/manifest/optimizer input recovery and the exact fresh/resume
    identity/AdamW presence semantics pinned above while consuming the runtime target
    classifier instead of defining a second target-path authority;
- **Modify** `bilqis_mlx/runtime/_bamf_first_student_support.py`
  - factor `_fresh_run_dir(...)` into `_canonical_run_dir_shape(...)` plus the
    existing empty-target requirement, and strengthen
    `_canonical_disjoint_run_paths(...)` so source/target equality and ancestry are
    decided from filesystem identities `(st_dev, st_ino)` and physical ancestor walks,
    not textual resolved paths; reject both directions before BAMF v2 routing can
    inspect a nonempty target;
- **Modify** `bilqis_mlx/runtime/bamf_first_student.py`
  - factor deterministic pre-publication preparation and expose exact run-identity
    preview with source/target disjointness, plus recovery-aware fresh target handling;
    for mutating create/recovery, take the neutral run-root claim before final target
    classification and hold it through generation-zero publication/recovery;
- **Modify** `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/__init__.py` and
  **Modify** `bilqis_mlx/runtime/_custody/bamf_bundle/publication/retry.py`
  - expose prepared retry plus source-independent cold recovery for an exact sealed
    unpointed generation zero; reconstruct a missing historical acceptance record
    only from trust-row digest + sealed student, using
    `initial_generation_candidate_identity_digest(student)` and exact optimizer
    digest equality, never from current Factory replay;
- **Modify** `bilqis_mlx/runtime/_custody/bamf_bundle/publication/storage.py` and
  **Modify** `bilqis_mlx/runtime/_custody/bamf_bundle/publication/__init__.py`
  - add `_write_parsed_initial_generation_acceptance(...)` as the only historical
    acceptance-sidecar write path, reusing existing canonical/atomic/fsync semantics;
  - make first creation of `.bamf-staging/` durable before generation-specific work by
    fsyncing the new staging directory and run root, and route every retained-root
    stage-child cleanup through one helper that fsyncs `.bamf-staging/` after child
    removal; preserve `.bamf-pointer.lock` as the existing persistent B13
    synchronization file rather than pretending the pre-seal residue is stage-only;
- **Modify** `bilqis_mlx/presentation/operator_cli/command.py` and **Modify**
  `bilqis_mlx/presentation/operator_cli/parser.py` only as required for
  the pinned v2 dispatch/presence-bit routing **and** the explicit BAMF-v2 foundation
  input flags frozen in this R11 contract; parser-owned explicit-store actions must
  preserve argparse abbreviations while making any accepted explicit v2-only
  foundation option intercept before historical learner dispatch even when topology
  is omitted or invalid; `--admission-policy` uses the same parser-owned explicitness
  pattern; no new trust-source flag and no change to
  historical `--admission-policy` default/action semantics;
- **Modify** `docs/tasks/bamf-0.2/children/C11.1.md` and **Modify**
  `docs/architecture/BAMF_0_2.md`
  - align the affected shared operator command contract with the exact scope matrix.

Tests:

- **Create** `bilqis_mlx/runtime/_coordination/tests/test_run_root_claim.py`
  - mirrored unit owner for physical-parent alias convergence, no-child-lock
    namespace behavior, acquire failure, successful release, post-body release
    failure, and body-error-plus-release-error precedence;
  - `create_parent=True` with a missing nested parent creates **only** the parent
    chain, never the target, and spies on fsync to require every newly created
    directory plus the nearest pre-existing ancestor before the claim yields;
  - `create_parent=False` with the same missing parent rejects
    `BAMF_RUN_ROOT_CLAIM_UNAVAILABLE` and proves the missing chain remains absent;
- **Create** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_create_resume.py`;
- **Create** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_atlas_release_create.py`;
- **Create** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_resume_admission_policy.py`;
- **Modify** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_preflight.py`;
- **Create** `bilqis_mlx/presentation/operator_cli/tests/test_bamf_first_start_neutrality.py`;
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
- full-name and `--flag=value` spellings of every BAMF-v2-only foundation flag,
  plus one shorter unambiguous abbreviation for each option where argparse actually
  exposes one, set parser-owned v2 explicitness and intercept before historical
  learner dispatch; `--adam-beta1` and `--adam-beta2` have no shorter
  unambiguous spelling and are explicitly exempt from the abbreviation subcase;
  missing/invalid/non-v2 topology reports
  `BAMF_OPERATOR_V2_TOPOLOGY_REQUIRED` with `_invoke_learner` unreachable;
- full-name and abbreviated `--admission-policy` spellings set
  `admission_policy_explicit`; omitted policy remains false and inherits accepted
  custody on resume;
- mixed-invalid fresh commands prove the pinned validation order across foundation,
  topology, Atlas manifest, scope, source/target overlap and occupied-target failures;
- the reviewed-base fresh-process no-MLX regression remains an **early-invalid**
  configuration witness: with MLX imports blocked it returns the pinned
  foundation/configuration error before exact B13 preparation and preserves the full
  source/target snapshot; a separate fully specified valid v2 dry-run runs with MLX
  available, returns the exact B13 `run_identity`, and proves zero target writes,
  zero learner dispatch and zero optimizer steps;
- mixed-invalid accepted resume commands prove CLI equality precedence
  run id -> run seed -> topology -> optimizer group -> Atlas identity, including at
  least one case with every equality assertion wrong;
- mixed-invalid explicit enrollment proves the accepted C07 owner reports
  `BAMF_ATLAS_V2_ENROLLMENT_RUN_IDENTITY_DRIFT` before
  `BAMF_ATLAS_V2_ENROLLMENT_ATLAS_RELEASE_DRIFT` when both request identity and
  Atlas release disagree with accepted custody;
- atlas-release dry-run validates request compatibility without `--human-run` and
  still performs zero durable target mutation;
- staged-gen0 -> resume enrollment completion;
- exact enrollment retry convergence;
- existing different lease -> renewal-required rejection;
- interrupted pre-current and post-current reconciliation;
- typed-equal but byte-different orphan v2 lease rejects immutable drift rather than
  being reused; only exact canonical `_durable_json` bytes may converge;
- accepted Atlas custody drift and request-vs-accepted Atlas mismatch with literal
  pinned error precedence;
- v1 historical accepted-run resume, v1+v2 epoch conflict, and rejection of v2 first
  enrollment on a v1-authorized run;
- shared epoch serialization: sequential v1->v2 and v2->v1 mutations plus a
  synchronized concurrent race prove exactly one current-authority epoch can win;
- low-level fixture APIs remain compatible on marker-free roots but every low-level
  v1/v2 persist/renew call against a real accepted B13 root rejects before Atlas
  storage mutation, closing the authority-lock bypass;
- synchronized B13-fresh-create versus generic v1/v2 fixture-writer races are
  serialized by the neutral physical-parent directory claim: accepted B13 custody and
  fixture-created C07 current authority can never coexist from the race; a legal run
  basename that formerly would have matched `.bamf-root-claim.lock` remains legal
  because R12 creates no lock child; on case-insensitive hosts, repeat with
  case-distinct aliases to the same physical target and, where supported,
  composed/decomposed Unicode aliases;
- B13 cold unpointed recovery after source advance both with persisted acceptance and
  with a missing sidecar reconstructed exactly from trust-row + sealed student;
- interrupted cold recovery with each independently changed run id, run seed,
  topology, Atlas identity and AdamW setting rejects before acceptance/pointer/outbox
  mutation;
- a real-owner lock+stage pre-seal crash residue is lifecycle-owned: B13 durably
  publishes `.bamf-staging/` by fsyncing it and the run root before staging children,
  and fsyncs the staging parent after generation-child cleanup; a no-pointer
  `--resume` with a safe regular `.bamf-pointer.lock` plus real `.bamf-staging/` rejects
  `BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY` with
  `_invoke_learner` and both mutating B13 recovery owners unreachable; repeated
  fresh create under the root claim may remove only an empty real stage root, fsync
  the run root, re-check the target while ignoring only the safe persistent pointer
  lock, and continue; a nonempty stage, any additional sibling, unsafe pointer lock,
  symlink or non-directory stage residue fails closed without recursive deletion; the
  regression must enter the real `_pointer_lock` -> `_stage` owner order before
  simulating the crash so the residue shape cannot be invented by a fixture;
- command-level nonempty/no-pointer interrupted create reaches B13 recovery; the sole
  candidate is the immutable Data Plane genesis-trust row selected by expected
  `run_id`; malformed/drifted row-bound trust/acceptance/bundle evidence preserves
  the existing B13/Data Plane error; extra unreferenced bundles are never alternate
  candidates; and an arbitrary occupied target with no trust row, exact prepared
  retry, or recognized malformed B13 evidence rejects
  `BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED`;
- source/target overlap is symmetric: source-under-target and target-under-source both
  reject before dry-run/create/recovery mutation, including an ancestor target with
  BAMF-looking contents; on case-insensitive hosts the same equality/ancestry cases
  are repeated through case-distinct aliases and, where supported, Unicode-normalized
  aliases, proving the guard follows filesystem identity rather than path spelling;
- command-level `--resume` against BAMF-v2 custody artifacts with no pointer is
  intercepted before historical learner dispatch and rejects
  `BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY` from marker-level
  classification only; snapshots prove zero acceptance/pointer/outbox/lease mutation
  and the mutating B13 recovery owners are unreachable;
- saved atlas-release -> explicit staged rejection;
- ordinary resume literal mismatches for run id, run seed, topology, complete
  optimizer override and Atlas identity each reject before any mutation or learner
  dispatch; partial optimizer override rejects as incomplete;
- parser presence-bit proof distinguishes omitted admission policy from explicit
  `staged` without changing argparse's historical default or abbreviation behavior;
- dry-run exact B13 identity equals subsequent create identity;
- parser-help text preserved across helper extraction;
- cohesive first-start Functional Factory/rollback/cold-resume witness including one
  source-valid positive acquired-or-retained taught-behavior evidence kind;
- post-generation-zero C07/C09 fault witness proving accepted staged genesis survives
  failed enrollment and corrected explicit resume-enrollment later converges;
- dashboard `READY_FOR_HUMAN_START` remains non-authorizing while lifecycle
  `ready_for_training` is false and learner dispatch is unreachable;
- unmocked persisted-source recovery + complete source-tree byte preservation for
  both dry-run and create, with both `BILQIS_STORAGE_ROOT` and `BILQIS_DATA_PLANE`
  isolated to disposable test-local roots;
- validation-only enrollment mismatches do not create `authority-epoch.lock`; after
  validation succeeds, the accepted writer acquires the shared lock and repeats epoch
  classification under lock before any lease/current mutation.
- mixed-invalid accepted enrollment with pre-existing dual or v1-only epoch authority
  plus invalid C09 cache/capability state proves the C07 read-only epoch precheck runs
  before `AcceptedRuntimeHost` construction and the pinned epoch error wins.
- atlas-release fresh create proves the same ordering after generation-zero
  publication: if pre-existing/concurrently established v1 or dual authority is
  visible before C09 host construction, the C07 epoch error wins; if the competing
  epoch lands only after the read-only precheck, the mandatory under-lock epoch
  recheck rejects before any v2 lease/current mutation. Neither route may fall back to
  learner dispatch or perform an optimizer step.

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
