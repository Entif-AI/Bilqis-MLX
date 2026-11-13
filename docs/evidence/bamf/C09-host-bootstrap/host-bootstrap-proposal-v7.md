# BAMF-0.2 C09 Host Bootstrap Proposal v7

Issue: #1030
Status: frozen-design candidate; implementation remains prohibited until fresh formal EGM returns 0 Blockers / 0 Majors
Supersedes for future implementation: v6 at `585b0e6a8cdf28e6df920e231908f16b5b67bff9`
Preserves v4-v6 as immutable failed-review evidence

## 1. Decision

Production C09 remains a fixed-host, fail-closed public trust root. Production C06 remains a fixed-host private runtime signer. Bilqis runtime cannot choose either path, generate either authority as a side effect, repair them, rotate them, or establish trust from run-local state.

v7 repairs the formal v6 review without changing the accepted C09 consumer model. The four C09 registry identities and scopes in `authority-manifest-v3.json` remain unchanged. A fifth key, `owner:bootstrap-admin`, exists only in operator custody. It is not a C09 source authority and is never installed on the Studio. It signs the host-specific runtime-principal authorization. This separates administrative admission from the runtime-readable C06 key.

Initial activation is an explicit trusted-host-administrator act. The sudo invoker must supply the expected package SHA-256 obtained independently from the reviewed #1030 checkpoint. Package bytes cannot approve themselves. Run-local code, the Bilqis runtime, and an unprivileged first writer cannot establish `HOST_SYSTEM_V1`.

## 2. Formal v6 failure and required repairs

Fresh formal review of exact v6 commit `585b0e6a8cdf28e6df920e231908f16b5b67bff9` against pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c` failed:

- Design Critic: 1 Blocker / 6 Majors / 2 Nits.
- Codebase Details: 0 Blockers / 3 Majors / 1 Nit.
- Implementation Readiness: 0 Blockers / 8 Majors / 1 Nit.

The Blocker was an authority loop: v6 used the runtime-readable C06 private key to sign the supposedly independent runtime-principal authorization. A compromised authorized runtime could therefore forge administrative admission. v7 assigns that signature to the operator-only bootstrap-admin key.

The remaining findings are closed by the exact machine contract in `bootstrap-contract-v3.json` and the rules below: raw ACL-mask validation, atomic pending-to-final publication, exact pending metadata, explicit sudo provenance, an exact C06 transfer producer, deterministic registry projection, typed package identities, exact receipt paths, a fixed runtime-smoke payload, coherent C13 revalidation canaries, and a frozen C13 reservation API.

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

All sudo-capable host administrators are inside this host-administration threat boundary. Protecting a machine against a malicious root administrator is outside #950/#1030. Protecting C09 from an unprivileged process, Bilqis runtime compromise, run-local state, package self-approval, path substitution, and accidental first-write races remains in scope.

## 4. Machine authority and revision identity

The machine-readable design authority is:

- authority manifest: `authority-manifest-v3.json`
- manifest SHA-256: `8aeedc9d0cd0de5d2e842eb98d12fdc5e194c7ee6f704cf2f538d3433ada6ac1`
- bootstrap contract: `bootstrap-contract-v3.json`
- contract SHA-256: `6a872da90ade985501a1c1cbd7fdeeecf4a5717d2a3d87d76288a284b1bd7194`
- source-revision domain: `bilqis.mlx.c09-host-bootstrap-source/v3`
- source revision: `008d9438116354a7a357bd66dbd97abe7769d50611459c00561618c9b530fa31`

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

The module exports exactly one C13 singleton named `C13_EPISODE_SOURCE_BINDING_RESERVATION`, whose seven values equal `bootstrap-contract-v3.json.binding_reservation`.

Wiring is fixed:

- `c13_episode.py` aliases capability, generator, and oracle IDs from the singleton.
- `c13_episode_cases.py` aliases source family from the singleton.
- `c13_episode_release.py` builds the C13 `CapabilitySourceBinding` from the singleton.
- `validate_source_bindings()` applies the reservation collision rule on every Factory compile/release verification.
- C13 capability-support materialization derives the correction rights prefix from the singleton.

Do not add fields to `CapabilitySourceBinding` for #1030. A foreign or ambiguous occupant of the reserved capability/source family/prefix fails before a release can become source-qualified.

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

Entry point remains `python3 scripts/operations/bamf_source_authority_bootstrap.py`. Exact flags live in `bootstrap-contract-v3.json`.

### 9.1 `operator-init`

Creates/resumes bootstrap-admin, C06, BAMF source, and C13-rights primary/recovery pairs, B14 public identity, package primary/recovery copies, and a protected canary bundle. It never prints private bytes.

### 9.2 `operator-verify`

Read-only verification of every retained pair and package copy. It recomputes public identities, manifest SHA, contract SHA, source revision, signer-record digest, canary digest, and exact package bytes.

### 9.3 `operator-canary`

Creates one fresh protected canary transfer from valid retained BAMF-source/C13-rights keys and the exact package. Existing conflicting final output fails.

### 9.4 `operator-c06-transfer`

Creates one fresh consumable C06 transfer by copying the exact validated retained C06 signer record. It verifies that SHA-256 of those exact bytes equals package `c06_signer_record_sha256`. It cannot generate or transform C06 key material.

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

The host reconstructs the exact no-newline canonical signing bytes frozen in `bootstrap-contract-v3.json` and verifies the runtime-principal authorization with `bootstrap_admin_public` from the independently approved package. It also verifies package SHA, source revision, host UUID, local account name/UID/GID, and signer owner literal. No C06 signature is accepted for this administrative artifact.

After signer publication, a child process drops to the authorized runtime UID/GID and invokes the unchanged production signer reader. The smoke payload is exact schema `bilqis.mlx.c09-host-runtime-smoke/v1` from the v3 contract. It signs dependency `POLICY salience-policy:bootstrap-smoke` with C06. The privileged parent verifies the signature against the pending/final registry and records only the payload SHA-256 and public verification result. Private key bytes never enter a receipt or parent log.

## 14. Canary requirements

Canaries remain deterministic and public except signatures. C07 and A12 use the already frozen checked-in A01 identity and complete validation context. C13 must prove the complete unchanged-support correction lifecycle:

1. construct the frozen dependency index containing `capability-support:Z.C13_EPISODE`;
2. call `apply_correction()` with the C13-rights event;
3. prove the capability-support artifact is held;
4. call `revalidate_node()` with BAMF-source signed candidate;
5. call `advance_revalidation()`;
6. require an unchanged transition, cleared hold, and no newly propagated work.

The candidate `correction_receipt_sha256` MUST equal the correction event `source_receipt_sha256`. v3 freezes both to the same `777...777` digest in the synthetic template. Changed-support requalification remains #529 territory and is not falsely claimed by this bootstrap canary.

## 15. Activation state machine

Registry publication remains the one-way activation boundary.

### 15.1 Pre-activation

Validate sudo provenance, approved package digest, package, bootstrap-admin signature, C06 transfer, canaries, manifest/contract/source revision, registry projection, host metadata, and runtime identity. Stage package, canary, signer, registry, and the exact `bilqis.mlx.c09-host-activation-commitment/v1` with the exact durability rules. The activation commitment binds the package, runtime-principal authorization digest, bootstrap-admin public key, runtime user/UID/GID, host UUID, signer digest, registry digests, canary digest, and source revision. Its pending file MUST be durable and read back before registry publication.

### 15.2 Publish signer

Publish the exact C06 signer with `RENAME_EXCL`. Verify final metadata, exact raw ACL mask, exact signer bytes, and runtime-UID smoke. If this succeeds and registry is absent, recovery may only continue with the same signer/public identity.

### 15.3 Publish registry last

Only after every prior proof succeeds and the exact activation commitment is durably staged, publish the exact registry with `RENAME_EXCL`. This establishes `HOST_SYSTEM_V1`. Immediately promote the already-frozen activation commitment from pending to final with `RENAME_EXCL` and directory fsync, then publish the external/public receipt. There is no normal rotation path.

### 15.4 Post-activation

Any rerun is verify-only. If the registry exists, exact activation commitment pending or final MUST also exist and match the registry, signer, package, host UUID, bootstrap-admin public key, and exact runtime-principal authorization. A crash after registry publication may only promote that already-durable commitment; it may not accept a newly issued authorization. Host drift, changed registry bytes, changed signer public identity, changed runtime-principal authorization, wrong package, wrong scopes, or wrong metadata fails closed.

## 16. Receipt publication and exact values

Host receipt schema is `bilqis.mlx.c09-host-bootstrap-receipt/v3`. It records only public metadata and digests. `registry_record` is exactly `SourceAuthorityRegistry.to_record()` for the installed registry. It records:

- `registry_path = /etc/entif-ai/bilqis/source-authority-registry.json`
- `signer_path = /etc/entif-ai/bilqis/source-authority-signer.json`

Physical `/private/etc` traversal does not change these logical receipt values.

The receipt is never created directly at the final path. A same-directory pending receipt is sudo-UID/GID owned, regular, mode `0600`, link count one, no extended ACL. Exact bytes are written, fsynced, F_FULLFSYNCed, read back, then published with `RENAME_EXCL` and parent fsync. A crash can leave only a non-authoritative pending receipt. If final is absent, `host-verify` may remove/reconstruct an incomplete pending receipt or publish an exact complete pending receipt. A conflicting final receipt is never overwritten.

## 17. Exclusive size bounds

All numeric `limits` in `bootstrap-contract-v3.json` are exclusive upper bounds. Accepted file size MUST satisfy `0 < size < limit`. Equality with the configured bound rejects. This definition replaces the ambiguous v6 word “maximum.”

## 18. Exact implementation file set after design freeze

The v4-v7 design authorities already exist as design files. They are not implementation Creates.

Implementation may begin only after a fresh formal v7 PASS and then uses this exact classification:

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
- `bootstrap-contract-v3.json`
- `host-bootstrap-proposal-v7.md`
- all v4-v6 failed-review design artifacts

No root `FEATURE_LOG.md` is created.

## 19. Acceptance proof

#1030 cannot close on unit tests alone. Proof must establish:

1. v7 fresh formal review is 0 Blockers / 0 Majors before implementation starts.
2. Canonical contract/manifest/source-revision computations reproduce the frozen values.
3. Operator key and output crash prefixes recover without replacing a valid retained authority.
4. Bootstrap-admin and C06 private keys remain distinct and no runtime path can sign principal authorization.
5. Sudo provenance rejects direct root and inconsistent environment/account identity.
6. Package self-approval fails; wrong independently supplied package digest fails.
7. C06 transfer bytes exactly equal retained signer bytes and package commitment.
8. Registry projection produces exactly the four-owner `SourceAuthorityRegistry` record required by C09.
9. Wrong owner/scope/key/package/canary/host UUID/runtime account/metadata/link/ACL fails closed.
10. Exact raw signer ACL mask is READ_DATA only.
11. C07, A12, C13-rights, and full unchanged C13 support lifecycle canaries pass with production verification code.
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

This v7 proposal and `bootstrap-contract-v3.json` are design artifacts only. No producer/provisioner implementation, production key ceremony, Studio write, or #528 rerun is authorized by their existence.

Freeze and push this design, then run new isolated Design Critic, Codebase Details, and Implementation Readiness reviews against one exact commit and pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Implementation unlocks only at aggregate 0 Blockers / 0 Majors.
