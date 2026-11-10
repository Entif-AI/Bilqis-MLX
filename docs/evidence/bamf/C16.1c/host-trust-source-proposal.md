# C16.1c host trust-source repair proposal

Status: PROPOSED v6 / fresh EGM re-review required before implementation.

Review note: v6 retains v5's fixed-host architecture and closes two source-mapping details
found during read-only implementation-feasibility mapping: the failed fresh-target exception
lives in `_bamf_first_student_support.py`, and the shared `genesis_preparation()` fixture
still passes `source_authority_run_dir`. V6 adds those exact Phase-B edit/test-fixture surfaces
and makes the host fd opener receive the existing registry byte limit explicitly rather than
duplicating a custody constant. It also closes the fresh-v5 Design Critic Major by preserving
the one lawful pre-#950 #926 transition: a verified historical unanchored generation may bind
the existing #917 run-local registry on its first retained successor. New C16.1c-born HOST
lineages cannot use that compatibility transition.

V5 retained v4's fixed-host architecture and corrected a Darwin behavior observed
during read-only feasibility proof: on ordinary files/directories with no extended ACL,
acl_get_fd_np(fd, ACL_TYPE_EXTENDED) returns NULL with errno ENOENT on the current host.
V5 treats exactly that result as an empty extended ACL and keeps every other ACL retrieval
failure fail-closed. It also verifies the root anchor descriptor before fd-relative traversal.
Fresh EGM review remains required before implementation.

V4 retained v3's fixed-host architecture and closed the fresh-v3 EGM
findings around exact Darwin path/ACL enforcement, callable custody APIs, phase-stable
accepted-runtime behavior, caller threat model, exact file/test scope, and the remaining
TOCTOU wording mismatch. Production code remains frozen until this amended shared contract
reaches 0 Blockers / 0 Majors.

V3 closed the fresh-v2 EGM findings around host path custody, lineage
inheritance, resolver lock ownership, generation-zero retry ordering, correction-frontier
compatibility, cache revalidation, Atlas-admission successors, and implementation/test
phasing. Production code remains frozen until this amended shared contract reaches
0 Blockers / 0 Majors.

## Problem

The first C16.1c implementation candidate treated a syntactically valid `source-authority-registry.json` placed inside the caller-selected fresh run directory as the host trust source. That is still first-writer trust-root selection: a caller can create the target directory and choose the registry bytes before generation zero exists. Pinned EGM drift review therefore invalidated candidate `fb18a4056abf6ee4be2c94c9773275882439e16b`.

The repair must give generation zero a C09 root whose provenance is independent of the run command, target path, package data, and candidate itself.

## Goals

- Every newly accepted B13 generation zero created through C16.1c carries an exact C09 registry record/digest and can cold-resolve `AcceptedRuntimeHost(...).source_authority()`.
- The caller cannot select the registry, its path, or its first writer through CLI, config, environment, target-directory contents, package data, or a runtime registry constructor.
- Existing #917 accepted-run authority semantics and #904/#926 independent genesis-trust, no-C05-bootstrap, retry/idempotence, and historical-read guarantees remain intact. #950 explicitly supersedes only #926's old absence-of-C09-at-gen0 assertion for newly C16.1c-born lineages.
- No C07 lease issuance/adoption and no neural/optimizer/teacher mutation are introduced.

## Non-goals

- Registry key rotation or migration after a lineage is born.
- Key generation, private-key custody, or source-rights issuance.
- A cross-platform general secret-management subsystem.
- Any CLI for installing or editing the host trust root.

## Proposed architecture

### Fixed host authority source

For new generation-zero C16.1c binding, the only production source of C09 registry bytes is the fixed host-administered system file:

`/etc/entif-ai/bilqis/source-authority-registry.json`

The path is a code constant owned by the host boundary. Production has no CLI flag, config field, environment override, run-directory fallback, package constructor, or public/private runtime registration API that accepts a registry or alternate path. Runtime code may only read and validate this file. It may not create, replace, repair, relocate, or populate it.

The host administrator provisions this file outside the Bilqis runtime/package process. A missing file is an authority-precondition failure, not an invitation for the runtime to create one.

The operator-facing logical path remains `/etc/entif-ai/bilqis/source-authority-registry.json`,
but the current supported runtime is Darwin/macOS, where `/etc` is the system-owned alias
for `/private/etc`. The reader MUST NOT follow that pathname generically. It opens `/`, then
traverses the expected physical components `private`, `etc`, `entif-ai`, and `bilqis`
fd-relatively with `O_DIRECTORY | O_NOFOLLOW`, and finally opens
`source-authority-registry.json` relative to the verified `bilqis` directory with
`O_RDONLY | O_NOFOLLOW`. It also verifies that the logical `/etc` alias resolves exactly to
`/private/etc`; any different alias/layout is unsupported by this leaf and fails closed.

Every traversed directory and the final file must be UID-0-owned and must not grant
group/world write through POSIX mode bits. The Darwin implementation additionally inspects
extended ACLs through a private libSystem ACL adapter and rejects any non-root ALLOW entry
that can mutate, replace, delete, relink, change ownership/security, or write attributes or
extended attributes on the checked directory/file. Deny-only ACLs may remain. The final
object must be a regular file, size `1.._MAX_REGISTRY_BYTES`, and contain a valid
`SourceAuthorityRegistry` record. Checks are performed on opened descriptors, not by a
check-then-open pathname sequence, so an ordinary process cannot win an ancestor/final-file
substitution race. Root/host-administrator compromise remains outside this leaf's threat
model.

### Generation-zero binding

`prepare_initial_generation` reads the fixed host registry before target publication,
validates the registry record, and inserts three owner-derived correction-frontier fields:

- `source_authority_registry`: the exact canonical registry record
- `source_authority_registry_sha256`: its digest
- `source_authority_registry_origin`: literal `HOST_SYSTEM_V1`

No caller argument controls this operation. The failed-candidate
`source_authority_run_dir` parameter is removed from `prepare_initial_generation`; the
`PreparedInitialGeneration.source_authority_run_dir` field is deleted; `_issue_binding` and
`_validate_candidate_source_authority` no longer accept a source-authority path; and the
publication target-path equality check is deleted rather than replaced. There is no new path
identity field: fixed host provenance is represented only by `HOST_SYSTEM_V1` plus the exact
registry record/digest in owner-derived custody.

Preparation performs the full Factory/B01/C09 replay before any publication work. B13 also
has a narrow C09-only replay that rereads the fixed host file and compares it with the
candidate's `HOST_SYSTEM_V1` tuple without consulting mutable Factory/source state. That
narrow replay runs before the generation-zero retry/pointer transaction on every publish
attempt. Consequently:

1. a first publish with missing/invalid/drifted host authority fails before the run-root
   publication lock/stage is created;
2. an unpointed retry of an already sealed generation zero rereads the host root before it
   may recreate acceptance or install a pointer, while preserving #904's ability to recover
   after the Factory source has advanced;
3. an already-pointed exact retry rereads the host root before it may return success or
   reconcile delivery; host drift therefore fails closed instead of silently reusing the
   accepted C09 authority.

The existing B13 sealed-genesis identity remains the retry oracle for everything except the
external C09 host root. `publication/retry.py` does not gain authority to choose a root;
the publication entry point gates all three retry cases with the narrow C09 replay before
entering retry mutation. `genesis_trust.py` remains the immutable seal and does not gain a
mutable host-path field.

If the fixed host registry is missing or invalid, new authoritative generation-zero preparation/publication fails before run mutation. A caller-created `<run_dir>/source-authority-registry.json` cannot satisfy this requirement and the fresh target remains subject to the existing empty/occupied-run rules.

### Accepted lineage and downgrade prevention

New C16.1c generation zero MUST carry `source_authority_registry_origin ==
"HOST_SYSTEM_V1"`; absence is never legal for newly prepared generation zero.

For every generation greater than zero, the authority branch is selected from the verified
currently accepted parent, never from the candidate. Before successor acceptance/publication,
the candidate must inherit the parent's source-authority tuple exactly except for one narrowly
authenticated historical #926 upgrade:

- `HOST_SYSTEM_V1` parent -> candidate must carry the same origin, registry record, and
  digest; then the fixed host root is reread and must still match;
- historical accepted parent whose origin field is genuinely absent and whose record/digest
  are already present -> candidate must omit the origin field and preserve that legacy tuple
  exactly; the existing #917 run-local root is then revalidated;
- verified pre-#950 historical parent whose origin, record, and digest are all genuinely absent
  -> candidate may remain unanchored or may perform the one-time #917 anchor by remaining
  origin-absent while adding exactly the currently provisioned run-local registry record/digest;
  after that anchor, descendants preserve the legacy tuple exactly;
- explicit JSON `null`, an unknown origin, a newly authored absent origin with no verified
  legacy parent, or any origin/record/digest downgrade/change -> reject before pointer
  mutation.

This rule applies equally to ordinary B13 successors and `AtlasAdmissionBinding` / C07
successors. The Atlas-admission branch may no longer return from publication authorization
before C09 inheritance and root revalidation have completed under the accepted-parent
boundary.

### Cold accepted runtime

`AcceptedRuntimeHost`/accepted execution-cache binding interprets
`source_authority_registry_origin == HOST_SYSTEM_V1` as a requirement to re-read the fixed
host registry and compare it to the accepted correction-frontier record/digest before issuing
or reusing `SourceAuthorityRuntime`.

Historical accepted lineages whose verified accepted artifact genuinely lacks the origin field
retain the existing #917 run-local provisioned-registry contract. Explicit `null` is invalid
and is not a spelling of legacy. This compatibility branch is based on authenticated accepted
custody metadata, not a caller switch.

All production consumers that currently call the run-local C09 registry helpers use one
custody-owned branch contract keyed only by authenticated correction-frontier metadata.
`source_authority_custody.py` exposes one locking resolver for callers that are not already
inside a legacy registry critical section. It behaves as follows:

- `HOST_SYSTEM_V1`: read/validate the fixed system root; acquire no run-local registry lock;
- field absent on authenticated legacy custody: acquire the existing run-local registry lock
  and run the existing #917 exact record/digest validator;
- explicit `null` or unknown origin: `BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID`.

The global order remains pointer lock -> legacy registry lock. No production caller acquires
the legacy registry lock and then the pointer lock. Cognitive-package staging therefore drops
its manual outer registry-lock acquisition: while holding the pointer lock it calls the unified
resolver, which conditionally acquires the legacy lock itself. System-host resolution takes no
run-local registry lock and has no writer.

Accepted execution-cache installation already runs under the pointer lock and calls the same
resolver on the loaded accepted student's correction frontier. Cache reuse/revalidation does
not add an origin field to the public `AcceptedExecutionCache` schema and does not change
`execution_cache.py`: while holding the pointer lock, `accepted_runtime.py` reloads/authenticates
the current accepted bundle, verifies it still matches the cache manifest/run/generation, then
passes that accepted correction frontier to the resolver and compares the returned registry to
the retained private registry/digest. Thus the branch always comes from accepted custody and a
stale cache cannot choose legacy/system behavior.

The same resolver/inheritance contract covers B13 successor publication, Atlas-admission
successor publication, `accept_and_publish`, accepted execution-cache install/revalidation,
and cognitive-package staging. Callers never choose the branch.

The correction-frontier sidecar remains schema
`bilqis.mlx.bamf-correction-frontier/v1`; C16.1c is an additive optional-field extension, not
a schema-version fork. Shape validation uses this literal table:

| origin field | registry record | digest | sidecar shape |
| --- | --- | --- | --- |
| absent | absent | absent | valid historical/unanchored shape; authority use cannot mint C09 |
| absent | present | matching present | valid legacy #917 shape |
| absent | only one present | any | invalid |
| `HOST_SYSTEM_V1` | valid present | matching present | valid system-host shape |
| `HOST_SYSTEM_V1` | either missing / mismatched | any | invalid / binding required |
| explicit `null` | any | any | invalid |
| any other value | any | any | invalid |

Shape validity alone never authorizes newly authored legacy custody. Generation-zero and
successor runtime rules above decide whether an absent field is historically admissible.

### Rotation semantics

C16.1c defines no live rotation. If the fixed host registry changes after a lineage is accepted,
that lineage fails closed at the next source-authority boundary because its accepted digest no
longer matches. A future governed migration must explicitly authorize any root transition.

The host administrator is a trusted external actor and MUST NOT rotate, replace, or relink the
fixed root concurrently with Bilqis operations under this leaf. Runtime revalidates immediately
before entering each relevant C09/B13 pointer transaction, but no cooperative host-admin lock
spans the final read through pointer commit. Therefore the guarantee is conditional: with the
no-concurrent-rotation precondition honored, drift between preparation and publication is
detected before pointer installation; if an administrator violates that precondition inside the
final-read/pointer TOCTOU window, the next C09/B13 authority boundary fails closed. A future
rotation protocol must define cross-process serialization before live rotation is supported.

## Alternatives considered

1. **Pre-existing registry in the fresh target run directory** — rejected. The caller selects the target and can become first writer; pinned EGM drift confirmed this violates C16.1c and recreates #917's attacker-first defect.
2. **Importable runtime/package provisioner accepting `SourceAuthorityRegistry`** — rejected. #917 already failed this architecture because the first same-process caller can install an attacker root.
3. **CLI/config/environment-selected registry path** — rejected. Moving selection into a path argument or environment variable does not create independent authority.
4. **Generic data-plane object/reference** — rejected. #904/#923 proof establishes that generic data-plane references cannot mint genesis trust; a caller-writable object store is not an authority root.
5. **Inherit from the source Factory run** — rejected as a universal C16.1c solution. The current first-student source contract can be a persisted Factory/admission run without accepted B13/C09 runtime custody, so no accepted source registry is guaranteed to exist there.
6. **Fixed host-administered system trust file** — selected. It removes per-run caller choice, requires independent host provisioning, preserves a simple canonical byte source, and composes with #917's existing registry validation without exposing a new registry-minting API.

## Failure semantics

Use the existing C09 custody reason vocabulary. Missing fixed host authority raises `BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED`; unsafe file shape/ownership/mode or malformed registry raises `BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID`; accepted-record/digest or re-read drift raises `BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH`; a missing record/digest for `HOST_SYSTEM_V1` raises `BAMF_C09_SOURCE_AUTHORITY_BINDING_REQUIRED`; unknown/inconsistent origin metadata raises `BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID`. No new caller-visible authority reason is invented unless implementation proves one of these cannot represent the boundary.

- Missing fixed host registry: fail before target mutation.
- Symlink, non-regular file, non-root ownership, group/world-writable permissions, malformed/noncanonical registry, or oversized content: fail before target mutation.
- Host registry changes between preparation and publication: under the explicit no-concurrent-
  rotation precondition, narrow C09 replay fails before pointer installation. A prohibited
  concurrent admin change in the final-read/pointer window is detected at the next boundary.
- Host registry changes after acceptance: cold/live source-authority binding fails closed; accepted generation remains historical evidence but cannot mint live C09 authority.
- Caller places a run-local registry on a fresh target: fresh-target occupancy rules reject it; even direct lower-level preparation never reads it for `HOST_SYSTEM_V1` authority.
- Historical run-local #917 lineage: continue validating against its accepted run-local root unless/until a separate governed migration changes that contract.

## Host-administrator operating contract

The operations docs must describe the privileged step rather than leaving it as folklore:

1. derive the registry record from the separately governed C09 key/rights source; Bilqis does
   not generate keys or decide rights;
2. create/verify the root-owned physical directory chain and reject unsafe POSIX/ACL grants;
3. install a complete temporary file in the same verified directory, `fsync` it, set root
   ownership and approved mode/ACL, then atomically rename it to the fixed final name and
   `fsync` the directory;
4. preserve the exact installed registry bytes/record/digest in the host backup/recovery
   procedure;
5. recovery for an accepted lineage is restore-the-exact-old-root or stop. Installing a new
   root is migration/rotation and is forbidden until a separate governed protocol authorizes it.

## V4 normative closure: exact host and custody contracts

This section supersedes any less-specific wording above. It is the implementation contract for
the remaining shared seams.

### Trusted-process boundary

The threat model trusts the integrity of the Bilqis Python package, interpreter process, and
loaded project code. Arbitrary in-process code execution, monkeypatching, debugger injection,
or replacement of private module globals is equivalent to compromise of the trusted Bilqis
process and is outside C16.1c. The guarantee is against ordinary callers that can invoke public
Bilqis APIs, choose run paths, create run-directory contents, set environment/configuration, or
control package payloads without already controlling the trusted process. Test-only patching of
private constants or syscall adapters exercises branches; it is not a supported authority
surface.

If hostile same-process code must be defended against later, the fixed-root reader must move
behind a separately protected process or OS capability boundary. This leaf does not claim that.

### Exact Darwin path and ACL adapter

Add one private Darwin-only module:

    bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_source_authority.py

It owns only host-filesystem verification. Its callable surface is exactly:

    HOST_SOURCE_AUTHORITY_LOGICAL_PATH = "/etc/entif-ai/bilqis/source-authority-registry.json"
    _HOST_SOURCE_AUTHORITY_COMPONENTS = (
        "private", "etc", "entif-ai", "bilqis", "source-authority-registry.json",
    )
    def open_host_source_authority_registry_fd(*, max_bytes: int) -> int: ...
    def read_extended_acl(fd: int) -> tuple[DarwinAclEntry, ...]: ...
    def require_safe_host_descriptor(fd: int, *, directory: bool) -> None: ...

DarwinAclEntry is a private frozen dataclass with:

    tag: Literal["ALLOW", "DENY"]
    principal_kind: Literal["UID", "GID"]
    principal_id: int
    permissions: frozenset[str]

The module loads libSystem.B.dylib privately and uses the Darwin C interfaces
acl_get_fd_np(fd, ACL_TYPE_EXTENDED), acl_get_entry, acl_get_tag_type,
acl_get_qualifier, acl_get_permset, acl_get_perm_np, acl_free, and
mbr_uuid_to_id. ID_TYPE_UID is 0; ID_TYPE_GID is 1. ACL entry iteration treats
acl_get_entry == 1 as an entry, 0 as end, and -1 as failure.

The current Darwin host was probed directly before implementation: both /private/etc and
/private/etc/hosts return NULL from acl_get_fd_np(fd, ACL_TYPE_EXTENDED) with errno ENOENT
when no extended ACL is present. Therefore read_extended_acl has one and only one successful
NULL-handle case: NULL plus errno == ENOENT returns the empty tuple. NULL with any other errno
fails closed. Once an ACL handle is returned, qualifier or permset failure, unknown tag, failed
UUID resolution, unexpected ID type, acl_get_entry == -1, or any other libSystem error fails
closed with BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID.

The mutation permission set is exactly:

    ACL_WRITE_DATA
    ACL_APPEND_DATA
    ACL_DELETE
    ACL_DELETE_CHILD
    ACL_WRITE_ATTRIBUTES
    ACL_WRITE_EXTATTRIBUTES
    ACL_WRITE_SECURITY
    ACL_CHANGE_OWNER

Darwin aliases ACL_ADD_FILE to ACL_WRITE_DATA and ACL_ADD_SUBDIRECTORY to
ACL_APPEND_DATA, so those are covered. DENY entries do not grant authority and may remain.
An ALLOW entry intersecting the mutation set is accepted only when its principal resolves to
principal_kind == "UID" and principal_id == 0. Mutating ALLOW entries for a group,
including gid 0, an unresolved principal, or any non-root UID reject. Non-mutating/read-only
ALLOW entries may remain.

open_host_source_authority_registry_fd(max_bytes=...) rejects a non-positive max_bytes and
verifies /etc without treating a Python-resolved
pathname as authority:

1. lstat("/etc") must report a UID-0 symlink.
2. readlink("/etc") must equal the exact relative target "private/etc".
3. Open "/" as the anchor directory and call require_safe_host_descriptor on that fd with
   directory=True.
4. Open private, then etc, then entif-ai, then bilqis fd-relatively with
   O_RDONLY | O_DIRECTORY | O_NOFOLLOW.
5. For each opened directory call require_safe_host_descriptor(..., directory=True).
6. Compare st_dev and st_ino of the fd-opened physical private/etc directory with
   stat("/etc"); mismatch rejects.
7. Open the final registry fd relative to verified bilqis with O_RDONLY | O_NOFOLLOW;
   call require_safe_host_descriptor(..., directory=False).

require_safe_host_descriptor uses fstat: expected directory or final regular-file type,
st_uid == 0, no S_IWGRP | S_IWOTH, and the ACL rule above. The final file additionally
requires size 1..max_bytes as supplied to the opener. All opened fds are closed on every
failure path.

The ordinary no-extended-ACL case is the observed NULL + ENOENT result above or an otherwise
successful enumeration containing zero entries. No other errno is interpreted as absence.

### Exact custody API

source_authority_custody.py owns the semantic branch and exposes these production-private
functions:

    HOST_SYSTEM_SOURCE_AUTHORITY_ORIGIN = "HOST_SYSTEM_V1"
    def read_host_system_source_authority_registry() -> SourceAuthorityRegistry: ...
    def resolve_source_authority_registry(
        run_dir: Path,
        correction_frontier: Mapping[str, object],
    ) -> SourceAuthorityRegistry | None: ...
    def require_source_authority_successor_inheritance(
        run_dir: Path,
        parent_frontier: Mapping[str, object],
        candidate_frontier: Mapping[str, object],
    ) -> SourceAuthorityRegistry | None: ...

read_host_system_source_authority_registry() calls the Darwin fd opener with the existing
source_authority_custody.py constant `_MAX_REGISTRY_BYTES`, reads exactly the already-bounded
bytes from that fd, closes the fd in a `finally` path, parses `SourceAuthorityRegistry`,
and never accepts a path argument. The registry byte-limit constant remains owned in
`source_authority_custody.py`; the Darwin module does not duplicate it.

resolve_source_authority_registry() requires that its caller is already operating on
authenticated custody when the frontier is being used as authority. The resolver itself does
not acquire the B13 pointer lock. It owns any legacy registry lock it needs:

- origin HOST_SYSTEM_V1: require record+digest, read fixed host registry, exact-match it,
  acquire no run-local registry lock;
- origin field genuinely absent + record+digest both present: acquire
  source_authority_registry_lock(run_dir) and run the existing legacy exact-match check;
- origin genuinely absent + both record/digest absent: return None only for historical
  read compatibility; it cannot mint C09 runtime authority;
- explicit null, unknown origin, half-binding, or digest mismatch: reject.

No production caller using resolve_source_authority_registry() may already hold the legacy
registry lock. The only retained unlocked legacy helper is private to the legacy-lock
implementation. The global nesting remains B13 pointer lock -> resolver -> optional legacy
registry lock.

require_source_authority_successor_inheritance() is the single authenticated-parent successor
gate. Its caller already holds the B13 pointer lock and MUST NOT hold the legacy registry lock.
It owns any legacy registry lock required by the branch and returns the trusted registry used by
the successor, or None only for a verified historical unanchored lineage that remains
unanchored.

Its branch table is exact:

- parent HOST_SYSTEM_V1 + exact record/digest: candidate must carry the identical
  HOST_SYSTEM_V1/record/digest tuple; re-read and exact-match the fixed host registry; return it;
- parent origin genuinely absent + record/digest both present: candidate must carry the exact
  same absent-origin legacy record/digest tuple; acquire the legacy run-local registry lock,
  exact-match that provisioned #917 registry, and return it;
- parent origin genuinely absent + record/digest both absent: this is the narrowly authenticated
  historical #926 unanchored state. The candidate may either:
  1. remain origin-absent + record/digest absent, returning None; or
  2. perform the one-time historical #917 anchor by remaining origin-absent while adding both a
     registry record and matching digest. In that case acquire the legacy run-local registry
     lock, require the candidate tuple to equal the currently provisioned run-local registry
     exactly, and return that registry.
- once the historical anchor above succeeds, every later descendant is the ordinary legacy
  exact-inheritance branch; it cannot change registry bytes/digest without a separately governed
  migration;
- explicit null, unknown origin, half-binding, HOST_SYSTEM_V1 introduced from an unanchored or
  legacy parent, removal of a HOST/legacy binding, or any other tuple change rejects.

This is the only exception to exact parent->child tuple equality, and it exists solely to
preserve #926's pre-#950 behavior where lawful generation zero was intentionally C09-unanchored
and the first retained successor could bind the #917 run-local registry. It cannot be used by a
new C16.1c-born generation zero because those are unconditionally HOST_SYSTEM_V1.

### Exact publication and admission ownership

publication/authority.py::validate_parent_transition(...) changes its return value from None
to CompleteStudent | None: None for generation zero, otherwise the exact parent bundle that it
already loads and validates against the live pointer. It remains the owner of parent identity
and transition validation.

publication/__init__.py::_publish_authorized_generation(...) consumes that returned
authenticated parent inside the final pointer transaction. Before any authority-type-specific
branch, including AtlasAdmissionBinding, it:

1. calls require_source_authority_successor_inheritance(
   run_dir, parent.correction_frontier, candidate.correction_frontier);
2. requires the returned registry digest, when present, to equal the candidate frontier digest.

Only after those checks may the existing ordinary-vs-Atlas authority-specific logic continue.
Thus ordinary and Atlas publication share one C09 parent gate and no candidate metadata selects
the branch.

admission.py::accept_and_publish(...) performs the same read-only inheritance/root check
against load_accepted_generation(run_dir) before minting the ordinary acceptance binding so
the binding's registry digest is not self-asserted by the candidate. B13 publication repeats
the check under its final pointer transaction; this repetition is intentional TOCTOU defense.
publish_atlas_admission_generation(...) does not mint an ordinary acceptance binding and
relies on the same final B13 parent gate before its Atlas-specific branch.

No separate inheritance-result object is introduced: the authenticated-parent successor gate
returns `SourceAuthorityRegistry | None`; the authenticated parent object remains the existing
`CompleteStudent`.

### Exact generation>0 already-pointed retry custody

The shared parent gate above covers the normal state where the live pointer still names
candidate.generation - 1. B13 also has a lawful exact-retry state where the live pointer already
names candidate.generation. That state has a separate custody proof and MUST NOT be forced
through validate_parent_transition, whose live-pointer precondition is the parent generation.

Add this private helper to publication/authority.py:

    def validate_current_successor_retry(
        run_dir: Path,
        current: dict,
        candidate: BamfBundleCandidate,
        authority: AcceptedCandidateBinding | AtlasAdmissionBinding,
        *,
        load_bundle,
        require_published_acceptance,
    ) -> tuple[CompleteStudent, CompleteStudent]:
        ...

It is called only while the B13 pointer lock is held and only after the existing retry branch has
proved current.run_id, current.generation, current.manifest_sha256,
current.parent_manifest_sha256, current.schema, and current.acceptance_sha256 exactly match the
candidate/digest/authority being retried.

The helper then:

1. loads the current accepted child from current["bundle"] at current["manifest_sha256"];
2. requires child run/generation/parent identity to equal the current pointer and candidate;
3. calls require_published_acceptance(run_dir, current, child), requires the parsed binding
   digest to equal authority.digest, and requires its parent_candidate_identity_sha256 to equal
   authority.parent_candidate_identity_sha256;
4. loads the historical parent bundle by child.parent_manifest_sha256 from bamf-bundles;
5. requires parent.run_id == child.run_id, parent.generation + 1 == child.generation, and
   parent.run_identity == child.run_identity;
6. requires authority.parent_candidate_identity_sha256 ==
   candidate_identity_digest(parent.retained_state);
7. returns (child, parent).

This proof deliberately uses the accepted current child's immutable parent manifest hash plus
the accepted child's parent-candidate identity binding. It does not require the historical
parent to be the live pointer, and it does not invent a second current-pointer fiction.

In publication/__init__.py's already-pointed generation>0 branch, before deleting the stage,
rewriting/reconciling acceptance, reconciling the outbox, or returning:

1. call validate_current_successor_retry(...);
2. call require_source_authority_successor_inheritance(
   run_dir, parent.correction_frontier, child.correction_frontier);
3. when a registry is returned, require its digest to equal the child's accepted
   source_authority_registry_sha256.

Only then may the existing exact retry reconcile/return. This applies identically to ordinary
AcceptedCandidateBinding and AtlasAdmissionBinding retries. A HOST root drift therefore blocks
an already-pointed retry before reconcile/return; a verified historical legacy parent continues
through the legacy resolver.

### Phase-stable accepted-runtime ownership

The accepted-runtime and cache cutover is part of Phase B, not Phase C. Phase B is not complete
until a newly created HOST_SYSTEM_V1 generation zero can be loaded and revalidated through
AcceptedRuntimeHost without any run-local C09 file.

accepted_runtime.py changes both cache install and cache reuse:

- while holding _pointer_lock, load and authenticate the current accepted bundle with
  _read_accepted_locked;
- resolve from that accepted student's correction frontier with
  resolve_source_authority_registry;
- compare the returned registry and accepted digest with the retained private cache entry;
- never call read_provisioned_source_authority_registry(run_dir) directly during cache reuse.

execution_cache.py remains unchanged. No origin selector is copied into the public cache schema.

### Conditional drift guarantee

Every claim that host-root drift between preparation and pointer publication is rejected before
pointer mutation is conditional on the explicit host-admin precondition that the root is not
rotated, replaced, or relinked concurrently with Bilqis operations. There is intentionally no
cross-process lock spanning final host-root read through pointer commit. If the trusted host
administrator violates that precondition inside that window, a commit may complete and the
next C09/B13 authority boundary detects the mismatch. C16.1c does not claim otherwise.

### Recovery boundary

Recovery restores the exact old registry content into a newly verified safe fixed-host boundary:
the physical directory chain, final owner, POSIX mode, ACLs, file type, and size must all pass
the same live reader before the restored bytes may satisfy an accepted lineage. Possessing the
old bytes or digest alone is insufficient.

## Implementation locations

- Add `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_source_authority.py` with the exact private fd/ACL contract above.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/source_authority_custody.py` with the exact fixed-host reader, accepted-custody resolver, and authenticated-parent successor gate above while preserving the legacy run-local reader/lock behind those custody functions.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/sidecar_contracts.py`: distinguish genuinely absent origin from explicit null; validate unanchored historical absence, legacy absence+record+digest, and exact `HOST_SYSTEM_V1` according to the literal table above.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/preparation.py` and `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/preparation_authority.py`: delete `source_authority_run_dir` from signatures/state, bind the fixed host root unconditionally for new gen0, and expose the narrow C09 replay used by publication retry.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/publication/__init__.py`: run narrow C09 replay before every gen0 retry transaction; remove target-path identity checks; and run the shared accepted-parent C09 gate before every generation>0 authority-specific branch.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/publication/authority.py`: return the authenticated parent `CompleteStudent | None` from `validate_parent_transition` as specified above.
- `bilqis_mlx/runtime/_custody/bamf_bundle/publication/retry.py` and `bilqis_mlx/runtime/_custody/bamf_bundle/publication/genesis_trust.py` are regression-read surfaces only and remain byte-unchanged unless implementation proves their existing signatures cannot support the reviewed entry-point gate. Such a required change is a design amendment.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/accepted_runtime.py` in Phase B: cache install/reuse reloads authenticated accepted custody and uses the unified resolver. `bilqis_mlx/runtime/_custody/bamf_bundle/execution_cache.py` remains byte-unchanged.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/admission.py`: ordinary acceptance validates exact accepted-parent inheritance/root before minting its binding.
- Modify `bilqis_mlx/runtime/cognitive_package/operator.py`: remove its manual outer legacy-registry lock and, while retaining pointer-lock ownership, use the unified resolver.
- Modify `bilqis_mlx/runtime/bamf_first_student.py`: remove the failed target-run trust argument.
- Modify `bilqis_mlx/runtime/_bamf_first_student_support.py`: restore ordinary absent-or-empty target semantics by removing the special allowance for `SOURCE_AUTHORITY_REGISTRY_FILE` and `SOURCE_AUTHORITY_REGISTRY_LOCK`.
- Update `docs/operations/BAMF_0_2_FIRST_STUDENT.md` and `docs/operations/BAMF_0_2_PACKAGES.md` to distinguish system-host genesis authority from historical run-local custody.
- Add or modify only the exact focused tests listed by phase below. Private syscall/stat/ACL seams may be patched in tests; no alternate production path selector is introduced.

## Stable implementation phases and exact focused proof

### Phase A: host reader, resolver, sidecar

Production scope:

- `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_source_authority.py` (new)
- `bilqis_mlx/runtime/_custody/bamf_bundle/source_authority_custody.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/sidecar_contracts.py`

Test scope:

- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_host_source_authority_custody.py` (new)
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/test_sidecar_contracts.py`

Prove
fd-relative `O_NOFOLLOW` traversal, expected `/etc` -> `/private/etc` alias, regular-file and
size bounds, UID-0 and POSIX-mode rejection, unsafe Darwin ACL rejection, malformed registry,
origin validation table, legacy locking, ALLOW/DENY handling, UID/GID/unresolved principals,
every named mutation right, empty ACL, ACL API failure, raw `/etc` symlink mismatch, physical
inode mismatch, writable/symlinked ancestors, and fd cleanup. UID/ACL logic is tested at the
private descriptor-metadata/libSystem adapter boundary rather than pretending an ordinary temp
file is root-owned; symlink, nonregular, mode, size, malformed-content and ancestor-substitution
cases use real filesystem fixtures. A privileged opt-in host smoke may read an actually
installed root, but is not a CI precondition.

Phase-A gate:

    ../Bilqis-485-venv/bin/python -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_host_source_authority_custody.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/test_sidecar_contracts.py
    python3 scripts/check_module_size.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    python3 scripts/code_smell_audit.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    git diff --check

### Phase B: generation-zero bind and retry gate

Production scope:

- `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/preparation.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/preparation_authority.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/publication/__init__.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/accepted_runtime.py`
- `bilqis_mlx/runtime/bamf_first_student.py`
- `bilqis_mlx/runtime/_bamf_first_student_support.py`

Regression-read, no planned edit:

- `bilqis_mlx/runtime/_custody/bamf_bundle/publication/retry.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/publication/genesis_trust.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/execution_cache.py`

Test scope:

- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_c09_source_authority.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_preparation_authority.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_retry.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_authority.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_cold_trust.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_source_authority.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/test_accepted_runtime_custody.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/test_accepted_runtime_recovery.py`
- `bilqis_mlx/runtime/tests/test_bamf_first_student.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/helpers.py`

Prove new gen0
always carries `HOST_SYSTEM_V1`; `source_authority_run_dir` is gone; missing/unsafe/drifted
host root rejects before target publication mutation; full first publish still replays
Factory/B01 authority; sealed unpointed/already-pointed retry revalidates only C09 and therefore
still recovers after Factory advance; host drift after seal cannot install/return a pointer;
and a HOST gen0 is immediately usable/revalidatable through accepted-runtime cache ownership
without a run-local registry file.

The shared test helper `genesis_preparation()` removes its
`source_authority_run_dir` override. It enters an explicit private test context that patches
only `read_host_system_source_authority_registry()` to return the canonical test registry.
Individual adversarial tests that exercise missing, invalid, or drifted host custody bypass or
override that helper context deliberately. This is test-only substitution of the private host
reader, not a production path or registry selector.

Phase-B gate:

    ../Bilqis-485-venv/bin/python -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_c09_source_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_preparation_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_retry.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_cold_trust.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_source_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/test_accepted_runtime_custody.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/test_accepted_runtime_recovery.py bilqis_mlx/runtime/tests/test_bamf_first_student.py
    python3 scripts/check_module_size.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    python3 scripts/code_smell_audit.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    git diff --check

### Phase C: accepted-parent consumer cutover

Production scope:

- `bilqis_mlx/runtime/_custody/bamf_bundle/publication/authority.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/publication/__init__.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/admission.py`
- `bilqis_mlx/runtime/cognitive_package/operator.py`

Test scope:

- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_core.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_isolation.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_publication.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/test_accepted_ingress_currentness.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_authority.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_custody.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_history.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_sources.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_atlas_admission_publication.py`
- `bilqis_mlx/runtime/cognitive_package/tests/test_adoption.py`
- `bilqis_mlx/runtime/cognitive_package/tests/test_adoption_recovery.py`
- `bilqis_mlx/runtime/cognitive_package/tests/test_operator.py`
- `bilqis_mlx/runtime/cognitive_package/tests/test_receiver_custody.py`
- `bilqis_mlx/runtime/cognitive_package/tests/test_staging.py`

Prove
HOST descendants cannot omit/null/change origin or registry tuple; Atlas-admission successors
also revalidate the fixed root; legacy descendants are accepted only from verified legacy
parents; cache reuse reloads accepted metadata; pointer -> legacy-registry lock ordering remains;
system-host reads take no run-local registry lock; two runs sharing one host root still cannot
exchange opaque capabilities; post-acceptance root drift disables mint/reuse and package staging;
and already-pointed exact retries for both ordinary and Atlas successors authenticate the current
child plus referenced historical parent, reject HOST drift before reconcile/return, and preserve
verified legacy retry compatibility. A verified pre-#950 unanchored parent may bind exactly the
currently provisioned #917 run-local registry on its first retained successor; forged HOST
upgrade, explicit-null origin, half-binding, or later legacy registry replacement rejects.

Phase-C gate:

    ../Bilqis-485-venv/bin/python -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_core.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_isolation.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_publication.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/test_accepted_ingress_currentness.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_custody.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_history.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_generation_acceptance_sources.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/acceptance/test_atlas_admission_publication.py bilqis_mlx/runtime/cognitive_package/tests/test_adoption.py bilqis_mlx/runtime/cognitive_package/tests/test_adoption_recovery.py bilqis_mlx/runtime/cognitive_package/tests/test_operator.py bilqis_mlx/runtime/cognitive_package/tests/test_receiver_custody.py bilqis_mlx/runtime/cognitive_package/tests/test_staging.py
    python3 scripts/check_module_size.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    python3 scripts/code_smell_audit.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    git diff --check

### Phase D: first-student and regression closure

Production scope: no new runtime semantics. Phase D is documentation and regression closure.

Documentation scope:

- `docs/operations/BAMF_0_2_FIRST_STUDENT.md`
- `docs/operations/BAMF_0_2_PACKAGES.md`

Additional test scope:

- `bilqis_mlx/runtime/tests/test_bamf_foundation_dashboard_projection.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication_durability.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication_recovery.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication_rejection.py`

Phase B already restored normal absent/empty fresh-target rules and replaced the failed
pre-provisioned-target positive test. Phase D updates operations docs/admin recovery procedure
and then runs
the #917 authority ring, #904/#923/#926 genesis regressions, no-C05-genesis proof, no-C07 and
no-neural-mutation assertions, structural/governance/error-control gates, and the differential
leaf gate with inherited baseline failures reported rather than edited.

Phase-D focused gate:

    ../Bilqis-485-venv/bin/python -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_host_source_authority_custody.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_core.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_isolation.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_source_authority_runtime_publication.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_c09_source_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_preparation_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_retry.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_cold_trust.py bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/genesis/test_generation_zero_source_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication.py bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication_durability.py bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication_recovery.py bilqis_mlx/runtime/tests/custody/bamf_bundle/publication/test_publication_rejection.py bilqis_mlx/runtime/tests/test_bamf_first_student.py bilqis_mlx/runtime/tests/test_bamf_foundation_dashboard_projection.py
    python3 scripts/check_module_size.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    python3 scripts/code_smell_audit.py --changed-from 0338f334388a01389163fb0cba74614c2bcdb83a
    python3 scripts/quality/check_governance_integrity.py --base-ref 0338f334388a01389163fb0cba74614c2bcdb83a
    python3 -B scripts/check_bamf_flow_control.py
    python3 -B scripts/error_control_plane.py --check --base-ref 0338f334388a01389163fb0cba74614c2bcdb83a
    python3 -B scripts/verify_bamf_0_2_contracts.py
    git diff --check

Only after the focused/structural gates are green run the leaf aggregate with
`BILQIS_QUALITY_BASE_REF=0338f334388a01389163fb0cba74614c2bcdb83a`; preserve the two
known inherited evidence failures as baseline debt if they remain byte-identical to base.

## Acceptance proof

- New generation zero always binds `HOST_SYSTEM_V1` plus exact registry record/digest from the fixed host file.
- Missing fixed host file rejects before any new run pointer/bundle/lease mutation.
- Caller-created run-local registry cannot establish gen0 authority.
- No public/package/CLI/config/environment path or raw-registry provisioner exists.
- Fixed host root drift between prepare/publish rejects before pointer mutation when the
  explicit no-concurrent-host-rotation precondition is honored. A prohibited administrator
  change inside the final-read/pointer window may commit and is detected at the next
  C09/B13 authority boundary.
- Fixed host root drift after acceptance prevents `SourceAuthorityRuntime` mint/reuse.
- Crash after genesis trust seal but before pointer, followed by missing/drifted host root,
  cannot recover/install the pointer; restoring the exact old root permits exact retry even if
  Factory source state has advanced.
- Ordinary and `AtlasAdmissionBinding` successors inherit the accepted parent's exact
  origin/record/digest tuple and revalidate its selected root; a HOST lineage cannot downgrade
  to absent/null legacy metadata.
- The sole historical exception is a verified pre-#950 parent with genuinely absent origin,
  record, and digest: its first retained successor may remain origin-absent while adding exactly
  the currently provisioned #917 run-local registry record/digest. Later descendants inherit
  that legacy tuple exactly.
- Two different fresh run roots on the same host may bind the same fixed root but their opaque runtime capabilities remain run/cache-bound and non-interchangeable.
- Exact cold resume reconstructs the same accepted C09 authority without caller input.
- Existing #917 attacker-first, forged capability, foreign capability, stale generation, wrong-scope/wrong-key, retry, and historical-read tests remain green.
- Existing #904/#923 generation-zero trust and no-C05-genesis invariants remain green.
- #950 explicitly supersedes only #926's historical assertion that current generation zero has no C09 registry digest. The #926 regression is amended for C16.1c-born lineages to require `HOST_SYSTEM_V1` + exact registry record/digest at generation zero while preserving its no-C05-bootstrap, authenticated run-identity, and successor-lineage guarantees. Historical pre-#950 generations remain readable under their recorded custody.
- No C07 lease/adoption or neural/optimizer/teacher mutation occurs.

## Risks and limits

- The host must perform a one-time privileged configuration step outside Bilqis runtime. Absence intentionally blocks new authoritative gen0 creation.
- `/etc/entif-ai/bilqis/...` is the operator-facing macOS contract; runtime traversal is pinned
  to the verified `/private/etc/...` physical chain described above. A future non-Darwin port
  needs an explicitly governed equivalent rather than an environment override.
- This leaf trusts the host administrator/UID 0 boundary. It does not defend against a malicious root administrator or concurrent out-of-band root rotation; rotation is prohibited until separately governed.
- Root rotation is intentionally unsupported by this leaf and fails closed.
- Tests may patch private syscall/stat/ACL seams and the private fixed-path constant in isolated
  fixtures; those substitutions must never become production configurability.
