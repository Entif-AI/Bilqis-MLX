# Incremental CI verification

Tracking: [#1653](https://github.com/Entif-AI/Bilqis-MLX/issues/1653).

## Reuse contract

The code-smell and historical ABI literal scanners retain source-local findings,
including empty findings, in a content-addressed SQLite ledger. The final
changed-path debt comparison and historical ABI source/expected-value validation
still run. A file edit, checker edit, or Python version change invalidates the
affected finding. The smell scanner uses Git blob identities for historical
source and hashes actual worktree bytes for current source.

Local worktrees share the database in the common Git directory. Set
`BILQIS_VERIFICATION_LEDGER` to choose a different database.
Use `--full` on either scanner or `BILQIS_VERIFICATION_FULL=1` for a cold run.

Hosted quality jobs restore a separate read-only ledger only when the latest
completed main push or scheduled quality workflow succeeded. A newer failed run
forces fresh verification rather than resurrecting older success. The artifact is
bound to its workflow run and attempt; its restored bytes are checked before
use. Fresh writes go to a different database. Only main push/scheduled jobs
publish the result. Missing, expired, corrupted or mismatched evidence falls
back to computation. Weekly scheduled and manually dispatched workflows perform
fresh verification. The portable aggregate still requires every applicable job.

The BAMF readiness, portable custody, architecture and legacy semantic boundary
commands have individual passing receipts. These initially bind the complete
tracked Git tree, exact command, installed dependency metadata, runner image,
tool resolution, editable-install metadata and execution configuration. A clean
checkout matching the hosted event SHA and a known hosted runner are required. The original required-tests command remains the readiness
authority, including its failure on any skipped case. Narrower test-specific
frontiers must be qualified before excluding source inputs.

## Measurements

Local M3 Ultra measured full/warm parity: 3,228 smell inspections in 5.81 s
cold and 0.30 s warm; 1,489 ABI literal inspections in 1.61 s cold and 0.31 s
warm. Both output files matched byte for byte; the combined database was
1.2 MiB. The unchanged required readiness targets completed with 37 passes
and no skips in 61.65 s using a single bounded MLX process.

Workflow restore and publication are optional accelerators; their failure does
not waive or fail a verification result. Main artifacts expire after 30 days.
