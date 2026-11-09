# C12.3 | Private-safe export and local exchange closeout

Issue: #527
Lane: C
Working branch: `codex/bamf02-c-runtime`
Reviewed unified consumed before issue-owned edits:
`6a770f10074df6f4f8889d439f783ad42f5efe63`
Exact semantic implementation/proof head:
`3aa81f18dba338b79eff935de96e9d94eda75fae`
Latest reviewed unified consumed before turn-in:
`039fbcab9df0e3aac6efb622bfaa059fa7e2bf5a`
Current integration head after the conflict-free reviewed-unified merge:
`64351d421edcd9594f1f393322fa15936602fc8c`

## Dependency and ownership closure

- Direct predecessor #526 is closed and EGM-Passed. Its accepted candidate
  `b60218e821adffff10971d524914b4d03f70786c` merged through PR #941 as
  `e206ec0e957e24823f3136c0f3bffe1fc950013e` and is an ancestor of the
  consumed reviewed-unified base.
- A12 #364, C05 #378 and C09 #377 are closed.
- B13 #372 remains an integration parent, but the C12.3-required package
  transition, atomic publication and cold-read surfaces are present on reviewed
  unified. Its implementing checkpoint/cold-resume children #478-#481 are closed.
- #527 composes existing owners rather than duplicating them: A12/C09 own current
  source-export authority; B12 owns changed-slice optimizer reset; C05 owns the
  complete-solver retention decision; B13 owns accepted PACKAGE_IMPORT publication;
  C03 owns teacher-lineage bootstrap and changed-student rebinding.

## Design review and amendments

The checked-in C12.3 child packet predated the split C12.1/C12.2/#718 implementation.
Fresh pre-implementation EGM against exact base `6a770f10` found material design gaps:
stale edit/test paths, no authoritative meaning for PUBLIC_DERIVED, unspecified v1
wire compatibility, incomplete B12/C03 composition, no mature-teacher rebind,
pre-bootstrap C03 stranding after a package import, and incomplete next-step/cold-
resume witness assignment.

The immutable issue contract was preserved and amended append-only on #527:

- comment `6753769152`: current edit surface; A12/C09/B12/C05/B13/C03 composition;
  portable/local boundary; unchanged v1 wire; mature C03 rebind; transitive
  next-step provenance; acceptance assignment;
- comment `6753797209`: deterministic PackageKind classification and the sealed,
  non-wire PublicExportGrant/current-process sender-token mechanism;
- comment `6753812392`: deterministic classification provenance and the narrow
  authenticated pre-bootstrap PACKAGE_IMPORT C03 exception.

Targeted re-audit of the complete amended design by readiness, codebase-fit and
comprehension scopes ended **0 Blockers / 0 Majors** in all three scopes before the
corrected implementation was frozen.

The provisional implementation commit `5d2f5425` preceded that repaired design
gate and is not the qualification head. The corrected semantic head above
supersedes it without rewriting branch history.

## Owned implementation

### Source-side public export authority

C12.3 does not add a caller-settable classification field to `PackageArtifact` and
does not add a new EvidenceRights regime.

`authorize_public_export(...)` requires the current source-owner-signed A12
`ExportClearanceReceipt`, exact Atlas selection, current `SourceFrontier` and current
C09 `SourceAuthorityRegistry`. The signed export digest set must equal the complete
snapshot artifact digest set.

After A12 authorization, C12 deterministically projects typed package roles:

- `FIXTURE`, `COUNTEREXAMPLE` -> `PUBLIC_FIXTURE`;
- `PROCEDURE`, `EXACT_TRANSFORM`, `ADAPTER_DELTA`, `WEIGHT_DELTA`,
  `BEHAVIORAL_DIFF` -> `PUBLIC_DERIVED`.

The label is descriptive; signed A12 exact-digest membership is the authority.
Upstream `PRIVATE_REAL` cannot enter that set and `UNCLASSIFIED` has no positive
export authorization.

The resulting `PublicExportGrant` is sealed by a module-private issuer and binds the
exact digest/classification tuple plus the portable `SourceRights` projection.
`export_capability(...)` requires that exact issued grant and marks only the returned
in-memory `CognitivePackage` with a non-dataclass sender-publication token.

`publish_package(...)` requires that token. Directly constructed and cold-decoded
packages cannot use the sender-publication API. Receiver staging uses the private
canonical-byte writer after addressed read/hash/canonical/compatibility inspection;
it does not mint re-export authority.

No portable schema changed. The outer package remains
`bilqis.c12.cognitive-package/v1`, the delta artifact remains
`bilqis.c12.plastic-delta/v1`, and the historical golden package still decodes to the
literal SHA-256
`98527cd13e7a10c65d4697277e681137f34ff55dbdf479bf842eb7f87c6372e4`.
The grant, classification projection, A12 verification context and sender token are
non-wire.

### Receiver-local adoption and teacher custody

The accepted path remains:

`receive_and_adopt_delta_package`
-> receiver-derived current B13 binding
-> A12/C09 authority check
-> compatible disposable delta
-> B12 `prepare_package_import`
-> C05 complete-solver screen
-> B13 `PACKAGE_IMPORT` publication.

For a mature recipient C03 lineage, accepted package import now reuses C03's existing
`bind_next_teacher_epoch(...)` + `advance_teacher_lineage(...)`. Recipient
teacher/strategy knowledge, adaptation authority, replay ancestry, next seed, cursor
and last-visit history are preserved while the changed student receives fresh
checkpoint-local grade/causal/retirement evidence. Generation provenance is updated
to the rebound teacher identity/epoch. Sender teacher state is never imported.

For a recipient without C03 lineage, package import preserves the pre-bootstrap
teacher sidecar. `_c03_projection(...)` may subsequently bootstrap on generation > 0
only when the current transition is a valid B13 `PACKAGE_IMPORT`, optimizer step is
still zero, teacher sidecar identity/epoch matches generation provenance, and the
ordinary authoritative legacy receipt/adaptation/prior-region inputs are supplied.
Any intervening native optimizer step, non-package transition or missing authority
remains fail-closed.

The next native optimizer step proves package/reset ancestry transitively through
`StepExecutionProvenance.parent_manifest_sha256 == accepted PACKAGE_IMPORT manifest`;
no duplicate package/reset fields were added to candidate-step wire.

## Behavioral proof

All proving runs used disposable fixture state. No live student or human-owned
optimizer was started or resumed.

- Focused export/wire/exchange/delta/receiver seam: **47/47 PASS**.
- Complete `bilqis_mlx/runtime/cognitive_package/tests` discovery: **68/68 PASS**.
- C12.3 + C03 targeted behavior pair: **5/5 PASS**. This includes:
  - two same-weight recipients with distinct local AdamW histories resetting only
    the changed slice/row and retaining distinct untouched state;
  - a mature recipient undergoing a real accepted native C03 generation, then real
    package screen/publish, then cold load with recipient-owned teacher epoch
    rebound to the imported retained student;
  - pre-bootstrap generation 0 -> authenticated PACKAGE_IMPORT generation 1 -> cold
    load -> ordinary C03 bootstrap/selection without stranding;
  - imported manifest -> next native optimizer step -> later rejected candidate ->
    exact cold-resume of the accepted local state.
- Cross-owner C03/B13/C05/A12/source-rights ring: **33/33 PASS**.
- Existing exchange coverage remains green for exact two-node bytes, wrong
  base/topology/release/motif rejection, behavioral diff/counterexamples, ancestry,
  crash-before-pointer retry and sender-optimizer non-adoption.

The complete **68/68** package suite passed again after merging latest reviewed
unified `039fbcab`, whose B09.3 transition-authority work changed
plasticity/package-import retention dependencies. A targeted post-merge C03/B09/
vocabulary ring also passed **10/10**. The merge was conflict-free and introduced
no C12.3 code edits. The earlier **33/33** cross-owner C03/B13/C05/A12/source-rights
ring remains the semantic-head proof recorded above.

Legacy-trainer authority source for the C03 fixture adaptation remains the canonical
run at
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`.

## Repository integration proof

Against latest reviewed unified `039fbcab`:

- `quality:structure`: PASS, zero development-structure violations;
- governance integrity: PASS, zero violations;
- changed-file smell audit: 19 files scanned, zero new findings;
- BAMF flow-control validator: PASS;
- flow-control tests: **15/15 PASS**;
- legacy-trainer checker unit tests: **7/7 PASS**;
- `verify_bamf_0_2_contracts.py`: PASS, 43/43 exact mirrors and 216 indexed
  owner/child identities;
- latest BAMF flow-control validator after `039fbcab`: PASS;
- latest `verify_bamf_0_2_contracts.py` after `039fbcab`: PASS with the same
  43/43 mirrors and 216 indexed owner/child identities;
- `git diff --check`: PASS.

The aggregate `quality:changed` chain stops only on
`LEGACY_TRAINER_SOURCE_OMITTED docs/evidence/bamf/C07.1b/atomic-adoption-20261109.md`.
After C12.3's own receipt was corrected, the current tree reports exactly that one
violation. A detached worktree at the exact consumed reviewed-unified base
`066c08028f1f8b6c8f7ccc36c285df0ea3c6cfba` reproduces the same single violation,
so it is inherited base debt and #527 does not edit that C07.1b receipt.

## Drift and turn-in

Post-implementation design-to-code drift is evaluated against exact semantic head
`3aa81f18dba338b79eff935de96e9d94eda75fae` and recorded in `drift.md`.
The readiness, codebase-fit and comprehension drift scopes all returned
**0 Blockers / 0 Majors**; the prime differential audit found no harmful drift.
That semantic head was pushed and read back exactly before the later
reviewed-unified merge. Draft human-review PR #946 targets
`codex/bamf-unified-base-20261028`. Final evidence/flow state is pushed and read
back before the PR is marked ready.

## Safety boundary

No `PRIVATE_REAL` payload entered the repository, CI, issue text or package wire.
No live student or human-owned optimizer was started or resumed. No `main` or sibling
lane was merged directly. The only private/local authority material referenced in
this receipt is already repository-governed test authority or the canonical local
legacy-trainer source path required by the repository checker.
