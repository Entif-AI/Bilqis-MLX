# C09 host-bootstrap remediation proposal v6

Status: PROPOSED v6 / issue #1030 / implementation frozen pending fresh formal review.

Reviewed integration base: `97a018ed7e9697fe284abd9fa8197cd7f4194b45`.

Failed design evidence retained unchanged:

- v4: `899eb017d9842c4fb2e5a5e4f5ebcb517d5fce2a`
- v5: `af56cc21f993d5579c6ac0418f7915eb3a0fbf89`

Pinned review authority: EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

No production implementation is authorized by this document. The existing #950 fixed-host
consumer remains fail-closed and unchanged unless the implementation phase proves an actual
consumer defect.

## 1. Why v6 exists

Fresh independent review of v5 failed the formal gate:

- Design Critic: 0 Blockers / 5 Majors / 1 Nit;
- Codebase Details: 0 Blockers / 2 Majors / 1 Nit;
- Implementation Readiness: 0 Blockers / 10 Majors / 0 Nits.

v6 closes the complete review batch before code work starts. In particular it freezes:

1. explicit alternatives and rejection rationale;
2. canonical machine-contract bytes and digest derivation;
3. a cryptographically bound source-revision identity;
4. an independent runtime-principal source instead of caller-selected UID;
5. secure operator-side secret path traversal and crash recovery;
6. exact C07, A12, C13 correction, and C13 revalidation canary wire objects;
7. the exact signer validation API split between root metadata proof and runtime proof;
8. file-size, UID/GID, mode, ACL, durability, and no-clobber rules;
9. a deterministic, timestamp-free host receipt;
10. coherent protected-canary consumption and regeneration;
11. exact Create/Modify/Delete implementation surfaces;
12. implementation phases with proof-bearing exit gates.

## 2. Non-negotiable invariants

The implementation MUST preserve all of these:

- no caller-selected registry path, signer path, owner set, scope set, or trust-root bytes;
- no runtime or package-local first writer for `HOST_SYSTEM_V1`;
- no test fixture, run-local registry, environment override, or package-local provisioner promoted
  to production authority;
- no private key in Git, GitHub, Drive, receipts, stdout, logs, or chat;
- no registry rotation for an accepted lineage; recovery restores exact old authority or stops;
- the registry remains public authority only; private signing material is a separate artifact;
- the external C07/A12/C13 signer remains off the Studio;
- B14 generic cache identity continues to consume the existing `rights:<64hex>` dependency
  unchanged;
- registry publication remains the final one-way activation event;
- no neural workload is part of #1030.

## 3. Frozen authority census

The newborn registry contains exactly four public identities. The machine-readable authority
contract is `authority-manifest-v3.json`.

### 3.1 C06 host priority signer

Owner: `owner:c06`.

Scopes:

- `POLICY salience-policy:`
- `SOURCE salience-fact:`
- `ARTIFACT salience-option:`
- `ARTIFACT salience-event:`

The private key is created by the operator administration flow before Studio activation,
retained in independently recoverable custody, and imported into the fixed host signer file.

### 3.2 B14 cache identity

Owner: `owner:b14-cache`.

Scope:

- `ARTIFACT cache:`

The private half exists only long enough to derive the public identity. Once a durable public
bootstrap package exists, the private half is destroyed. No detached-signature path uses it.

### 3.3 External BAMF source owner

Owner: `owner:bamf-source`.

Scopes:

- `ARTIFACT atlas-approval:`
- `ARTIFACT a12-export:`
- `ARTIFACT capability-support:Z.C13_EPISODE`

The private key remains off-Studio. This owner receives no `RIGHTS` authority.

### 3.4 External C13 correction-rights owner

Owner: `owner:c13-rights`.

Sole scope:

- `RIGHTS c13-source-rights:Z.C13_EPISODE:`

This namespace is deliberately disjoint from generic `rights:` so B14 cache identity and
unrelated source rights are not delegated to the C13 correction signer.

## 4. Alternatives considered and rejected

The selected design is not the only possible design. These alternatives were evaluated before
v6 was frozen.

### 4.1 Signer custody

**Selected: operator-side generation with independent recovery before activation.**

Advantages: every long-lived private authority exists in recoverable custody before the
immutable registry can activate; the Studio importer is validate/install-only; another trusted
Studio can restore exact bytes without rotation.

Costs: operator-side secret storage and protected transfer require strict descriptor safety.
Those requirements are specified in section 8.

**Rejected: generate C06 on the Studio, then back it up.**

Reason: there is an activation-to-backup failure window in which the immutable registry can bind
a key whose only private copy is lost with the Studio. Closing that window requires an export
acknowledgment protocol before activation, which is strictly more complex than pre-generation.

**Rejected: generate all private authorities on the Studio.**

Reason: C07/A12/C13 source-owner authority is intentionally external. Giving those private keys
to the Bilqis runtime collapses the source-owner/runtime separation accepted by #950/C07/A12.

### 4.2 Host activation transaction

**Selected: same-directory pending files, metadata durability, signer publication, preactivation
runtime proof, and registry publication last with `renameatx_np(..., RENAME_EXCL)`.**

Advantages: no final trust root exists until all recoverable prerequisites are durable; final
names cannot be overwritten; crash prefixes have a deterministic resume/stop classification.

**Rejected: write final files directly.**

Reason: partial writes or metadata changes can leave a visible trust root without a durable
signer or exact recovery frontier.

**Rejected: publish registry before signer.**

Reason: the registry is the immutable activation boundary. Publishing it first can create a
born lineage whose private C06 signer is absent or unreadable.

**Rejected: transactional directory swap.**

Reason: #950 already defines stable fixed file paths below a trusted directory. Swapping an
entire directory adds alias/descriptor semantics without reducing the two-file state machine.

### 4.3 C13 authority namespace

**Selected: preserve generic `rights:<digest>` and add the disjoint correction-only dependency
`c13-source-rights:Z.C13_EPISODE:<digest>` to retained C13 capability support.**

Advantages: least privilege for corrections, exact compatibility with B14 cache parsing, and no
change to existing training-row identity.

**Rejected: grant `owner:bamf-source` generic `RIGHTS rights:`.**

Reason: prefix-based C09 matching would authorize unrelated rights corrections.

**Rejected: rename the existing generic C13 row rights key.**

Reason: B14 deliberately extracts one unique `rights:<64hex>` dependency as cache identity;
renaming it changes accepted causal/cache semantics.

**Rejected: grant SOURCE authority for every C13 row.**

Reason: #529 needs a qualified correction/revalidation path, not broad source-row signing. The
retained capability-support node is the narrow durable correction target.

### 4.4 C13 namespace reservation ownership

**Selected: one neutral declarative contract in
`bilqis_mlx/factory/source_binding_reservations.py`, consumed by both the C13 release producer
and generic Factory validation.**

**Rejected: duplicate C13 literals in `curriculum_definition.py` and the source adapter.**

Reason: duplicated policy literals create split ownership and future drift.

## 5. Durable C13 source-binding and correction contract

### 5.1 Neutral source-binding reservation

The neutral reservation contains exactly:

- capability ID `Z.C13_EPISODE`;
- capability namespace prefix `Z.C13_EPISODE`;
- source anchor `public-formal:bamf.c13.episode-binding/v1`;
- source family `bamf.c13.episode-binding/v1`;
- generator `bilqis.c13.episode-binding-generator/v1`;
- oracle `bilqis.c13.episode-binding-checker/v1`;
- correction-rights prefix `c13-source-rights:Z.C13_EPISODE:`.

`source_adapters.c13_episode_release.compile_episode_release()` imports that declaration when it
builds the C13 source binding. `factory.curriculum_definition.validate_source_bindings()`
imports the same declaration and rejects:

- exact `Z.C13_EPISODE` with any different source anchor/generator/oracle;
- the reserved source anchor/generator/oracle under any different capability;
- a capability beginning `Z.C13_EPISODE` that is not exactly the reserved capability;
- any binding that would create a second occupant under the reserved capability-support prefix.

The validator is independent of host bootstrap state.

### 5.2 Existing generic rights remain unchanged

Current provenance includes `RIGHTS rights:<64hex>`. B14 intentionally recognizes keys beginning
exactly `rights:` and expects one unique digest. That dependency MUST remain byte-for-byte
semantically unchanged.

### 5.3 Additional correction-only dependency

`capability_support_materialization.materialized_support()` adds one extra dependency only when
its validated capability is the reserved C13 capability:

`RIGHTS c13-source-rights:Z.C13_EPISODE:<digest>`

`<digest>` is the one unique 64-hex suffix already present among the support node's generic
`RIGHTS rights:<digest>` dependencies. Zero, multiple, or malformed generic rights digests fail
materialization. Caller payloads do not supply the new namespace.

The new dependency is added after anchor proof verification and before `ArtifactNode`
construction. All unrelated capability-support nodes remain unchanged.

## 6. Canonical machine authority and source revision

Three v6 design files are machine/review authority:

- `authority-manifest-v3.json`
- `bootstrap-contract-v2.json`
- `host-bootstrap-proposal-v6.md`

The JSON files are committed in canonical form: UTF-8, recursive sorted keys, separators
`(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, exactly one terminal newline.

Frozen v6 review identities are:

- authority manifest v3 SHA-256:
  `8aeedc9d0cd0de5d2e842eb98d12fdc5e194c7ee6f704cf2f538d3433ada6ac1`;
- bootstrap contract v2 SHA-256:
  `9f7d120391517d185a28cf4214c9b7ad16bb02ab15d3448bc71e9d4b089173bf`;
- derived source revision:
  `ac9220551e8c971042ffee59ee52ad8c32105fd8126bcc03fbc1ba72c6417b16`.

These values are review receipts, not caller configuration. Implementation recomputes them
from the checked-in canonical files and the source-revision algorithm below.

`authority_manifest_sha256` is SHA-256 of the exact committed canonical manifest bytes.

`bootstrap_contract_sha256` is SHA-256 of the exact committed canonical contract bytes.

`source_revision` is not a Git SHA and is not caller data. It is:

```text
sha256(
  b"bilqis.mlx.c09-host-bootstrap-source/v2\0"
  + authority_manifest_sha256.encode("ascii")
  + b"\0"
  + bootstrap_contract_sha256.encode("ascii")
).hexdigest()
```

The public package, protected canary bundle, and host receipt carry the same source revision.
Every operator/host command recomputes the two checked-in digests and source revision and rejects
mismatch before mutation. This avoids a circular self-hash while binding package interpretation
to exact reviewed machine semantics.

## 7. Exact protected canary contract

All unsigned canary inputs are frozen under `canary_templates` in
`bootstrap-contract-v2.json`. Operator signing adds only signature fields required by the
existing domain dataclasses. The protected bundle schema is
`bilqis.mlx.c09-host-bootstrap-canaries/v2`.

### 7.1 C07 canary

The frozen JSON record maps deterministically to `AtlasSourceApproval`; it is not passed to the
dataclass constructor with `**record`.

Decoder rules are exact:

1. require literal `verification_mode == "DISPOSABLE_CONTRACT"` and
   `schema_version == "bilqis.c07.atlas-source-approval/v1"`, then omit those two `init=False`
   fields from constructor kwargs;
2. construct `DeltaBudgetPolicy` from the nested object and require its exact version;
3. convert `source_family_ids` and `operator_ids` JSON arrays to tuples preserving order;
4. add the generated `signature_hex` field;
5. construct `AtlasSourceApproval` with only its `init=True` fields;
6. require `dataclasses.asdict(approval)` to equal the canonical decoded wire record including
   the literal init-false fields and signature before calling `verify()`.

Operator initialization signs the real `AtlasSourceApproval.signing_bytes()` with
`owner:bamf-source`. Host validation performs the same decoder/round-trip and calls real
`verify()` against the pending registry.

### 7.2 A12 canary

The contract freezes all four validator inputs:

1. `ExportClearanceReceipt` fields other than signature;
2. exact `AtlasArtifactSelection` pinned to the checked-in A01 identity;
3. exact `SourceFrontier(rights_epoch=0, correction_generation=0, grants=())`;
4. exact export artifact digest tuple.

The receipt's `source_frontier_sha256` is derived with existing `contract_digest()` from the
literal frozen frontier. Operator initialization signs the real
`ExportClearanceReceipt.signing_bytes()`. Host validation calls the real
`validate_export_clearance_context()` with those exact objects and the pending registry.

A12 JSON decoding is exact: all digest arrays become tuples; `SourceFrontier.grants` becomes a
tuple; the literal frontier schema version is required; `AtlasArtifactSelection` is constructed
from its exact JSON fields; `signature_hex` is added only to the receipt. After construction,
each dataclass is projected with `asdict()` and must round-trip to the canonical wire object
before validation.

The checked-in A01 source-pin registry SHA remains
`842b66ad7b19ddb333610668410820b3f5d703fa1e452d014755c2c5cc308cee`.
Any drift before implementation returns this design to review; the tool never silently chooses a
new live pin.

### 7.3 C13 correction canary

The contract freezes a complete `CorrectionEvent` except its Ed25519 signature. The dependency
is exactly:

`RIGHTS c13-source-rights:Z.C13_EPISODE:` + `"6" * 64`

Operator initialization signs `CorrectionEvent.signing_bytes()` with `owner:c13-rights`.
Host validation constructs the real event and calls `pending_registry.verify_correction()`.

The correction decoder converts the nested dependency object to `DependencyRef`, converts
`supersedes_event_ids` to a tuple, adds only `source_signature_hex`, constructs the real
`CorrectionEvent`, and requires its field projection to round-trip to the canonical wire record
before verification.

### 7.4 C13 capability-support revalidation canary

The contract freezes a complete synthetic `ArtifactNode` with:

- artifact ID `capability-support:Z.C13_EPISODE`;
- kind `CAPABILITY_SUPPORT`;
- impact/exigency `4/4`, matching `owner_priority(CAPABILITY_SUPPORT)`;
- content digest `"a" * 64`;
- `eligible=true`;
- a production-shaped dependency tuple containing POLICY retention, RELEASE generation,
  RELEASE source-generation/source-release, the unchanged generic `rights:<digest>`, the new
  C13 correction-rights dependency, and SOURCE row/digest/batch/proof dependencies.

The candidate `RevalidatedArtifact` carries the exact same sorted dependency tuple, same content
digest, and same eligibility. Operator initialization signs its real `signing_bytes()` with
`owner:bamf-source` and wraps it in one `RevalidationFrontier`.

Host validation calls real `revalidate_node(node, frontier, pending_registry)` and requires an
unchanged `StateTransition` matching the frozen expected fields. This canary proves ARTIFACT
revalidation authority and exact dependency conservation. It deliberately does not claim to
exercise the queue/changed-support requalification branch; #529 owns that end-to-end witness.

The revalidation decoder converts both dependency arrays to tuples of `DependencyRef`, requires
the node/candidate tuples to be exactly equal after decoding, adds only
`source_signature_hex` to the candidate, constructs `ArtifactNode` and
`RevalidatedArtifact`, wraps the candidate in `RevalidationFrontier(results=(candidate,))`, and
requires `asdict()` projections to round-trip to the frozen wire objects before
`revalidate_node()` is called.

### 7.5 Canary lifecycle

A signed C07/A12 canary is a capability-bearing authorization artifact, so it is never retained
on the Studio after a successful host command.

`operator-init` emits a protected transfer canary. `operator-canary` can deterministically
regenerate the exact same bundle later from the retained external keys and public package.

`host-install` and `host-verify` both require a canary transfer. On success they unlink the
root-owned staged copy and the caller transfer file, fsync both containing directories, and
return only after deletion durability. On failure they leave the caller transfer untouched so
the operator can inspect/retry. Routine post-install verification therefore begins by running
`operator-canary` again.

The C06 signer input is also a consumable transfer artifact. After the fixed signer has been
published and the preactivation runtime-UID proof has succeeded, the command unlinks the caller
C06 transfer and fsyncs its parent before registry activation. A later `host-verify` therefore
requires a fresh protected transfer copy of the exact retained operator C06 record; it consumes
that copy on success as well. The fixed signer is the only persistent private-key copy on the
Studio.

## 8. Operator-side key custody and crash recovery

### 8.1 Secret parent and descriptor safety

`operator-init`, `operator-verify`, `operator-canary`, and `operator-host-principal` MUST run with
non-root EUID.

Every primary/recovery secret parent directory MUST already exist. The tool traverses each
absolute path fd-relative from `/` using `O_RDONLY|O_DIRECTORY|O_NOFOLLOW`. Intermediate
components MUST be UID 0 or EUID-owned and MUST NOT be group/world writable. The final secret
parent MUST be EUID-owned, mode exactly `0700`, have no extended ACL, and not be a symlink.

Secret files are opened/created only fd-relative. New files use
`O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`, initial mode `0600`, followed by `fstat()` requiring:

- regular file;
- owner EUID;
- mode exactly `0600`;
- link count exactly 1;
- no extended ACL;
- configured size bound.

Existing final files are opened `O_RDONLY|O_NOFOLLOW` and must satisfy the same metadata and
canonical schema checks. A symlink, hardlink, wrong owner, wrong mode, unexpected ACL, or
conflicting canonical record fails closed. The tool never overwrites a conflicting final file.

`operator-host-principal --out` uses the same fd-relative parent traversal and no-clobber output
contract: EUID-owned mode-`0700` parent with no extended ACL; new regular mode-`0600` file,
owner EUID, link count 1; write canonical signed bytes, `fsync`, `F_FULLFSYNC`, close/reopen and
read back exact bytes, then fsync the containing directory. Existing output is accepted only
when its canonical bytes equal the newly derived authorization exactly.

### 8.2 Independent recovery domain

For each retained private record, primary and recovery parents MUST have different `st_dev` and
different Darwin `ParentWholeDisk` values from `/usr/sbin/diskutil info -plist`. Two APFS
volumes on the same whole disk do not qualify.

### 8.3 Private-key pair crash state machine

For each of C06, BAMF source, and C13 rights keys:

- both absent: generate once in memory, durably create primary, then durably create recovery;
- primary valid / recovery absent: copy exact primary canonical bytes to recovery;
- recovery valid / primary absent: restore exact recovery canonical bytes to primary;
- both present: require byte-for-byte equality and identical derived public identity;
- any invalid/conflicting copy: stop, never generate a replacement.

A file is durable only after byte write, `fsync(fd)`, Darwin `F_FULLFSYNC`, final metadata
validation, no-clobber publication, and containing-directory `fsync`.

### 8.4 B14/public-package crash state machine

B14 is special because its private half is intentionally destroyed.

- no package copy: generate B14 keypair, construct package, durably publish primary package;
- primary package exists / recovery absent: validate primary and copy exact bytes to recovery;
- recovery package exists / primary absent: validate recovery and restore exact bytes to primary;
- both exist: require exact byte equality and exact reconstruction from retained C06/source/C13
  public identities plus the stored B14 public identity;
- conflicting packages: stop.

B14 private material may be destroyed only after at least one durable valid package contains its
public key. `operator-init` does not report success until both package copies are durable on
independent whole disks.

## 9. Exact CLI contract

Entry point: `python3 scripts/operations/bamf_source_authority_bootstrap.py`.

The exact subcommands and flags are frozen in `bootstrap-contract-v2.json`.

### 9.1 `operator-init`

Creates or resumes the three private primary/recovery pairs, B14 identity, both public package
copies, and one protected canary transfer. It prints only paths, public IDs/keys, and SHA-256
digests. No private bytes appear on stdout/stderr.

### 9.2 `operator-verify`

Mutation-free. It verifies both copies of every retained key and both public package copies,
recomputes manifest digest, contract digest, source revision, public identities, and public
package bytes, and requires exact equality.

### 9.3 `operator-canary`

Mutation is limited to a new protected canary transfer file. It requires valid retained BAMF
source/C13-rights keys plus a valid public package and regenerates the exact deterministic signed
canary bundle committed by the package digest. An existing conflicting `--canary-out` fails.

### 9.4 `operator-host-principal`

This is the independent administrative decision point for which local OS principal may read the
C06 signer on one physical host. It accepts the retained C06 operator key, exact public package,
target Darwin `IOPlatformUUID`, runtime account name, UID, GID, and a protected output path.

It emits canonical schema `bilqis.mlx.c09-host-runtime-principal-authorization/v1` with exactly:

```text
schema
source_revision
bootstrap_package_sha256
host_platform_uuid
runtime_user
runtime_uid
runtime_gid
signer_owner_id
signature_hex
```

The signature is Ed25519 by the retained `owner:c06` private key over every field except
`signature_hex`. This artifact is the authority to install a signer ACL for one principal on one
physical host. The host installer cannot mint or change it.

### 9.5 `host-install`

Requirements: Darwin, EUID 0, and valid sudo provenance. It accepts only:

- public package path + expected SHA-256;
- signed runtime-principal authorization path;
- protected canary transfer path;
- protected C06 signer transfer path + expected SHA-256;
- public receipt output path.

It accepts no runtime user, UID/GID, owner, scope, registry bytes, destination path, or manifest
path from the caller.

`--receipt-out` is the only caller-selected output path and is not authority. Because the
command is privileged, its parent MUST pass the same fd-relative/no-symlink traversal as an
operator output parent, be owned by the resolved sudo UID, mode `0700`, and contain no extended
ACL. The receipt is created `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`, owned by the sudo UID/GID,
mode `0600`, regular, link count 1. An existing path is opened read-only only to prove exact
byte equality during idempotent verification; it is never overwritten.

### 9.6 `host-verify`

Same transfer/digest/receipt arguments as `host-install`. It performs no trust-root mutation.
A fresh canary transfer is required because successful commands consume/delete prior canaries.
If the receipt is missing after a prior activation crash, `host-verify` deterministically
reconstructs the exact receipt from fixed state and authenticated transfers.

## 10. Independent runtime principal authority

The runtime principal is not caller-selected by `host-install` and is not inferred from the
sudo invoker. Sudo provenance establishes only who elevated the command.

Before host installation, the operator issues one signed
`bilqis.mlx.c09-host-runtime-principal-authorization/v1` using `operator-host-principal` and the
retained C06 private key. Root validates this artifact against `c06_public` from the authenticated
package before signer staging.

The installer also reads the target's Darwin `IOPlatformUUID` and requires exact equality with
`host_platform_uuid`. It then requires:

- `runtime_uid != 0`;
- `pwd.getpwuid(runtime_uid).pw_name == runtime_user`;
- `pwd.getpwnam(runtime_user).pw_uid == runtime_uid`;
- the account's primary GID equals `runtime_gid`;
- the account and group resolution remain identical on a second read before ACL publication.

SUDO_UID/GID/USER MAY be recorded as installer-audit context outside the canonical receipt but
MUST NOT select the runtime account. A sudo-capable account cannot authorize itself merely by
invoking the installer. The signed host-specific C06 authorization is the independent authority.

Recovery to another trusted Studio uses the same immutable registry/C06 key but requires a new
host-specific authorization signed by the retained external C06 key for that host's
IOPlatformUUID and intended runtime account. No registry rotation is required.

## 11. Fixed Darwin host-state contract

### 11.1 Size bounds

Exact maximum input sizes are frozen in `bootstrap-contract-v2.json`:

- public package: 262,144 bytes;
- protected canary bundle: 524,288 bytes;
- C06 signer record: 8,192 bytes;
- runtime-principal authorization: 8,192 bytes;
- external key record: 8,192 bytes.

Files at or above the bound are rejected before JSON parsing.

### 11.2 Directories and public registry

`/private/etc/entif-ai` and `/private/etc/entif-ai/bilqis` MUST be UID 0, GID 0, mode `0755`,
real directories, and have no extended ACL. All descendants are traversed fd-relative with
`O_NOFOLLOW`.

If no final signer/registry exists, root may create missing directories and normalize newly
created directory metadata before staging. Existing unsafe metadata is never silently repaired;
it fails. Once either final authority file exists, all directory metadata is verify-only.

Final registry:

- UID 0 / GID 0;
- mode `0444`;
- no extended ACL;
- regular file, link count 1;
- canonical C09 v2 registry bytes;
- must pass the existing production fixed-path registry reader unchanged.

### 11.3 C06 signer ACL and reader API

Final signer:

- UID 0 / GID 0;
- mode `0400`;
- regular file, link count 1;
- exactly one non-root ALLOW ACE, for the resolved runtime UID;
- that ACE contains exactly `ACL_READ_DATA` and no mutation bit;
- no group ALLOW and no DENY ACE.

`_darwin_source_authority` is extended to decode `ACL_READ_DATA = 1 << 1` while its existing
mutation-permission set remains the eight existing mutation names.

`_darwin_salience_signer` freezes this API split:

```python
def _read_host_system_source_authority_signer_for_uid(
    registry: SourceAuthorityRegistry,
    *,
    expected_reader_uid: int,
    require_process_uid_match: bool,
) -> HostSourceAuthoritySigner: ...

def read_host_system_source_authority_signer(
    registry: SourceAuthorityRegistry,
) -> HostSourceAuthoritySigner:
    # public runtime path: expected_reader_uid=os.geteuid(),
    # require_process_uid_match=True, EUID 0 rejected.
```

The root installer uses the private helper with the independently authorized runtime UID and
`require_process_uid_match=False` only for metadata/content validation. Actual access proof is
performed in a child process after clearing supplementary groups and adopting the resolved
primary GID and UID; the child calls the public production reader.

ACL installation uses descriptor APIs only:
`acl_init -> acl_create_entry -> acl_set_tag_type(ACL_EXTENDED_ALLOW) ->
mbr_uid_to_uuid -> acl_set_qualifier -> acl_get_permset -> acl_add_perm(ACL_READ_DATA) ->
acl_set_fd_np(fd, acl, ACL_TYPE_EXTENDED)` followed by readback through the existing ACL reader.

## 12. Protected host staging and durability

Every caller-selected transfer path (`--package`, `--runtime-principal-auth`,
`--canary-bundle`, `--c06-signer`) is anchored before privileged use. Root traverses its
absolute parent fd-relative from `/` with `O_RDONLY|O_DIRECTORY|O_NOFOLLOW`, requires each
intermediate directory to be root- or sudo-invoker-owned and not group/world writable, then
requires the final parent to be owned by the sudo invoker, mode `0700`, with no extended ACL.
It retains that verified parent fd and basename for the entire command.

The file itself is opened with `openat(parent_fd, basename, O_RDONLY|O_NOFOLLOW)`, then must be
regular, link count 1, below its frozen size bound, owned by the sudo invoker, mode exactly
`0600`, and have no extended ACL. Before any later cleanup, root re-`fstat()`s the already-open
descriptor and reopens the same basename through the anchored parent fd to require the same
device/inode identity. Cleanup uses `unlinkat(parent_fd, basename, 0)` only. No privileged
`unlink(path)` is permitted.

Public package authenticity additionally requires the caller's expected SHA-256. Runtime
principal authorization authenticity requires a valid `owner:c06` signature, exact package
digest/source revision, and target `IOPlatformUUID`. C06 authenticity requires both caller
digest and package-committed digest plus public-key derivation. Canary authenticity requires the
package-committed digest.

The public package is parsed as canonical v2, then root recomputes and verifies:

- canonical manifest v3 digest;
- canonical bootstrap-contract v2 digest;
- source revision;
- canary bundle digest;
- C06 signer digest;
- all public owner identities.

Root copies package/canary/signer into fixed pending names using same-directory exclusive files.
For every pending signer/registry file the durability order is exact:

1. write canonical bytes;
2. `fsync(fd)`;
3. `fcntl(fd, F_FULLFSYNC)`;
4. apply UID/GID/mode/ACL metadata;
5. re-read metadata/ACL through the open descriptor;
6. `fsync(fd)` again after metadata mutation;
7. `fcntl(fd, F_FULLFSYNC)` again;
8. close and reopen with `O_NOFOLLOW`;
9. verify exact bytes, digest, UID/GID/mode/ACL/link count;
10. fsync containing directory before any publish rename.

No metadata mutation is considered durable merely because the directory was fsynced.

## 13. Crash-safe host activation state machine

Fixed pending names come from `bootstrap-contract-v2.json`.

First install sequence:

1. authenticate package, signed runtime-principal authorization, canary, C06 transfer, machine
   contracts, source revision, and target platform identity;
2. create/verify fixed directories;
3. durably stage package and canary;
4. construct exact four-owner pending registry from checked-in manifest plus package public keys;
5. durably stage signer and registry with the full file+metadata durability sequence in section 12;
6. verify pending registry, C06 key/public match, B14 selector semantics, and all four typed
   canaries through real domain validators;
7. publish signer with `renameatx_np(..., RENAME_EXCL)`;
8. fsync the `bilqis` directory;
9. fork runtime UID/GID child and prove public production signer reader + bounded C06 signature
   against the pending registry object;
10. consume/unlink staged canary, caller canary transfer, and caller C06 transfer; fsync all
   affected parents;
11. publish registry **last** with `renameatx_np(..., RENAME_EXCL)`;
12. fsync the `bilqis` directory; this completes one-way activation;
13. re-read registry through the production fixed-path reader;
14. run the runtime child again through both fixed production readers;
15. construct canonical deterministic receipt; write with no-clobber semantics and fsync/F_FULLFSYNC;
16. fsync receipt parent; read back exact bytes; success.

Recovery matrix:

- neither final file: validate pending state; complete exact missing pending work or discard only
  incomplete unactivated pending files and reconstruct from authenticated transfers;
- final signer, no final registry: exact pending registry MUST exist and bind final signer +
  package identities; otherwise stop as durability-contract violation;
- final registry present: verify-only; exact final signer must already exist; never mutate key,
  owner, scope, ACL, or registry;
- conflicting final file: fail as rotation/migration;
- final registry present but receipt absent: `host-verify` with freshly regenerated canary transfer
  reconstructs the deterministic receipt; no trust-root mutation occurs.

## 14. Deterministic host receipt v2

Schema: `bilqis.mlx.c09-host-bootstrap-receipt/v2`.

The receipt contains no clock, inode, ctime, mtime, or other irreproducible field. Exact fields
and nested field sets are frozen in `bootstrap-contract-v2.json`.

Top-level fields are exactly:

```text
schema
source_revision
authority_manifest_sha256
bootstrap_contract_sha256
bootstrap_package_sha256
canary_bundle_sha256
registry_record
registry_semantic_digest
registry_file_sha256
signer_record_sha256
runtime_principal_authorization_sha256
runtime_principal
registry_stat
signer_stat
signer_acl_summary
canary_validation
runtime_uid_smoke
registry_path
signer_path
```

`registry_semantic_digest` is `SourceAuthorityRegistry.digest`.
`registry_file_sha256` is SHA-256 of exact canonical installed registry bytes.
They are deliberately distinct.

`registry_stat`/`signer_stat` include only `{uid,gid,mode,size}`.
`runtime_principal` is `{user,uid,gid}`.
`runtime_principal_authorization_sha256` is SHA-256 of the exact canonical signed host-specific
authorization bytes accepted by the installer.
`signer_acl_summary` normalizes the exact UID/permission entry.
`canary_validation` is four booleans for C07/A12/C13-rights/C13-support.
`runtime_uid_smoke` binds UID/GID, `owner:c06`, the literal
`POLICY salience-policy:bootstrap-smoke` dependency, signature-verification result, and registry
semantic digest.

`host-verify` recomputes this exact record from fixed state plus authenticated transfers. An
existing receipt must match byte-for-byte; a conflicting receipt fails.

## 15. Exact implementation surfaces

### Create

- `bilqis_mlx/factory/source_binding_reservations.py`
- `bilqis_mlx/factory/tests/curriculum/frontier/test_c13_source_binding_reservation.py`
- `bilqis_mlx/runtime/tests/correction/test_c13_capability_support_authority.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_host_salience_signer.py`
- `scripts/operations/bamf_source_authority_bootstrap.py`
- `scripts/tests/test_bamf_source_authority_bootstrap.py`
- `docs/evidence/bamf/C09-host-bootstrap/authority-manifest-v3.json`
- `docs/evidence/bamf/C09-host-bootstrap/bootstrap-contract-v2.json`
- `docs/evidence/bamf/C09-host-bootstrap/host-bootstrap-proposal-v6.md`
- `docs/evidence/bamf/C09-host-bootstrap/implementation-receipt-v1.md`
- `docs/evidence/bamf/C09-host-bootstrap/host-proof-receipt-v1.md`

### Modify

- `bilqis_mlx/factory/curriculum_definition.py`
- `bilqis_mlx/source_adapters/c13_episode.py`
- `bilqis_mlx/source_adapters/c13_episode_cases.py`
- `bilqis_mlx/source_adapters/c13_episode_release.py`
- `bilqis_mlx/runtime/_correction/owners/capability_support_materialization.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_source_authority/__init__.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_salience_signer/__init__.py`
- `docs/operations/BAMF_0_2_FIRST_STUDENT.md`
- `docs/operations/BAMF_0_2_PACKAGES.md`

### Delete

None.

v4/v5 files and earlier manifests/contracts remain immutable failed-review evidence.

## 16. Implementation phases and checkpoints

Production mutation remains frozen until v6 itself clears fresh EGM 0B/0M.

### Phase I: semantic/authority contracts

Files: neutral reservation, Factory/source-adapter modifications, capability-support rights
materialization, focused tests.

Exit proofs:

- C13 tuple is sourced from one neutral declaration;
- collisions fail;
- generic `rights:<digest>` remains unchanged;
- only retained C13 support gains the disjoint correction-rights dependency;
- B14 cache identity tests remain green.

Checkpoint: push/read-back an issue-backed non-force commit before Phase II.

### Phase II: pure bootstrap serialization and operator custody

Files: bootstrap script pure serializers/operator commands + script tests + machine contracts.

Exit proofs:

- canonical v3/v2 machine-file digests and source revision are stable;
- primary/recovery crash matrix is exhaustive;
- descriptor/symlink/hardlink/ACL negative cases fail;
- B14 package recovery survives every crash prefix;
- typed canary bytes are deterministic and real validators accept them with an in-memory registry.

Checkpoint before any host mutation code.

### Phase III: Darwin descriptor/ACL and host state machine

Files: Darwin custody readers, host-install/verify paths, signer/host tests.

Exit proofs:

- exact ACL READ_DATA semantics;
- C06-signed host-specific runtime-principal authorization with sudo provenance kept
  non-authoritative for runtime selection;
- full post-metadata fsync/F_FULLFSYNC ordering;
- no-clobber publish;
- every activation crash prefix has one prescribed resume/stop result;
- host-verify receipt reconstruction is deterministic.

Checkpoint before documentation/real-host execution.

### Phase IV: operations/docs and local integrated verification

Files: both BAMF operations docs + implementation receipt.

Exit proofs:

- exact commands/documented recovery match the CLI contract;
- targeted suites and relevant owner/differential suites pass;
- EGM drift check and required premerge checks pass;
- no private bytes appear in fixtures/logs/receipts.

Checkpoint pushed and reviewed before real host provisioning.

### Phase V: real m3-ultra proof

Use the reviewed `host-install` flow only. Administrator authorization may be required.

Exit proofs:

- real fixed registry reader passes;
- real runtime UID signer read/sign/verify passes;
- exact public receipt is preserved;
- no canary authorization artifact remains on the Studio;
- fresh generation-zero preflight binds `HOST_SYSTEM_V1` without patch/mock/run-local fallback.

Only then can #528 rerun.

## 17. Acceptance and negative proof matrix

At minimum, implementation must prove:

1. exactly four registry owners and no scope broader than authority manifest v3;
2. canonical manifest/contract digests and source revision are recomputed, never trusted from
   caller text;
3. package with wrong contract digest/source revision is rejected before mutation;
4. C13 source-binding collisions fail at Factory validation;
5. generic rights and B14 cache behavior remain unchanged;
6. only C13 capability support gains the disjoint correction-rights dependency;
7. C07/A12/C13 correction/C13 revalidation canaries all pass real validators;
8. C13 revalidation candidate dependencies exactly equal the frozen node dependencies;
9. wrong owner/key/scope/A01 pin/frontier/artifact tuple/capability namespace fails;
10. operator secret path symlink, hardlink, unsafe parent, unsafe mode/ACL/owner fails;
11. primary-only/recovery-only key crash states restore exact existing bytes, never regenerate;
12. B14 package one-copy state repairs exact bytes without a private-key re-creation path;
13. direct-root host invocation without sudo provenance fails;
14. UID 0 as runtime principal fails;
15. signer lacking ACL_READ_DATA fails;
16. second ALLOW principal, group ALLOW, DENY ACE, mutation ACL, wrong mode/owner/link count fails;
17. every pending file is fsynced/F_FULLFSYNC after metadata mutation before publish;
18. existing final signer/registry cannot be overwritten;
19. runtime child proves the public production signer reader before registry activation;
20. registry publication is last and followed by directory fsync;
21. final-registry state is verify-only;
22. missing receipt after activation is deterministically reconstructed, not used to justify
    trust-root mutation;
23. successful host commands consume all protected canary copies on the Studio;
24. exact rerun is idempotent and conflicting rerun refuses rotation;
25. generation-zero preflight binds real `HOST_SYSTEM_V1` fixed-root authority.

## 18. Review and execution gate

v6 remains design-only until it is committed and pushed as one immutable checkpoint and a new,
fresh, isolated pinned-EGM review of that exact commit reports aggregate 0 Blockers / 0 Majors
for all three lenses:

- Design Critic;
- Codebase Details;
- Implementation Readiness.

If any lens reports a Blocker or Major, the v6 commit remains immutable failed evidence and the
next design amendment is reviewed fresh again. No production implementation begins merely
because a prior design version was close.

After a reviewed implementation and real m3-ultra host proof, #528 reruns at exact head
`e560ccbf6a62480ee0f079e8343b43c5583bc1ab` with bounded `--max-steps 2`. If #528 passes, its
real receipt is consumed by #529, then #530 proceeds only after #529 satisfies its prerequisite.

No PR is self-merged.
