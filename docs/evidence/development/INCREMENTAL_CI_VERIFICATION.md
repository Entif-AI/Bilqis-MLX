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

BAMF readiness has a passing receipt bound to a validated Git source view,
canonical Python test command, actual installed artifact bytes, resolved tools,
runner image, editable-install metadata and execution configuration. The
fingerprint has a 512 MiB byte budget; unavailable or larger environments run
fresh. The required runner uses the same canonical target list from npm and CI,
including its failure on any skipped case.

For normal hosted readiness, Git archives a source view without
`apps/mission-control/` or `docs/evidence/development/`. The archive contains
no Git history and is verified against the selected tree entries, including file
modes and symlink targets. Dependencies install against that view; the required
suite executes in it with Git repository discovery disabled. Frontend and
engineering-evidence edits therefore cannot change this predicate's visible
source. An invalid archive or a failed projected check falls back to the
original full source; no projected pass is minted from a fallback. Full mode,
scheduled verification and retries use the complete checkout. Changes to any
included source invalidate the readiness receipt. The other portable gates
continue to execute.

The changed-path gate finds the governance adoption merge using a logarithmic
first-parent search and uses the ordinary merge base when the branch inherited
main's existing governance. Long-lived branches that adopted governance on
their own still exclude pre-adoption debt and imported mainline changes.


## Measurements

Local M3 Ultra measured full/warm parity: 3,228 smell inspections in 5.81 s
cold and 0.30 s warm; 1,489 ABI literal inspections in 1.61 s cold and 0.31 s
warm. Both output files matched byte for byte; the combined database was
1.2 MiB. The unchanged required readiness targets completed with 37 passes
and no skips in 61.65 s using a single bounded MLX process. The canonical
runner passed all 37 tests on full source in 64.23 s and the independently
archived projected source passed all 37 in 63.23 s, with no skips in either.

The changed-file structure gate previously remained active after 35 s on this
branch; the repaired gate finished in 1.11 s. The changed-file smell gate
finished in 0.50 s with 22 hits and one miss.

Workflow restore and publication are optional accelerators; their failure does
not waive or fail a verification result. Main artifacts expire after 30 days.

## Local pre-push parity

The tracked Husky pre-push hook executes every applicable repository-owned
pull-request CI predicate before Git sends source updates. Hosted workflows
and the hook use the same command groups in `scripts/quality/ci_checks.sh`.
A parity regression checks the workflow inventory against the local gate and
exercises both branch classifications and all semantic shard selections.

The hook reads the actual Git push ref records, requires the checked-out commit
and a clean source tree, fetches the integration base, and blocks stale
candidates. An open GitHub PR supplies its base and title; new branches default
to main, or set `BILQIS_CI_BASE_BRANCH` for another integration target.
Missing pinned CI dependencies block execution rather than allowing dependency
skips. Install the semantic requirements, NumPy 2.4.4, MLX 0.31.1 and the
project dependencies in the selected local Python environment. A semantic
DIFF or FULL plan additionally requires the extraction and Falkor requirements.

The pre-push runner preserves the previous local governance checks and applies
a single-worker 12 GiB MLX limit with caching disabled for test processes.
Failure, timeout, or a changed candidate blocks the push. Hosted CI retains
independent runner-specific proof, CodeQL and GitHub-only orchestration.
Scheduled, manual and publication-only workflows remain hosted.

`npm run prepare` installs Husky and points Git to the tracked `.husky` directory.
This prevents linked worktrees from silently losing hooks when their generated
Husky shim directory is absent. Do not bypass the verification hook.
