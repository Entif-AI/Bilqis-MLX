# C16.1c host trust-source repair proposal

Status: PROPOSED / EGM review required before implementation.

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

The fixed-host reader must open the final file with `O_NOFOLLOW`, require a regular file owned by UID 0, reject group/world-writable mode bits, reject empty or oversized content, and parse the existing canonical `SourceAuthorityRegistry` record. These checks establish the local host-administrator boundary assumed by this leaf; same-process callers running as the ordinary Bilqis user cannot manufacture a trusted file merely by choosing bytes. Root/host-administrator compromise is outside this leaf's threat model.

### Generation-zero binding

`prepare_initial_generation` reads the fixed host registry before target publication, validates the canonical registry record, and inserts three owner-derived correction-frontier fields:

- `source_authority_registry`: the exact canonical registry record
- `source_authority_registry_sha256`: its digest
- `source_authority_registry_origin`: literal `HOST_SYSTEM_V1`

No caller argument controls this operation. Immediately before generation-zero publication, B13 rereads the same fixed host file and requires exact record/digest equality. Rotation or replacement between preparation and publication fails before the generation pointer is installed.

If the fixed host registry is missing or invalid, new authoritative generation-zero preparation/publication fails before run mutation. A caller-created `<run_dir>/source-authority-registry.json` cannot satisfy this requirement and the fresh target remains subject to the existing empty/occupied-run rules.

### Cold accepted runtime

`AcceptedRuntimeHost`/accepted execution-cache binding interprets `source_authority_registry_origin == HOST_SYSTEM_V1` as a requirement to re-read the fixed host registry and compare it to the accepted correction-frontier record/digest before issuing or reusing `SourceAuthorityRuntime`.

Historical accepted lineages that do not carry `HOST_SYSTEM_V1` retain the existing #917 run-local provisioned-registry contract. This is an explicit compatibility branch based on accepted custody metadata, not a caller switch.

All production consumers that currently call the run-local C09 registry helpers must use one custody-owned resolver keyed only by accepted correction-frontier metadata. That includes B13 successor publication, `accept_and_publish`, accepted execution-cache installation/revalidation, and cognitive-package staging. `HOST_SYSTEM_V1` resolves and revalidates the fixed system root; legacy/no-marker custody retains the existing run-local resolver and lock. Callers never choose this branch.

The correction-frontier validator accepts only `None` (legacy) or literal `HOST_SYSTEM_V1` as `source_authority_registry_origin`. `HOST_SYSTEM_V1` requires both registry record and matching digest. Unknown origin values reject.

### Rotation semantics

C16.1c defines no live rotation. If the fixed host registry changes after a lineage is accepted, that lineage fails closed at the next source-authority boundary because its accepted digest no longer matches. A future governed migration must explicitly authorize any root transition.

The host administrator is a trusted external actor and must not rotate the fixed root concurrently with Bilqis operations under this leaf. Runtime revalidates the fixed root at each existing C09/B13 authority boundary; it does not claim to serialize a malicious or concurrent root administrator. A future rotation protocol must define cross-process serialization before live rotation is supported.

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
- Host registry changes between preparation and publication: fail before pointer installation.
- Host registry changes after acceptance: cold/live source-authority binding fails closed; accepted generation remains historical evidence but cannot mint live C09 authority.
- Caller places a run-local registry on a fresh target: fresh-target occupancy rules reject it; even direct lower-level preparation never reads it for `HOST_SYSTEM_V1` authority.
- Historical run-local #917 lineage: continue validating against its accepted run-local root unless/until a separate governed migration changes that contract.

## Implementation locations

- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/source_authority_custody.py`: add the fixed system-host path/reader, UID/mode/file-shape validation, `HOST_SYSTEM_V1` origin handling, and unified authoritative-registry resolver while preserving legacy run-local validation/locking.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/genesis/preparation.py` and `preparation_authority.py`: remove target-path trust selection; require/bind/replay the fixed host root.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/accepted_runtime.py`: choose fixed-host versus legacy run-local root strictly from accepted custody metadata for cache install and revalidation.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/publication/__init__.py` and `admission.py`: route successor publication/acceptance through the same accepted-metadata resolver so `HOST_SYSTEM_V1` descendants do not fall back to run-local files.
- Modify `bilqis_mlx/runtime/cognitive_package/operator.py`: preserve pointer-locked source-root revalidation while resolving system-vs-legacy authority from accepted custody rather than assuming a run-local file. The existing run-local lock remains for legacy custody; the fixed-host path is read-only and has no runtime writer.
- Modify `bilqis_mlx/runtime/_custody/bamf_bundle/sidecar_contracts.py`: validate `source_authority_registry_origin` as absent/legacy or exact `HOST_SYSTEM_V1`, and require record+digest when system-host origin is present.
- Modify `bilqis_mlx/runtime/bamf_first_student.py` / private support: restore absent-or-empty fresh target semantics; do not allow pre-existing registry files to bootstrap authority.
- Update `docs/operations/BAMF_0_2_FIRST_STUDENT.md` and `docs/operations/BAMF_0_2_PACKAGES.md` to distinguish system-host genesis authority from historical run-local custody.
- Update focused genesis/source-authority tests and shared fixtures only as needed; test-only path substitution must not be exported as production configuration.

## Acceptance proof

- New generation zero always binds `HOST_SYSTEM_V1` plus exact registry record/digest from the fixed host file.
- Missing fixed host file rejects before any new run pointer/bundle/lease mutation.
- Caller-created run-local registry cannot establish gen0 authority.
- No public/package/CLI/config/environment path or raw-registry provisioner exists.
- Fixed host root drift between prepare/publish rejects before pointer mutation.
- Fixed host root drift after acceptance prevents `SourceAuthorityRuntime` mint/reuse.
- Two different fresh run roots on the same host may bind the same fixed root but their opaque runtime capabilities remain run/cache-bound and non-interchangeable.
- Exact cold resume reconstructs the same accepted C09 authority without caller input.
- Existing #917 attacker-first, forged capability, foreign capability, stale generation, wrong-scope/wrong-key, retry, and historical-read tests remain green.
- Existing #904/#923 generation-zero trust and no-C05-genesis invariants remain green.
- #950 explicitly supersedes only #926's historical assertion that current generation zero has no C09 registry digest. The #926 regression is amended for C16.1c-born lineages to require `HOST_SYSTEM_V1` + exact registry record/digest at generation zero while preserving its no-C05-bootstrap, authenticated run-identity, and successor-lineage guarantees. Historical pre-#950 generations remain readable under their recorded custody.
- No C07 lease/adoption or neural/optimizer/teacher mutation occurs.

## Risks and limits

- The host must perform a one-time privileged configuration step outside Bilqis runtime. Absence intentionally blocks new authoritative gen0 creation.
- `/etc/entif-ai/bilqis/...` is a Unix/macOS host contract. BAMF's current MLX execution target is macOS; a future non-Unix port needs an explicitly governed equivalent rather than an environment override.
- This leaf trusts the host administrator/UID 0 boundary. It does not defend against a malicious root administrator or concurrent out-of-band root rotation; rotation is prohibited until separately governed.
- Root rotation is intentionally unsupported by this leaf and fails closed.
- Tests must patch the private fixed-path reader or constant in isolated fixtures; that test substitution must never become production configurability.
