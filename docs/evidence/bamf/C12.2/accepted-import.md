# C12 accepted package import through B12 and B13

The candidate branch `codex/746-c12-import-commit-20261102` consumes unified
`48315ee7bae3caa7d5ac279128c79217b9178d16`. It also contains the reviewed C05
owner-run screen from #744 (`b7c792a1`) and the A12 export-clearance owner from #745,
which is already present in unified. IPR-0220 remains governing. All execution in
this receipt uses disposable fixtures. No real learner, optimizer, teacher,
champion, soup or checkpoint lineage is changed.

## Authority path

An exact-compatible package first becomes a sealed `DisposableDeltaCandidate` from
the current B13 pointer. C05 then runs its required evaluation cohorts through
`evaluate_retention_candidate(...)`; callers cannot pass retained evidence into
`screen_delta_candidate(...)` or construct `ScreenedDeltaCandidate` directly.

Adoption requires a signed A12 `ExportClearanceReceipt`. C09's host-provisioned
`SourceAuthorityRegistry` verifies the detached signature. A12 then binds the
receipt to the selected release, live source frontier and exact artifact set. The
package's embedded `SourceRights` must equal that signed projection. A forged
signature or caller-chosen clearance digest rejects before receiver mutation.

For an eligible screen, C12 re-reads the current B13 pointer and complete receiver.
The screened parent manifest must still be current. B12 then creates a sealed
`PackageImportTransaction`; imported bytes may differ from the parent only inside
the package's declared slices. B12 resets changed-slice optimizer moments, resets
the owner-supported update count for affected rows or tensors, resets touched
identity-row ages, preserves untouched state and policy mode, and resets the
accepted-fast counter. The import keeps the optimizer-step clock unchanged because
it is not a training visit.

B13 accepts `PACKAGE_IMPORT` only through a sealed
`PackageImportBundleCandidate`. An ordinary public `BamfBundleCandidate` with the
same transition fields is rejected before publication writes. The published
evaluation contract and outbox bind the parent manifest, package digest, reset
policy digest, C05 decision/evidence/policy digests and A12 clearance digest. The
recipient teacher state is unchanged. Pointer publication remains atomic and
retryable under the existing B13 custody owner.

## Executed proof

- Accepted import resets only the declared weight, moment, count and age state and
  cold loads the exact package-import lineage.
- A following disposable B12 optimizer step starts from reset update counts and
  retains the cold-loaded package and reset lineage.
- B12 rejects any imported tensor change outside the declared package slices.
- Rejected C05 screening leaves the current pointer unchanged.
- Stale screened parent drift rejects before a new generation can become current.
- Injected pointer failure leaves the parent current; retry publishes the same
  immutable candidate.
- Unsigned A12 clearance and mismatched embedded rights both reject.
- A caller-created `PACKAGE_IMPORT` bundle cannot self-authorize publication.

Focused adoption proof: **6/6 PASS**, zero skips. Combined C12 package, C05 screen,
A12 clearance, C09 authority/revalidation and B13 custody/publication proof:
**114/114 PASS**, zero skips. The existing B12 candidate suite passes **9/9**
through its public package path. Changed-scope structure, governance, Factory
architecture, docs, error-control, code-smell, flow-control and diff checks are run
again after this evidence is frozen.

## Remaining boundary

The repository still has no non-test caller of `export_capability`, `receive_package`,
`apply_plastic_delta`, `screen_delta_candidate` or `adopt_screened_delta`. The
package subsystem therefore has a coherent owner path but no existing production
operator/importer that can invoke the accepted-import sequence. This branch does
not invent one. #746/#718/#526 remain open until that production caller seam exists.

Final exact-head EGM belongs to the complete #718/#526 candidate only after that
caller is real, the local gates are green and the branch has remote readback. #708,
#709 and #754 remain separate B13 mitigations. This candidate supplies their missing
accepted package-import custody/publication owner, but it does not claim their
feature-receipt, cold-continuation or cache-transition requirements complete.
