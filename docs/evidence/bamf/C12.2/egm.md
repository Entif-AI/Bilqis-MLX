# C12.2 local exchange review and proof

Consumed unified/Lane C: `70e37ae27214061dcc1712503eae6741a2e3781e`.
Consumed same-C #525 source: `30385b0f245e820657b8c8e71f762eb6f9c0e40e`.
Production exchange implementation: `990eeadbb5d0e05ab1192bb6be0eda00faed24ec`.
Reviewed repair: `1ea55f40e85d165badd7a00cd506eaafd6cc8a66`.

Fresh-context independent reviewer: `/root/c526_exchange_review`, forked with no
conversation history. The reviewer verified the pinned EGM checkout at
`b3a35956759bf7f024af2ff061b2e0b44b438e4c` and read `docs/codex.md`,
`agents/codebase_details.md` and `agents/comprehension.md`, the plan, implementation,
mirrored tests, operations documentation and direct package contract owners.
The review was read-only and did not rerun tests.

Initial finding: documentation claimed regular-file ownership verification, while
code verifies type and refuses symlinks within a trusted local directory. The
wording is corrected. The reviewer also requested post-link directory-fsync
failure coverage/documentation. The repair adds an injected failure, verifies the
complete addressed bytes survive with no temporary file, retries publication and
checks unchanged mtime. Documentation states this partial-publication boundary.

The targeted independent re-audit of `990eeadb..1ea55f40` resolved both findings
and found no new ones. Scoped exchange/staging disposition: PASS. This does not
clear full #526 acceptance or production rights/adoption.

## Executed proof

- Red: exchange test import fails because the API does not exist before the patch.
- Green: 32 package tests, zero failures, zero skips (18 inherited +14 exchange).
- Clean built-wheel install: the same32 tests pass from `/tmp`, outside the source
  tree, including a fresh isolated-process canonical decode.
- Two actual temporary node directories preserve exact package bytes and digests;
  idempotent and eight concurrent publications converge without temporary files.
- Heterogeneous exact package is TEACHING_ONLY. Incompatible motif-bound delta,
  tampered/noncanonical wire, symlinks, oversized wire and receiver conflict reject.
- File-flush and create-link interruption leave no partial addressed file.
  Directory-flush interruption leaves complete retryable bytes and does not report
  success. No payload executes and no learner or optimizer path is called.

## Remaining owned work

#526 remains open. Native compatible tensor application, whole-capability retention
before activation, per-recipient optimizer reset, rollback, subsequent update and
cold-resume proof need actual B13/C05 custody/source producers and #527 integration.
Embedded clearance is caller-asserted historical metadata; production revocations
need the current source owner. No source release, learner start/resume/stop, graph
mutation or self-merge occurred. All turn-in remains draft for human review.
