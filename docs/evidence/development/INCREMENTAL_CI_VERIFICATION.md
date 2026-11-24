# Incremental CI verification

Tracking: [#1653](https://github.com/Entif-AI/Bilqis-MLX/issues/1653).

## Reuse contract

The code-smell and historical ABI literal scanners retain source-local findings,
including empty findings, in a content-addressed SQLite ledger. The final
changed-path debt comparison and historical ABI source/expected-value validation
still run. A file edit, checker edit, or Python version change invalidates the
affected finding. The smell scanner uses Git blob identities for historical
source and hashes actual worktree bytes for current source.

Local worktrees share a same-account cache in the common Git directory.
Files writable by another account or group are not accepted. Local results
are performance hints within the developer account; hosted CI independently
uses only trusted main artifacts. Set
`BILQIS_VERIFICATION_LEDGER` to choose a different database.
Use `--full` on either scanner or `BILQIS_VERIFICATION_FULL=1` for a cold run.

Hosted quality jobs restore a separate read-only ledger only when the latest
completed main push or scheduled quality workflow succeeded. A newer failed run
forces fresh verification rather than resurrecting older success. The artifact is
bound to its workflow run and attempt; its restored bytes are checked before
use. Fresh writes go to a different database. Only main push/scheduled jobs
publish the result. Missing, expired, corrupted or mismatched evidence falls
back to computation. Weekly scheduled, manually dispatched, and retried workflows perform
fresh verification. The portable aggregate still requires every applicable job.

BAMF readiness has a passing receipt bound to its complete tracked Git tree,
canonical Python test command, actual installed artifact bytes, resolved tools,
runner image, editable-install metadata and execution configuration. The
fingerprint has a 512 MiB byte budget; unavailable or larger environments run
fresh. The required runner uses the same canonical target list from npm and CI,
including its failure on any skipped case. The other portable gates continue
to execute; narrow, independently qualified readiness frontiers can extend
reuse to unrelated source changes without weakening the original suite.

The changed-path gate finds the governance adoption merge using a logarithmic
first-parent search and uses the ordinary merge base when the branch inherited
main's existing governance. Long-lived branches that adopted governance on
their own still exclude pre-adoption debt and imported mainline changes.


## Measurements

Local M3 Ultra measured full/warm parity: 3,228 smell inspections in 5.81 s
cold and 0.30 s warm; 1,489 ABI literal inspections in 1.61 s cold and 0.31 s
warm. Both output files matched byte for byte; the combined database was
1.2 MiB. The unchanged required readiness targets completed with 37 passes
and no skips in 61.65 s using a single bounded MLX process.

The changed-file structure gate previously remained active after 35 s on this
branch; the repaired gate finished in 1.11 s. The changed-file smell gate
finished in 0.50 s with 22 hits and one miss.

Workflow restore and publication are optional accelerators; their failure does
not waive or fail a verification result. Main artifacts expire after 30 days.
