# C16.1c host trust-source repair proposal

Status: PROPOSED v3 / fresh EGM re-review required before implementation.

Review note: v3 closes the fresh-v2 EGM findings around host path custody, lineage
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
the candidate must inherit the parent's source-authority tuple exactly:

- `HOST_SYSTEM_V1` parent -> candidate must carry the same origin, registry record, and
  digest; then the fixed host root is reread and must still match;
- historical accepted parent whose origin field is genuinely absent -> candidate must also
  omit the origin field and preserve the parent's registry-record/digest state exactly; the
  existing #917 run-local root is then revalidated;
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

## Implementation locations

- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/source_authority_custody.py`: add the fixed system-host path/reader, UID/mode/file-shape validation, `HOST_SYSTEM_V1` origin handling, and unified authoritative-registry resolver while preserving legacy run-local validation/locking.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/preparation.py` and `preparation_authority.py`: delete `source_authority_run_dir` from signatures/state, bind the fixed host root unconditionally for new gen0, and expose the narrow C09 replay used by publication retry.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/accepted_runtime.py`: choose fixed-host versus legacy run-local root strictly from authenticated accepted custody for cache install and revalidation; reload accepted custody on cache reuse. `execution_cache.py` is intentionally unchanged.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/publication/__init__.py`: run narrow C09 replay before every gen0 retry transaction; remove target-path identity checks; and enforce accepted-parent origin/record/digest inheritance plus root revalidation for every generation>0 path, including `AtlasAdmissionBinding`.
- `bilqis_mlx/runtime/_custody/bamf_bundle/publication/retry.py` and `publication/genesis_trust.py` retain their sealed-genesis identity roles. No new host selector is added there; regression tests prove their mutation paths are gated by the publication entry point's C09 replay. If implementation cannot preserve those signatures, that is a design amendment, not an implementation improvisation.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/admission.py`: acceptance consumes the authenticated-parent inheritance/result rather than allowing candidate metadata to select legacy/system authority.
- Modify `bilqis_mlx/runtime/cognitive_package/operator.py`: preserve pointer-locked source-root revalidation while resolving system-vs-legacy authority from accepted custody rather than assuming a run-local file. The existing run-local lock remains for legacy custody; the fixed-host path is read-only and has no runtime writer.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/sidecar_contracts.py`: validate `source_authority_registry_origin` as absent/legacy or exact `HOST_SYSTEM_V1`, and require record+digest when system-host origin is present.
- Modify `bilqis_mlx/runtime/bamf_first_student.py` / private support: restore absent-or-empty fresh target semantics; do not allow pre-existing registry files to bootstrap authority.
- Update `docs/operations/BAMF_0_2_FIRST_STUDENT.md` and `docs/operations/BAMF_0_2_PACKAGES.md` to distinguish system-host genesis authority from historical run-local custody.
- Update focused tests explicitly listed below. Private syscall/stat/ACL seams may be patched in tests; no alternate production path selector is introduced.

## Stable implementation phases and exact focused proof

### Phase A: host reader, resolver, sidecar

Change only `source_authority_custody.py`, `sidecar_contracts.py`, and focused tests. Prove
fd-relative `O_NOFOLLOW` traversal, expected `/etc` -> `/private/etc` alias, regular-file and
size bounds, UID-0 and POSIX-mode rejection, unsafe Darwin ACL rejection, malformed registry,
origin validation table, and legacy locking. UID/ACL logic is tested at the private descriptor-
metadata adapter boundary rather than pretending an ordinary temp file is root-owned; symlink,
nonregular, mode, size, malformed-content and ancestor-substitution cases use real filesystem
fixtures. A privileged opt-in host smoke may read an actually installed root, but is not a CI
precondition.

Focused files:

- `bilqis_mlx/runtime/tests/custody/bamf_bundle/contracts/test_sidecar_contracts.py`
- new or existing focused custody tests under
  `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/`

### Phase B: generation-zero bind and retry gate

Change genesis preparation/preparation-authority and publication entry wiring. Prove new gen0
always carries `HOST_SYSTEM_V1`; `source_authority_run_dir` is gone; missing/unsafe/drifted
host root rejects before target publication mutation; full first publish still replays
Factory/B01 authority; sealed unpointed/already-pointed retry revalidates only C09 and therefore
still recovers after Factory advance; host drift after seal cannot install/return a pointer.

Focused files:

- `.../contracts/genesis/test_generation_zero_c09_source_authority.py`
- `.../contracts/genesis/test_generation_zero_preparation_authority.py`
- `.../contracts/genesis/test_generation_zero_retry.py`
- `.../contracts/genesis/test_generation_zero_authority.py`
- `.../contracts/genesis/test_generation_zero_cold_trust.py`
- `.../contracts/genesis/test_generation_zero_source_authority.py`
- `.../publication/test_publication.py`

### Phase C: accepted-parent consumer cutover

Change successor publication, admission, accepted runtime, and cognitive-package staging. Prove
HOST descendants cannot omit/null/change origin or registry tuple; Atlas-admission successors
also revalidate the fixed root; legacy descendants are accepted only from verified legacy
parents; cache reuse reloads accepted metadata; pointer -> legacy-registry lock ordering remains;
system-host reads take no run-local registry lock; two runs sharing one host root still cannot
exchange opaque capabilities; post-acceptance root drift disables mint/reuse and package staging.

Focused files:

- all tests in `.../authority/source_authority_runtime/`
- `.../authority/test_accepted_runtime_custody.py`
- `.../authority/test_accepted_runtime_recovery.py`
- `.../authority/test_accepted_ingress_currentness.py`
- `.../contracts/acceptance/test_generation_acceptance.py`
- `.../contracts/acceptance/test_atlas_admission_publication.py`
- `bilqis_mlx/runtime/cognitive_package/tests/adoption_harness.py` plus the package adoption/
  recovery tests that exercise `_stage_received_package_if_current`

### Phase D: first-student and regression closure

Restore normal absent/empty fresh-target rules, replace the failed pre-provisioned-target positive
test with fixed-host authority tests, update operations docs/admin recovery procedure, then run
the #917 authority ring, #904/#923/#926 genesis regressions, no-C05-genesis proof, no-C07 and
no-neural-mutation assertions, structural/governance/error-control gates, and the differential
leaf gate with inherited baseline failures reported rather than edited.

Focused files include `bilqis_mlx/runtime/tests/test_bamf_first_student.py` and
`bilqis_mlx/runtime/tests/test_bamf_foundation_dashboard_projection.py` in addition to the
rings above.

## Acceptance proof

- New generation zero always binds `HOST_SYSTEM_V1` plus exact registry record/digest from the fixed host file.
- Missing fixed host file rejects before any new run pointer/bundle/lease mutation.
- Caller-created run-local registry cannot establish gen0 authority.
- No public/package/CLI/config/environment path or raw-registry provisioner exists.
- Fixed host root drift between prepare/publish rejects before pointer mutation.
- Fixed host root drift after acceptance prevents `SourceAuthorityRuntime` mint/reuse.
- Crash after genesis trust seal but before pointer, followed by missing/drifted host root,
  cannot recover/install the pointer; restoring the exact old root permits exact retry even if
  Factory source state has advanced.
- Ordinary and `AtlasAdmissionBinding` successors inherit the accepted parent's exact
  origin/record/digest tuple and revalidate its selected root; a HOST lineage cannot downgrade
  to absent/null legacy metadata.
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
