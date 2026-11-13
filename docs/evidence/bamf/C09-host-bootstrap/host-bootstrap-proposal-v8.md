# BAMF-0.2 C09 Host Bootstrap Proposal v8

Issue: #1030
Status: frozen-design candidate; implementation remains prohibited until fresh formal EGM returns 0 Blockers / 0 Majors
Supersedes for future implementation: v7 at `0ecf75aae489f0d72bdb009c0c2cf9435a0ad37b`
Preserves v4-v7 as immutable failed-review evidence

## 1. Decision

Production C09 remains a fixed-host, fail-closed public trust root. Production C06 remains a fixed-host private runtime signer. Bilqis runtime cannot choose either path, generate either authority as a side effect, repair them, rotate them, or establish trust from run-local state.

v8 repairs the fresh formal v7 review without changing the accepted C09 consumer model. The four C09 registry identities and scopes in `authority-manifest-v3.json` remain unchanged. A fifth key, `owner:bootstrap-admin`, exists only in operator custody. It is not a C09 source authority. Its private key never reaches the Studio; its public key is intentionally carried in the approved public package and activation commitment. It signs the host-specific runtime-principal authorization. This separates administrative admission from the runtime-readable C06 key.

Initial activation is an explicit trusted-host-administrator act. The sudo invoker must supply the expected package SHA-256 obtained independently from the reviewed #1030 checkpoint. Package bytes cannot approve themselves. Run-local code, the Bilqis runtime, and an unprivileged first writer cannot establish `HOST_SYSTEM_V1`.

## 2. Formal v7 failure and required repairs

Fresh formal review of exact v7 commit `0ecf75aae489f0d72bdb009c0c2cf9435a0ad37b` against pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c` failed narrowly:

- Design Critic: 0 Blockers / 1 Major / 2 Nits.
- Codebase Details: 0 Blockers / 2 Majors / 0 Nits.
- Implementation Readiness: 0 Blockers / 0 Majors / 0 Nits.

The Design Major found that v7 excluded root from the runtime identity but did not prove that the authorized runtime account itself lacked configured administrative escalation. v8 machine-closes that boundary with a dedicated-runtime predicate checked before activation, at runtime smoke, and during host verification. The runtime user must differ from the sudoing administrator, must not belong to Darwin's `admin` group, and must have no sudoers authorization under a root-run, C-locale `sudo -n -U <runtime_user> -l` probe. This is a configured-privilege guarantee; malicious root, administrator action, and operating-system privilege-escalation vulnerabilities remain outside #1030.

The Codebase Majors found two overclaims in the C13 design. First, generic `CapabilitySourceBinding` has no `source_family_id`, so `validate_source_bindings()` cannot enforce that field. v8 narrows generic reservation enforcement to the tuple that validator can actually see and proves source-family identity on the C13 adapter/release surface. Second, v7 abbreviated the production correction/revalidation API. v8 freezes the exact `DependencyIndex.build`, `RevalidationFrontier((candidate,))`, `apply_correction`, `revalidate_node`, and `advance_revalidation` construction and call shape.

The two Design nits are also closed: only the bootstrap-admin **private** key is forbidden from the Studio, while its public key is intentionally carried in the approved package; and every temporary C06 transfer now has an explicit post-success unlink-plus-parent-fsync lifecycle.

## 3. Authority inventory

### 3.1 C09 registry identities

`authority-manifest-v3.json` remains the only authority census for the immutable C09 registry:

- `owner:c06`: C06 salience policy/fact/option/event signing.
- `owner:b14-cache`: `ARTIFACT cache:` identity.
- `owner:bamf-source`: C07 approval, A12 export, and C13 capability-support revalidation.
- `owner:c13-rights`: C13-only correction authority under `RIGHTS c13-source-rights:Z.C13_EPISODE:`.

No other C09 authority is admitted. The legacy atlas-delta path remains excluded.

### 3.2 Bootstrap administrative authority

`owner:bootstrap-admin` is deliberately outside C09. Its private key:

- is generated or imported only by non-root operator administration;
- has primary and recovery copies on independent whole-disk failure domains;
- never reaches `/etc`, `/private/etc`, the Bilqis runtime, Git, Drive, logs, receipts, or test fixtures;
- signs only schema `bilqis.mlx.c09-host-runtime-principal-authorization/v2`;
- cannot sign C06, C07, A12, C13, B14, registry, or correction artifacts by protocol.

Its public key appears in the public bootstrap package so a trusted host administrator can verify the signed runtime-principal authorization associated with the independently approved package digest.

### 3.3 Trust boundary for first activation

The trusted human host administrator is the generation-zero selection authority. `host-install` requires valid sudo provenance and an expected package SHA-256 supplied separately from the package. Operational procedure must obtain that digest from the reviewed #1030 public checkpoint before invoking sudo.

This is not first-writer-wins. A file merely appearing first under `/private/etc/entif-ai/bilqis` has no authority. The package cannot supply its own expected digest. The runtime cannot invoke the bootstrap-admin signer. The installer refuses activation unless the independently supplied digest, package contents, admin signature, manifest, contract, canaries, C06 transfer, host identity, and fixed-path state all agree.

All sudo-capable host administrators are inside this host-administration threat boundary. Protecting a machine against a malicious root administrator is outside #950/#1030. Runtime-compromise protection applies to the dedicated runtime account at its admitted configured privilege level: before activation and on verification, that account must be non-root, distinct from `SUDO_USER`, absent from Darwin `admin`, and have no sudoers authorization under the exact v4 runtime-principal predicate. Operating-system privilege-escalation vulnerabilities and later deliberate administrator privilege grants are outside the runtime-compromise guarantee; the latter are detected as host-policy drift and make `host-verify` fail closed.

## 4. Machine authority and revision identity

The machine-readable design authority is:

- authority manifest: `authority-manifest-v3.json`
- manifest SHA-256: `8aeedc9d0cd0de5d2e842eb98d12fdc5e194c7ee6f704cf2f538d3433ada6ac1`
- bootstrap contract: `bootstrap-contract-v4.json`
- contract SHA-256: `2521cd93985b36375238bdb0357f1c8f2bb13e660a508ceb22ff3044830f0ffe`
- source-revision domain: `bilqis.mlx.c09-host-bootstrap-source/v4`
- source revision: `e8ea1d10abf5812202a65bfd66adb95c581472c600215d41d236e3801f35fdac`

Source revision is SHA-256 over:

`domain || NUL || authority_manifest_sha256_ascii || NUL || bootstrap_contract_sha256_ascii`.

The JSON contract is canonical JSON with UTF-8, recursively sorted keys, compact separators, `ensure_ascii=false`, `allow_nan=false`, and one terminal newline. Signing payloads that explicitly say “no terminal newline” use the same canonical rules without that final newline.

## 5. Exact private and public records

### 5.1 C06 signer record

C06 primary, recovery, consumable transfer, pending host signer, and installed signer use identical canonical bytes:

```json
{"owner_id":"owner:c06","private_key_hex":"<64 lowercase hex>","schema":"bilqis.mlx.source-authority-signer/v1"}
```

The canonical record above is serialized in sorted-key order and terminated by one newline. No alternate C06 private-key schema exists. `c06_signer_record_sha256` is SHA-256 over those exact canonical bytes including the terminal newline. The installer derives the Ed25519 public key and requires exact equality with package `c06_public` and the C09 registry projection before activation.

### 5.2 External retained keys

Bootstrap-admin, BAMF source-owner, and C13-rights retained records use `bilqis.mlx.external-source-owner-key/v1` with exactly `schema`, `owner_id`, and `private_key_hex`. Each owner ID is fixed by the operation that opens the record. Private keys are 32-byte Ed25519 seeds encoded as 64 lowercase hexadecimal characters.

### 5.3 Public owner identity

Every package public identity uses schema `bilqis.mlx.c09-public-owner-identity/v1` with exactly:

- `schema`
- `owner_id`
- `public_key_hex`

The package field fixes the owner ID: bootstrap-admin, C06, BAMF source, C13 rights, or B14 cache. Extra fields fail. Scopes never come from this record.

## 6. Registry projection is deterministic

`authority-manifest-v3.json` is a census, not a serialized registry. The registry builder MUST:

1. Read and digest the exact checked-in manifest.
2. Join its four C09 owner IDs to the four corresponding package public identities. `owner:bootstrap-admin` is excluded.
3. Drop manifest-only `key_material` and `scope_intent`.
4. For each manifest scope, create `SourceAuthorityScope(kind, key_prefix, schema_version="bilqis.c09.source-authority-scope/v1")`.
5. Sort scopes by `(kind.value, key_prefix)`.
6. Create each `SourceAuthorityKey` with schema `bilqis.c09.source-authority-key/v2`.
7. Sort keys by `owner_id`.
8. Create `SourceAuthorityRegistry(..., schema_version="bilqis.c09.source-authority-registry/v2")`.
9. Serialize exactly through `SourceAuthorityRegistry.to_record()`.
10. Canonicalize that record and derive both the semantic registry digest and raw-file SHA-256.

No package field can add an owner, scope, prefix, dependency kind, or schema version.

## 7. C13 reservation is a compile-time invariant

Create `bilqis_mlx.factory.source_binding_reservations` with:

```python
@dataclass(frozen=True)
class SourceBindingReservation:
    capability_id: str
    capability_prefix: str
    source_anchor: str
    source_family_id: str
    generator_id: str
    oracle_id: str
    rights_prefix: str
```

The module exports exactly one C13 singleton named `C13_EPISODE_SOURCE_BINDING_RESERVATION`, whose seven values equal `bootstrap-contract-v4.json.binding_reservation`.

Generic Factory enforcement is limited to identities that `CapabilitySourceBinding` actually exposes. `validate_source_bindings(curriculum, bindings)` MUST reject any binding whose `capability_id.startswith("Z.C13_EPISODE")` unless the visible tuple equals exactly:

- `capability_id = Z.C13_EPISODE`
- `source_anchor = public-formal:bamf.c13.episode-binding/v1`
- `generator_id = bilqis.c13.episode-binding-generator/v1`
- `oracle_id = bilqis.c13.episode-binding-checker/v1`

No new field is added to `CapabilitySourceBinding`. Source-family identity is instead enforced where it exists:

- `c13_episode.py` aliases capability, generator, and oracle IDs from the reservation.
- `c13_episode_cases.py` aliases `SOURCE_FAMILY` from `reservation.source_family_id`.
- `c13_episode_release.py` builds the exact visible binding tuple from the reservation.
- `source_attestation_sha256()` includes exactly `reservation.source_family_id`.
- C13 adapter/release tests prove emitted case/row family and attestation use that exact reserved family.
- C13 capability-support materialization derives the correction rights prefix from the reservation.

Thus the generic validator protects the namespace it can inspect, while the C13-owned surface proves the family identity it actually emits. No validator is asked to infer data absent from its inputs.

## 8. Operator custody and atomic publication

Operator commands run with non-root EUID. Every primary/recovery secret parent is fd-relative, no-symlink traversed, EUID-owned, mode `0700`, no extended ACL. Secret/public-package operator files are EUID-owned regular files, mode `0600`, link count one, no extended ACL, and below the exclusive configured size bound.

No operator artifact is created directly at its final path. Every operator output uses a same-directory hidden pending file opened with `O_EXCL|O_NOFOLLOW`. The tool:

1. writes exact canonical bytes;
2. `fsync(fd)`;
3. applies Darwin `F_FULLFSYNC`;
4. verifies metadata and bytes through the descriptor;
5. fsyncs the parent;
6. closes and reopens the pending file with `O_NOFOLLOW` and revalidates it;
7. publishes with `renameatx_np(..., RENAME_EXCL)`;
8. fsyncs the parent again.

If the process crashes before publication, an orphan pending file has no authority. When final is absent, a subsequent run may validate and complete an exact pending publication or remove an incomplete/conflicting pending file and reconstruct it from already-valid retained inputs. A conflicting final file is never overwritten.

The same rule applies to retained keys, public packages, canary outputs, C06 transfer outputs, and runtime-principal authorizations.

### 8.1 Independent recovery

Each retained private authority pair, including bootstrap-admin, C06, BAMF source, and C13 rights, requires primary and recovery parents on different `st_dev` and different Darwin `ParentWholeDisk`. Two APFS volumes on one whole disk do not qualify.

Both absent may generate once. One valid copy restores the other. Two valid copies must be byte-identical. Any conflicting valid pair fails closed. An invalid final file is never silently replaced or treated as permission to generate a new key.

B14 remains public-only after package durability. Its private half is destroyed only after the package has been durably published to both independent package locations.

## 9. Exact CLI

Entry point remains `python3 scripts/operations/bamf_source_authority_bootstrap.py`. Exact flags live in `bootstrap-contract-v4.json`.

### 9.1 `operator-init`

Creates/resumes bootstrap-admin, C06, BAMF source, and C13-rights primary/recovery pairs, B14 public identity, package primary/recovery copies, and a protected canary bundle. It never prints private bytes.

### 9.2 `operator-verify`

Read-only verification of every retained pair and package copy. It recomputes public identities, manifest SHA, contract SHA, source revision, signer-record digest, canary digest, and exact package bytes.

### 9.3 `operator-canary`

Creates one fresh protected canary transfer from valid retained BAMF-source/C13-rights keys and the exact package. Existing conflicting final output fails.

### 9.4 `operator-c06-transfer`

Creates one fresh consumable C06 transfer by copying the exact validated retained C06 signer record. It verifies that SHA-256 of those exact bytes equals package `c06_signer_record_sha256`. It cannot generate or transform C06 key material. The transfer is temporary transport state, never recovery authority. Before activation failure it may remain only for an exact protected retry. After successful installation and durable final activation commitment, `host-install` unlinks it through its already-opened parent directory fd and fsyncs that parent. Only after cleanup succeeds may the immutable external/public receipt be published with `c06_transfer_cleanup_success=true`. `host-verify` applies the same unlink-before-receipt rule to any fresh verification transfer. If a crash occurs after registry plus activation commitment are final but before cleanup/receipt, the next `host-verify` may only validate the exact committed authority state, unlink and parent-fsync the exact transfer, then publish the missing receipt; it may not accept replacement administrative state. APFS blocks are not promised to be overwritten.

### 9.5 `operator-host-principal`

Uses only the bootstrap-admin private key. Inputs include exact package, target `IOPlatformUUID`, runtime user, UID, and GID. Output schema is `bilqis.mlx.c09-host-runtime-principal-authorization/v2`.

The signature covers exactly: schema, source revision, package SHA-256, host UUID, runtime user, runtime UID, runtime GID, and signer owner ID. `signer_owner_id` is `owner:bootstrap-admin`. Signing bytes are canonical JSON of exactly those signing fields, UTF-8, `sort_keys=true`, compact comma/colon separators, `ensure_ascii=false`, `allow_nan=false`, with no terminal newline.

C06 cannot create this artifact. The Studio does not receive the bootstrap-admin private key.

### 9.6 `host-install` and `host-verify`

Both require Darwin, EUID 0, valid sudo provenance, exact package plus independently obtained expected package SHA-256, signed runtime-principal authorization, fresh canary transfer, fresh C06 signer transfer plus expected SHA-256, and a public receipt output path.

The caller cannot select runtime UID/GID, owner IDs, scopes, registry bytes, destination paths, manifest path, or authority keys at host time.

## 10. Sudo provenance

Privileged commands require all of `SUDO_USER`, `SUDO_UID`, and `SUDO_GID`. UID and GID must use canonical unsigned decimal encoding and satisfy the v3 ranges. The username must match the frozen regex.

Before reading privileged transfers and again immediately before the first privileged mutation, the process MUST resolve system accounts and require:

- `pwd.getpwuid(uid).pw_name == SUDO_USER`
- `pwd.getpwnam(SUDO_USER).pw_uid == uid`
- `pwd.getpwnam(SUDO_USER).pw_gid == gid`

Missing, malformed, changed, or mismatched provenance fails. Direct root execution without valid sudo provenance fails.

Sudo provenance identifies the elevating host administrator. It does not select the runtime principal. Runtime identity comes only from the bootstrap-admin-signed host authorization.

### 10.1 Dedicated runtime privilege predicate

The signed runtime identity is necessary but not sufficient. `host-install`, the runtime-child smoke preflight, and `host-verify` MUST all prove the v4 machine predicate:

1. `runtime_uid > 0`;
2. `runtime_user != SUDO_USER`;
3. `pwd` lookups round-trip exact user/UID/GID;
4. `grp.getgrnam("admin").gr_gid` is absent from `os.getgrouplist(runtime_user, runtime_gid)`;
5. while EUID is 0, execute `/usr/bin/sudo -n -U <runtime_user> -l` with stdin `/dev/null`, `LC_ALL=C`, and otherwise-cleared environment except the fixed safe PATH;
6. accept only a nonzero exit plus the recognized C-locale “not allowed to run sudo” diagnostic for that exact runtime user and host; exit zero, password prompts, policy/plugin/configuration errors, or unrecognized output all reject.

This does not claim immunity from kernel/OS privilege-escalation vulnerabilities. It proves that #1030 did not deliberately admit configured administrative privilege into the runtime principal. If the predicate later stops passing, `host-verify` fails closed.

## 11. Host staging and metadata

Physical base is `/private/etc/entif-ai/bilqis`. Logical production paths remain:

- `/etc/entif-ai/bilqis/source-authority-registry.json`
- `/etc/entif-ai/bilqis/source-authority-signer.json`

The installer verifies the `/etc -> private/etc` alias exactly as the production reader does.

Pending package and canary are root:root regular files, mode `0400`, link count one, no extended ACL. Pending registry is root:root `0444`, link count one, no ACL. Pending signer is root:root `0400`, link count one, with exactly the authorized runtime UID `READ_DATA` ACL and nothing else.

Every pending host file follows one durability sequence: write exact bytes, fsync, F_FULLFSYNC, apply/verify metadata, descriptor readback, fsync, F_FULLFSYNC, close/reopen `O_NOFOLLOW`, verify bytes/digest/stat/ACL/link count, then fsync the Bilqis directory.

Before the final registry exists, exact valid package, canary, and activation-commitment pending files may be reused after a crash. Incomplete, malformed, or conflicting package/canary pending files may be removed and reconstructed from authenticated fresh transfers. An incomplete, malformed, or conflicting activation-commitment pending file may be removed and reconstructed only from the already-validated package, runtime-principal authorization, host identity, signer, registry projection, canary, and source-revision inputs. No pending file has authority by itself. After final signer publication with no registry, the signer is immutable; package/canary may be restaged and the exact registry pending file must agree with the immutable signer and approved package.

## 12. Exact Darwin signer ACL

The implementation extends the Darwin ACL parser with raw permission-mask retrieval through `acl_get_permset_mask_np`. `ACL_READ_DATA` is raw mask `2` on the supported Darwin SDK.

Signer acceptance requires:

- one and only one non-root extended ACL entry;
- tag `ALLOW`;
- principal kind `UID`;
- principal ID exactly the bootstrap-admin-authorized runtime UID;
- raw permission mask exactly `2`;
- no DENY entries;
- no other ALLOW entries;
- no unknown or extra permission bit.

Named permission decoding may be retained for diagnostics. Authorization is decided from the raw mask. EXECUTE, READ_ATTRIBUTES, READ_EXTATTRIBUTES, READ_SECURITY, SYNCHRONIZE, mutation rights, or any other bit fails.

## 13. Runtime-principal and runtime smoke proof

The host reconstructs the exact no-newline canonical signing bytes frozen in `bootstrap-contract-v4.json` and verifies the runtime-principal authorization with `bootstrap_admin_public` from the independently approved package. It also verifies package SHA, source revision, host UUID, local account name/UID/GID, and signer owner literal. No C06 signature is accepted for this administrative artifact.

After signer publication, a child process drops to the authorized runtime UID/GID and invokes the unchanged production signer reader. The smoke payload is exact schema `bilqis.mlx.c09-host-runtime-smoke/v1` from the v4 contract. It signs dependency `POLICY salience-policy:bootstrap-smoke` with C06. The privileged parent verifies the signature against the pending/final registry and records only the payload SHA-256 and public verification result. Private key bytes never enter a receipt or parent log.

## 14. Canary requirements

Canaries remain deterministic and public except signatures. C07 and A12 use the already frozen checked-in A01 identity and complete validation context. C13 proves the complete unchanged-support correction lifecycle with the exact production API, not a wrapper invented by the bootstrap tool.

The tool MUST:

1. construct `node: ArtifactNode` from the frozen C13 support template;
2. construct `dependency_index = DependencyIndex.build((node,))`;
3. construct and C13-rights-sign the frozen `CorrectionEvent`;
4. compute `queue = apply_correction(event, dependency_index, authority_registry)` and require `node.artifact_id` is held;
5. construct and BAMF-source-sign the frozen `RevalidatedArtifact` candidate;
6. construct exactly `frontier = RevalidationFrontier((candidate,))`;
7. compute `transition = revalidate_node(node, frontier, authority_registry)`;
8. require the transition equals the frozen unchanged expectation and `transition.changed is False`;
9. compute `progress = advance_revalidation(dependency_index, queue, transition, authority_registry)`;
10. require the resulting node preserves content digest and eligibility, `progress.queue.held_artifact_ids == ()`, `progress.queue.pending == ()`, and `progress.queue.history == (transition,)`.

The candidate `correction_receipt_sha256` MUST equal the correction event `source_receipt_sha256`. v4 freezes both to the same synthetic digest in the template. Changed-support requalification remains #529 territory and is not falsely claimed by this bootstrap canary.

## 15. Activation state machine

Registry publication remains the one-way activation boundary.

### 15.1 Pre-activation

Validate sudo provenance, the dedicated runtime privilege predicate, approved package digest, package, bootstrap-admin signature, C06 transfer, canaries, manifest/contract/source revision, registry projection, host metadata, and runtime identity. Stage package, canary, signer, registry, and the exact `bilqis.mlx.c09-host-activation-commitment/v1` with the exact durability rules. The activation commitment binds the package, runtime-principal authorization digest, bootstrap-admin public key, runtime user/UID/GID, host UUID, signer digest, registry digests, canary digest, and source revision. Its pending file MUST be durable and read back before registry publication.

### 15.2 Publish signer

Publish the exact C06 signer with `RENAME_EXCL`. Verify final metadata, exact raw ACL mask, exact signer bytes, and runtime-UID smoke. If this succeeds and registry is absent, recovery may only continue with the same signer/public identity.

### 15.3 Publish registry last

Only after every prior proof succeeds and the exact activation commitment is durably staged, publish the exact registry with `RENAME_EXCL`. This establishes `HOST_SYSTEM_V1`. Immediately promote the already-frozen activation commitment from pending to final with `RENAME_EXCL` and directory fsync. Then unlink and parent-fsync the exact temporary C06 transfer. Only after that cleanup succeeds publish the external/public receipt with cleanup success recorded. There is no normal rotation path.

### 15.4 Post-activation

Any rerun is verify-only. If the registry exists, exact activation commitment pending or final MUST also exist and match the registry, signer, package, host UUID, bootstrap-admin public key, and exact runtime-principal authorization. A crash after registry publication may only promote that already-durable commitment; it may not accept a newly issued authorization. Host drift, runtime privilege-predicate failure, changed registry bytes, changed signer public identity, changed runtime-principal authorization, wrong package, wrong scopes, or wrong metadata fails closed.

## 16. Receipt publication and exact values

Host receipt schema is `bilqis.mlx.c09-host-bootstrap-receipt/v3`. It records only public metadata and digests. `registry_record` is exactly `SourceAuthorityRegistry.to_record()` for the installed registry. It records:

- `registry_path = /etc/entif-ai/bilqis/source-authority-registry.json`
- `signer_path = /etc/entif-ai/bilqis/source-authority-signer.json`

Physical `/private/etc` traversal does not change these logical receipt values.

The receipt is never created directly at the final path. A same-directory pending receipt is sudo-UID/GID owned, regular, mode `0600`, link count one, no extended ACL. Exact bytes are written, fsynced, F_FULLFSYNCed, read back, then published with `RENAME_EXCL` and parent fsync. A crash can leave only a non-authoritative pending receipt. If final is absent, `host-verify` may remove/reconstruct an incomplete pending receipt or publish an exact complete pending receipt. A conflicting final receipt is never overwritten.

## 17. Exclusive size bounds

All numeric `limits` in `bootstrap-contract-v4.json` are exclusive upper bounds. Accepted file size MUST satisfy `0 < size < limit`. Equality with the configured bound rejects. This definition replaces the ambiguous v6 word “maximum.”

## 18. Exact implementation file set after design freeze

The v4-v8 design authorities already exist as design files. They are not implementation Creates.

Implementation may begin only after a fresh formal v8 PASS and then uses this exact classification:

Create:

- `bilqis_mlx/factory/source_binding_reservations.py`
- `scripts/operations/bamf_source_authority_bootstrap.py`
- `scripts/tests/operations/test_bamf_source_authority_bootstrap.py`
- `bilqis_mlx/factory/tests/sources/test_source_binding_reservations.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_host_source_authority_bootstrap.py`

Modify:

- `bilqis_mlx/factory/curriculum_definition.py`
- `bilqis_mlx/source_adapters/c13_episode.py`
- `bilqis_mlx/source_adapters/c13_episode_cases.py`
- `bilqis_mlx/source_adapters/c13_episode_release.py`
- `bilqis_mlx/runtime/_correction/owners/capability_support_materialization.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_source_authority/__init__.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_salience_signer/__init__.py`
- `bilqis_mlx/source_adapters/tests/test_c13_episode.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/source_authority_runtime/test_host_source_authority_custody.py`
- `docs/operations/BAMF_0_2_FIRST_STUDENT.md`
- `docs/operations/BAMF_0_2_PACKAGES.md`

Existing/frozen design authorities, not implementation files:

- `authority-manifest-v3.json`
- `bootstrap-contract-v4.json`
- `host-bootstrap-proposal-v8.md`
- all v4-v7 failed-review design artifacts

No root `FEATURE_LOG.md` is created.

## 19. Acceptance proof

#1030 cannot close on unit tests alone. Proof must establish:

1. v8 fresh formal review is 0 Blockers / 0 Majors before implementation starts.
2. Canonical contract/manifest/source-revision computations reproduce the frozen values.
3. Operator key and output crash prefixes recover without replacing a valid retained authority.
4. Bootstrap-admin and C06 private keys remain distinct and no runtime path can sign principal authorization.
5. Sudo provenance rejects direct root and inconsistent environment/account identity; the runtime privilege predicate rejects root/admin/sudo-authorized or sudo-admin-identical runtime principals.
6. Package self-approval fails; wrong independently supplied package digest fails.
7. C06 transfer bytes exactly equal retained signer bytes and package commitment, and temporary transfers are unlinked plus parent-fsynced after successful install/verify.
8. Registry projection produces exactly the four-owner `SourceAuthorityRegistry` record required by C09.
9. Wrong owner/scope/key/package/canary/host UUID/runtime account/metadata/link/ACL fails closed.
10. Exact raw signer ACL mask is READ_DATA only.
11. C07, A12, C13-rights, and the exact `DependencyIndex` / `RevalidationFrontier` / production-call unchanged C13 support lifecycle canaries pass with production verification code.
12. Runtime child loads the real fixed signer and completes the frozen domain-separated smoke signature.
13. The exact activation commitment is durable before registry publication; registry is published after signer and all pre-activation proofs, never before.
14. Activation-commitment and receipt publication survive every crash prefix without accepting replacement administrative state or leaving an authoritative partial final file.
15. Fresh generation zero binds `HOST_SYSTEM_V1` from the real fixed root with no patch/mock/caller path.
16. C13 enrollment proposal exposes the eligible external `atlas-approval:` signer when required.
17. Real supported `m3-ultra` proves root ownership, modes, ACLs, fixed readers, signer/public-key match, scopes, digest, and generation-zero binding.
18. Only after #1030 acceptance/provisioning may #528 rerun at exact head `e560ccbf6a62480ee0f079e8343b43c5583bc1ab` with `--max-steps 2`.

## 20. Recovery

An existing lineage recovers only by restoring exact old authority bytes and exact approved administrative state. Regenerating keys, editing scopes, changing registry bytes, or issuing a new host authorization is not recovery for an already-born lineage.

If exact material cannot be restored, stop. A new authority set implies a new lineage under separate authority, not silent repair.

## 21. Non-goals

#1030 does not build a general secret manager, live registry rotation, caller-selectable trust paths, environment-variable trust-root overrides, run-local first-writer establishment, or a second C09 consumer contract. It does not place external source-owner, C13-rights, or bootstrap-admin private keys into Bilqis runtime custody.

## 22. Gate

This v8 proposal and `bootstrap-contract-v4.json` are design artifacts only. No producer/provisioner implementation, production key ceremony, Studio write, or #528 rerun is authorized by their existence.

Freeze and push this design, then run new isolated Design Critic, Codebase Details, and Implementation Readiness reviews against one exact commit and pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Implementation unlocks only at aggregate 0 Blockers / 0 Majors.
