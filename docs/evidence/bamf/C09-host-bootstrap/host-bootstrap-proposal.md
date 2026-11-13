# C09 host-bootstrap remediation proposal

Status: PROPOSED v4 / issue #1030 / implementation frozen pending fresh review.

Reviewed integration base: `97a018ed7e9697fe284abd9fa8197cd7f4194b45`.

## Problem

C16.1c/#950 correctly made the C09 registry a fixed host-administered trust root at
`/etc/entif-ai/bilqis/source-authority-registry.json`, but no durable owner ever
materialized the registry bytes or the key set from which they are derived. C03.4b/#1010
later added `/etc/entif-ai/bilqis/source-authority-signer.json` for C06 priority signing
without defining host provisioning for that private key. The real #528 Studio witness
therefore fails before generation-zero mutation with
`BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED`.

The repair must establish the missing producer side without weakening #950. Runtime code
still may not select, create, replace, repair, or rotate the C09 trust root. Host bootstrap
is an explicit administration operation that occurs before a new lineage is born.

## Architecture checkpoint

### Verified facts

- #950 binds one exact host registry record/digest at generation zero and requires exact
  inheritance for successors; live rotation is unsupported.
- #1010's production C06 issuer needs a private Ed25519 signer whose public identity and exact
  salience scopes are already trusted by C09.
- B14 production cache custody requires exactly one registry key whose sole scope is
  `ARTIFACT cache:`.
- current C07 v2 requires a signed `AtlasSourceApproval` but deliberately removed the old
  per-delta `atlas-delta:` signature.
- A12/C12 verifies signed source-owner export clearance under `ARTIFACT a12-export:`.
- C13 retained support carries a `RIGHTS rights:` dependency, and C09 requalification of that
  support requires artifact authority for the narrow
  `capability-support:Z.C13_EPISODE` prefix namespace.

### Trust assumption preserved from #950

The selected Bilqis interpreter/process and its provisioned runtime OS principal are one
trusted execution principal. #1030 protects the signer from other host users and from
caller-selected write/ACL/path authority; it does not claim to isolate hostile code already
running as that trusted principal. A future same-UID sibling-process threat requires a new OS
capability/process boundary.

### Rejected alternatives

- **Caller- or run-supplied registry:** recreates first-writer trust and violates #950.
- **One key for every role:** collapses C06, B14, and external source-owner authority and makes
  prefix mistakes cross-domain privilege escalations.
- **Broad correction key:** over-authorizes namespaces for which no current producer exists.
- **Root launchd signing broker:** changes the #1010 consumer architecture and still does not
  protect against a compromised same-UID client without a stronger process-identity contract.
- **Actual C07 lease/approval fixed at bootstrap:** freezes future human/source authorization
  too early. Bootstrap proves the immutable signer identity and scope; a real approval remains
  a later source-owner decision bound to the then-current release and rights evidence.

### Recommendation

Freeze the three-role manifest below, prove each role with typed canaries, install the C06
signer before the registry, and make the final registry rename the one-way activation point.
Any later owner, key, or scope is an explicit registry migration, not an in-place bootstrap
repair.

## Authority census and frozen newborn registry

A new `HOST_SYSTEM_V1` lineage inherits its exact C09 registry record and digest forever
under the current #950 contract. The bootstrap must therefore provision every authority
identity already required by the executable BAMF-0.2 path. It must not grant speculative
catch-all prefixes.

The newborn registry contains exactly these three keys.

The reviewed role/scope contract is also recorded in
`authority-manifest-v1.json`. Bootstrap code may validate that checked-in manifest, but no
runtime caller, CLI argument, environment variable, or external JSON may replace or extend it.

### 1. C06 priority authority

Owner ID: `owner:c06`.

The matching private key is host-local and is used only by the existing C06 production
priority issuer. Its registry scopes are:

- `POLICY` / `salience-policy:`
- `SOURCE` / `salience-fact:`
- `ARTIFACT` / `salience-option:`
- `ARTIFACT` / `salience-event:`

These are the exact dependency families emitted by
`runtime/_teacher/priority_authority.py`. The bootstrap does not add
`salience-row:` or `salience-annotation:` because the current production path has no
source-owner issuer for those optional artifacts.

### 2. B14 cache authority identity

Owner ID: `owner:b14-cache`.

Its sole scope is `ARTIFACT` / `cache:`. This key MUST have no second scope because
`atlas_cache_production_custody._cache_registry_key()` requires exactly one registry key
whose only allowed scope is `cache:`. B14 uses the registered public key as the accepted
cache-artifact authority identity; it does not use the Ed25519 private key for detached
signatures. Bootstrap generates a valid Ed25519 pair, records the public key, and destroys
the private half before the registry is installed.

### 3. External BAMF source owner

Owner ID: `owner:bamf-source`.

The private key is never installed on the Studio and is never available to Bilqis runtime.
The operator/source owner retains it outside the runtime host. The registry carries only its
public key with these current production scopes:

- `ARTIFACT` / `atlas-approval:`
- `ARTIFACT` / `a12-export:`
- `ARTIFACT` / `capability-support:Z.C13_EPISODE`
- `RIGHTS` / `rights:`

The first scope authorizes the signed `AtlasSourceApproval` consumed by current C07 v2
enrollment and renewal. The second preserves the already-implemented A12/C12 export
clearance boundary. The third authorizes revalidation only inside the reserved C13 episode
capability-support prefix namespace. C09 scopes are prefix scopes by contract; this grant is
therefore intentionally a namespace grant, not an exact-string grant. Before registry
activation, bootstrap MUST prove that every currently admitted/source-qualified capability ID
whose resulting artifact ID starts with `capability-support:Z.C13_EPISODE` belongs to the same
C13 episode source family, and that the required witness artifact is exactly
`capability-support:Z.C13_EPISODE`. Any foreign or ambiguous occupant of that prefix rejects
bootstrap. The fourth scope authorizes source-owner correction of the exact namespaced rights
dependencies already embedded in C13 training rows and retained C09 support. These are
source-owner statements and may share one external source-owner identity for the first BAMF
lineage.

The historical C07 v1 `atlas-delta:` signature is deliberately absent. #958 replaced that
fixture-only signer contract with the signer-free v2 A09/Factory handoff. Generic C09
correction APIs do not justify catch-all SOURCE, POLICY, TIME, RELEASE, OPERATOR, or ARTIFACT
prefixes. C13.2 can exercise a real correction through the already-namespaced `RIGHTS` /
`rights:` dependency. A future new source owner or a new correction authority family requires
an explicit governed registry-migration design. The bootstrap does not silently pre-authorize
unknown future signers.

## Key custody

### Public registry

The canonical `bilqis.c09.source-authority-registry/v2` bytes are public trust material.
The final registry is UID 0 owned, not group/world writable, and installed through the exact
fd-relative Darwin boundary already enforced by #950. Mode `0444` is acceptable for the
final public registry after atomic installation.

### C06 private signer

The current #1010 reader loads the C06 Ed25519 private key into the trusted Bilqis process.
#950 already treats the Bilqis interpreter, loaded project code, and host administrator as a
trusted execution boundary. #1030 preserves that boundary rather than introducing a second
privileged signing service.

The signer file is UID 0 owned with mode `0400`. A root-installed Darwin ACL grants read
access to exactly one non-root UID: the selected Bilqis runtime principal. The signer reader
must verify after open that:

1. the object is a regular UID-0-owned file;
2. group and other mode bits are zero;
3. no non-root ACL entry grants a mutation permission;
4. the only non-root `ALLOW` principal is the process EUID;
5. no group `ALLOW` entry is present; and
6. the derived public key exactly matches `owner:c06` in the accepted C09 registry before a
   signature is returned.

Successful `O_RDONLY` open plus mode `0400` proves that the selected EUID's root-installed
ACL supplies the required read authority. A different runtime user cannot select itself into
the trust boundary because it cannot alter the root-owned ACL. Compromise of the selected
runtime OS principal is treated as compromise of the trusted Bilqis execution principal and
is outside this remediation's threat model.

The provisioning receipt never includes `private_key_hex` or any reversible secret.

### External source-owner private key

`owner:bamf-source` is generated on the operator host into a non-repository file with mode
`0600`, with an exact protected recovery copy at a second explicit non-repository path. The
Studio bootstrap receives only its public key. A small operator-side signer may
issue typed source-owner records required by the current BAMF path: `AtlasSourceApproval`,
`ExportClearanceReceipt`, and a C09 `CorrectionEvent` whose dependency is exactly `RIGHTS`
with a `rights:` key, plus the C13 `RevalidatedArtifact` / transition needed to requalify the
`capability-support:Z.C13_EPISODE` namespace witness. It does not expose a raw
arbitrary-payload signing command. The tool must never expose the private seed in stdout,
logs, Git, issue bodies, receipts, or the Studio registry.

## Bootstrap operation

Add one administration tool outside the `bilqis_mlx` runtime package. It has two explicit
operations.

### Operator source-owner initialization

The non-root operator command creates `owner:bamf-source` once, writes its private-key record
to an explicit non-repository primary path and an explicit protected recovery path with mode
`0600`. Both files are written through same-directory temporary files, fsynced, atomically
renamed, directory-fsynced, and read back byte-for-byte. Only after both durable copies match
does initialization print or write the public identity needed by host provisioning. Existing
different key material, a missing recovery copy, or divergent copies fail closed. Exact rerun
is idempotent.

If the primary key is later lost, operator recovery restores only the exact recovery bytes and
requires the restored public identity to match the already-provisioned registry. A new private
key is never generated as recovery for an accepted lineage. The operator's normal protected
backup system must include the recovery path; #1030 does not invent an external secret-storage
service.

Initialization also emits a public bootstrap-canary bundle signed by that same private key.
The bundle contains disposable, non-run-authoritative instances of the four exact authority
families granted to `owner:bamf-source`: an `AtlasSourceApproval`, an
`ExportClearanceReceipt`, a C09 `CorrectionEvent` over `RIGHTS` / `rights:`, and the exact
`RevalidatedArtifact` / transition form for `capability-support:Z.C13_EPISODE`. Canary records
use fixed bootstrap-only identities and digests and confer no lease, export, correction, or
requalification authority on a real run. The bundle contains no private key bytes.

### Root host provisioning

The privileged command requires Darwin, EUID 0, the selected runtime account, and the
external source-owner public canary bundle. It derives the external public key from that
bundle. It does not accept an arbitrary registry JSON or a list of scopes. The three owner IDs
and scope sets above are code constants of the administration contract.

On first provisioning it:

1. resolves the selected runtime account to one UID;
2. generates the C06 host signer and the disposable B14 identity pair;
3. destroys the B14 private half after deriving its public key;
4. constructs and validates the canonical registry through `SourceAuthorityRegistry`;
5. creates or verifies the root-owned `/private/etc/entif-ai/bilqis` chain;
6. writes complete fixed-name pending registry and signer files in that directory;
7. fsyncs each pending file and applies final owner, mode, and signer read-only ACL state;
8. validates the pending signer against the pending registry, verifies the external canary
   signatures through the real C07/A12/C09 contract objects, and exercises the B14 key
   selector;
9. atomically renames the signer to its fixed final name and fsyncs the directory;
10. atomically renames the registry to its fixed final name **last** and fsyncs the directory;
    this registry rename is the bootstrap activation boundary; and
11. rereads both through the production readers before reporting success.

Before step 10, generation zero still fails closed because the fixed registry is absent. A
crash after the final signer rename but before registry activation leaves the exact pending
registry available for idempotent completion. A crash after registry activation leaves both
authority files complete; rerun performs verify-only recovery and recreates only the public
receipt if needed. Pending files are never interpreted by Bilqis runtime.

If both final files already exist, bootstrap enters verify-only mode. Exact expected state
returns the existing receipt. A final signer with absent final registry is recoverable only
when the root-owned pending registry exactly binds that signer's derived public key, the
external source-owner key, and the B14 identity. Every other partial or conflicting state
fails closed. Any key, registry, owner, mode, ACL, schema, or digest mismatch is rotation, not
repair. The tool never mutates a different live root in place.

Before either final file exists, pending files are unactivated bootstrap scratch, not accepted
authority. Bootstrap validates their fixed names, root ownership, regular-file shape, safe
mode/ACL state, and content before using them. An exact complete pending signer+registry pair
may resume. A lone or incomplete pending file may be removed and recreated by the privileged
bootstrap owner because no final signer or registry has crossed an activation boundary yet.
Once the final signer exists, that freedom ends: only the exact pending registry that binds the
final signer's public key may complete activation. Once the final registry exists, the whole
bootstrap is verify-only.

## Receipt and recovery

The host-admin receipt contains only public facts: schema version, tool/source revision,
registry record and digest, owner IDs, public keys, scope records, runtime UID, fixed paths,
final mode/ownership summaries, a digest of the external canary bundle, and a digest of the
private signer record. It contains no private key bytes. The canaries prove possession and
scope compatibility only; they are not a future Atlas lease, export clearance, or correction
event and are not replayed into any run.

The exact C06 signer record must be included in the host's protected backup/recovery system.
The exact external source-owner recovery record must likewise remain in the operator's
protected backup/recovery system. Recovery of an accepted lineage restores the exact old
registry, C06 signer bytes, and external source-owner key under their original custody or
stops. A new C06 key, B14 identity, external source key, owner ID, or scope set is registry
migration and is forbidden by #950 until separately governed.

## Implementation surfaces

Expected bounded changes:

- new administration module/script under `scripts/operations/`;
- focused administration tests under `scripts/tests/`;
- signer-specific custody validation in
  `runtime/_custody/bamf_bundle/_darwin_salience_signer/`;
- focused C06 signer custody tests;
- `docs/operations/BAMF_0_2_FIRST_STUDENT.md` host-bootstrap instructions and stale #1010
  status repair; and
- this #1030 evidence packet and final receipt.

The C09 fixed registry reader, accepted-custody origin/inheritance rules, generation-zero
publication contract, C07 v2 signer-free delta authority, neural model, optimizer, and learner
remain unchanged.

## Proof gates

Before real provisioning:

- canonical registry composition is literal and deterministic;
- the registry contains exactly the three owner IDs and exact scopes above;
- B14 has exactly one `cache:`-only key;
- C06 signer public identity matches its registry entry;
- external source-owner private material never appears in the host output or receipt;
- signer mode `0644`, `0640`, wrong EUID ACL, group ALLOW, mutating ACL, wrong owner, symlink,
  malformed signer, and key mismatch all fail closed;
- exact bootstrap retry is idempotent and conflicting retry refuses rotation;
- external source-owner creation proves durable primary+recovery atomicity, exact restore, and
  replacement-key refusal before its public key may enter host bootstrap;
- current C07 v2 `atlas-approval:` verification succeeds and no `atlas-delta:` scope is
  required;
- A12 export-clearance verification succeeds under the external source-owner key;
- an external source-owner `RIGHTS rights:` correction holds the C13 capability support, and
  `ARTIFACT capability-support:Z.C13_EPISODE` namespace revalidation can requalify it, while
  SOURCE, POLICY, TIME, RELEASE, OPERATOR, and ARTIFACT keys outside that reserved namespace
  reject;
- bootstrap rejects if any currently admitted/source-qualified non-C13-episode capability
  would produce a capability-support artifact whose ID starts with the reserved C13 episode
  prefix;
- a production B14 cache authority can select exactly its `cache:` key; and
- generation-zero preflight binds the resulting registry as `HOST_SYSTEM_V1` with no
  run-local or caller-selected fallback.

Crash-prefix tests cover pending-file creation/fsync, signer rename and directory fsync,
registry activation rename and final fsync. `signer present + registry absent` is resumable
only from the exact root-owned pending registry. Any state with a final registry present must
already have the exact final signer; it is verify-only and never repaired or rotated.
Additional precommit cases prove convergence from pending-signer-only, pending-registry-only,
and both-complete-pending states while both final files remain absent.

After software proof and fresh review, provision the real `m3-ultra` host through the
privileged operation. Verify production registry readback and one bounded C06 signing round,
then rerun #528 at exact branch head
`e560ccbf6a62480ee0f079e8343b43c5583bc1ab`. No neural workload belongs to #1030 itself.
