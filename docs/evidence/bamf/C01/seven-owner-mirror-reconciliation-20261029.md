# C01 live owner mirror reconciliation | 2026-10-29

The live C01 workstack `--live` validation identified seven owner-body divergences after GitHub issue amendments. The repository mirror and workstack metadata still carried earlier owner hashes. Live GitHub issue bodies remain authoritative for these existing workstreams.

The reusable dry-run-first reconciler (`scripts/bamf/reconcile_owner_mirrors.py`) verifies that every original nonblank line survives in the live body in its original order, rejects forged or non-additive changes, and preserves original mirrors and machine metadata in the private durable Work Stack. It synchronized repository mirrors and each descendant's `source_parent_sha256` without rewriting child issue bodies.

| Owner | GitHub issue | Live amendment retained |
| --- | --- | --- |
| A03 | #349 | A03.4 #578 source-schema witness child |
| A05 | #357 | A05.4 #575 nested partial-forest child |
| B02 | #359 | B02.4 #576 child-frame constituent child |
| B05 | #355 | B05.4 #577 depth-provenance child |
| C08 | #374 | Distributed resource mode, C08.4 #558 |
| C13 | #385 | Hardware-scaling calibration receipt metrics |
| C14 | #386 | Heterogeneous swarm contribution, C14.3 #559 |

Four live owner bodies (A03, A05, B02, B05) had trailing blank lines. Their GitHub bodies were normalized by removing **only** trailing empty lines, preserving all substantive text. Preimages were preserved privately and immediate readbacks matched exactly. The final mirror, manifest and descendant hashes were reconciled in a second idempotent pass.

- Focused workstack and reconciler tests: **32 passed, 0 failed, 0 skipped**.
- Changed-path structural check: zero violations.
- At this checkpoint, the only remaining local and `--live` workstack issue is A09.1's known `MIRROR_HASH_MISMATCH`, already repaired in separate draft PR #605. This batch does not claim all-green validation until that dependency is consumed and retested.
- New owner child links are preserved, but new children #575 through #559 are not silently added to the original 157-child registry. Recursive registry expansion is a separate governed change.

No neural training, source admission, learner promotion, parent closure or self-merge occurred. Original mirror preimages remain preserved outside the public repository.
