# #1031 unprivileged per-user C09 authority contract v1

Status: design-only; implementation remains gated on fresh EGM review.

## Decision

BAMF authority bootstrap and runtime consumption require no `sudo`, root, administrator
membership, privileged helper/daemon, ACL escalation, or system-owned write.  The
fixed `/etc/entif-ai/bilqis/*` placement selected by #950/#1010 is superseded for new
BAMF-0.2 lineages.

The security invariant is narrower than OS privilege: callers and Bilqis runtime APIs
cannot select an authority path or create a trust root as a side effect of normal
execution.  A process already executing arbitrary code as the same OS user is inside
that user's blast radius; #1031 does not pretend ordinary-user DAC can make such a
process less powerful than its own account.  Accepted lineage instead detects trust
root substitution by binding and rechecking the exact canonical registry record and
semantic digest.

## Fixed account-scoped location

The production authority home is derived only from the effective OS account:

1. `euid = os.geteuid()`; EUID 0 is rejected.
2. Resolve `pwd.getpwuid(euid).pw_dir`; `$HOME`, XDG variables, CLI/config values,
   current working directory, package paths, and run directories are not consulted.
3. Open that home and traverse, descriptor-relative with `O_NOFOLLOW`, the fixed
   components `.entif-ai/bilqis/source-authority`.
4. Registry filename is `source-authority-registry.json`.
5. C06 signer filename is `source-authority-signer.json`.

The three authority-directory components are regular directories owned by the
effective UID, mode `0700`, with no extended ACL entries.  Final authority files are
single-link regular files owned by the effective UID, mode `0400`, with no extended
ACL entries.  Registry and signer readers expose no pathname argument.  Missing files
fail as `BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED`; unsafe ownership, type,
mode, ACL, link count, size, symlink traversal, or malformed bytes fail closed.

The serialized origin literal `HOST_SYSTEM_V1` remains unchanged for lineage
compatibility.  It now denotes the fixed OS-account authority store, not a root-owned
machine-global `/etc` file.

## Canonical registry projection

`authority-manifest-v1.json` is the complete BAMF-0.2 newborn public-authority census
for this child.  It contains four and only four owners: C06 priority authority, B14
cache identity, BAMF external source authority, and C13 source-rights authority.
`owner:bootstrap-admin` does not exist in this contract.

Projection accepts an exact mapping from those four owner IDs to Ed25519 public-key
hex strings.  It adds the manifest scopes, sorts scopes by `(kind.value, key_prefix)`,
sorts keys by `owner_id`, and constructs the existing
`bilqis.c09.source-authority-registry/v2` `SourceAuthorityRegistry`.  Missing or extra
owners reject.  #1031 never creates or imports a private key.

Canonical registry file bytes are exactly `SourceAuthorityRegistry.to_record()`
encoded as UTF-8 JSON with `sort_keys=true`, compact comma/colon separators,
`ensure_ascii=false`, `allow_nan=false`, and one terminal LF.  The existing
`SourceAuthorityRegistry.digest` remains the semantic registry digest; SHA-256 of the
canonical file bytes is a separate storage checksum and does not redefine C09
semantic identity.  The production reader rejects noncanonical encodings.

## Lineage behavior

- Generation zero reads only the fixed account store and records the existing
  `HOST_SYSTEM_V1` origin, exact registry record, and semantic digest.
- Accepted successors inherit that tuple exactly.
- Runtime has no production API that writes, replaces, rotates, repairs, or selects
  the account trust root.
- If account-store registry bytes later differ, canonical parsing and the accepted
  record/digest comparison fail closed before the changed root can authorize the
  accepted lineage.
- A registry copied into a run directory, checkout, package, current directory, or
  alternate environment-selected location has no authority for a new lineage.
- Historical pre-#950 run-local compatibility behavior remains unchanged.

## Implementation surface

Modify:

- `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_source_authority/__init__.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/_darwin_salience_signer/__init__.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/source_authority_custody/__init__.py`
- `bilqis_mlx/runtime/_teacher/priority_authority.py`
- focused source-authority path/custody/resolution and C06 signer tests
- `docs/operations/BAMF_0_2_FIRST_STUDENT.md`
- `docs/operations/BAMF_0_2_PACKAGES.md`

Create:

- `bilqis_mlx/runtime/_custody/bamf_bundle/source_authority_custody/registry_projection.py`
- focused projection tests

The two existing Darwin modules retain their names because BAMF-0.2/MLX production is
Darwin-hosted; their privilege semantics change from root-owned host files to fixed
ordinary-user files.  No compatibility alias to the old `/etc` path remains.

## Proof

Focused tests must prove:

1. account resolution uses EUID + `pwd`, ignoring hostile `$HOME`/XDG/cwd values;
2. production readers accept no path argument and traverse only the fixed components;
3. EUID 0, missing authority, symlinks, wrong UID/type/mode/ACL/link count, oversize,
   malformed JSON, and noncanonical registry bytes fail closed;
4. projection is input-order independent and produces the exact four-owner scope set;
5. missing/extra owner identities and invalid keys reject;
6. canonical registry bytes are stable and terminal-LF-delimited;
7. existing accepted-lineage exact-match and drift rejection remain green;
8. C06 signer public identity must still match the projected C06 registry owner;
9. no test or implementation writes `/etc`, requires privilege, or starts a learner.

## Non-goals

#1031 does not generate private keys, publish/install authority files, implement
recovery copies, add C13 source-binding collision enforcement, activate a Studio, run
#528, rotate accepted authority, or build a general secret manager.  Those outcomes
belong to #1032-#1035.
