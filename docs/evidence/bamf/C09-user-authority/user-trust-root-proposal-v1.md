# #1031 minimal ordinary-user C09 authority contract

Status: BAMF-0.2 launch-path remediation.

## Purpose

Remove the root-owned `/etc/entif-ai/bilqis/*` requirement that blocked the real BAMF
trainer path. This child does not create a new cryptographic architecture. It reuses
the existing C09 registry, digest, signer verification, accepted-custody binding, and
drift-rejection behavior already present in the trainer.

## Fixed ordinary-user location

On Darwin, production C09 files live under the effective OS account's home directory:

- `.entif-ai/bilqis/source-authority-registry.json`
- `.entif-ai/bilqis/source-authority-signer.json`

The account home is resolved from `geteuid()` plus the OS account database. `$HOME`,
XDG variables, CLI/config values, package input, current working directory, and the run
directory cannot select another production authority path. EUID 0 is rejected because
BAMF-0.2 must not require privileged execution.

The reader requires a regular file owned by the effective UID and enforces the existing
size bounds. The final path component is opened with `O_NOFOLLOW`. No `sudo`, root/admin
membership, privileged helper/daemon, ACL escalation, or system-owned write is required.

## Existing authority semantics remain unchanged

`read_host_system_source_authority_registry()` continues to parse the existing
`SourceAuthorityRegistry` record. `SourceAuthorityRegistry.digest` remains the semantic
registry identity. Generation zero records the existing `HOST_SYSTEM_V1` origin, exact
registry record, and digest in accepted custody; resume re-reads the fixed account file
and rejects record/digest drift exactly as before.

The existing C06 signer reader moves to the same fixed ordinary-user account store and
still verifies its derived public key and requested scope against the accepted C09
registry. #1031 does not generate keys, redesign roles/scopes, add rotation, or create
new signing formats.

## Proof boundary

Focused tests prove:

1. the path derives from EUID plus the OS account database and ignores `$HOME`/cwd;
2. neither registry nor signer reader accepts a caller-selected path;
3. root execution, missing files, symlink final files, wrong ownership, wrong type,
   oversize files, and malformed registry/signer records fail closed;
4. existing accepted-lineage exact-match and drift rejection remain green;
5. no test writes `/etc`, requires privilege, or starts a learner.

## Deferred until after the first BAMF trainer is end-to-end testable

New PKI hierarchy, authority-role census redesign, cross-role key-separation policy,
canonical-JSON byte policing beyond the existing semantic digest, generalized key
rotation, secret-manager behavior, and elaborate ACL/installer/recovery hardening are
not launch blockers unless a current BAMF-0.2 requirement or observed trainer failure
proves otherwise.
