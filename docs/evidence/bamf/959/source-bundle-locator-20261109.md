# #959 Atlas source-bundle locator checkpoint — 2026-11-09

Status: **repair checkpoint; Draft PR #961; exact-head full witness and fresh re-review pending.**

## Authority boundary

Reviewed unified base: `7a6c048e9325a877b9b3451c731be3545a11ee69`.
Current-unified flow reconciliation: `b9ce1e73fbc196532642635ba5f08d73d2eca885`.
Initial semantic implementation: `236cfad999e7f6ea24dd90281af639ed161f807b`.
Accepted-ID ordering repair: `bc5c524ec3828b67661b44e8e576338ee7e46068`.

A01 remains source authority. #959 adds only host storage location beneath that authority.
`BILQIS_A01_SOURCE_BUNDLE_ROOT` selects a host-owned root; it grants no semantic,
source, training, C07 or B13 authority. The requested `source_bundle_id` must be a
64-hex content identity. The locator forms only `root/<source_bundle_id>` and then
runs the existing canonical `_verify_bundle` contract. The identity-first A02 entry
reads accepted parent custody and compares the requested content ID with the accepted
Atlas source selection before planning, resource materialization or tensor staging.
The same accepted parent is then carried into staging, and the Registry-mirror path
independently re-verifies the bundle bytes and accepted source identity.

The existing pathful `stage_vocabulary_extension(...)` remains intact for
compatibility. The new additive
`stage_vocabulary_extension_from_source_id(...)` is the production-facing seam
for consumers that already possess accepted content identity and must not persist
or trust a caller host path.

## TDD and behavior proof

Initial tests failed because the content-ID locator and A02 identity-first wrapper
did not exist. After implementation:

```text
Atlas source-bundle locator suite: 4/4 PASS
```

The suite proves relocation under a different approved host root and rejects:
invalid/traversal IDs, missing IDs, a valid bundle stored under the wrong digest,
mutated member bytes, undeclared members, symlinked bundles, relative roots,
symlinked roots and missing root configuration.

Fresh exact-head review then found one ordering Major: a second fully valid source
bundle addressed by its own correct ID could enter full vocabulary staging before
the later Registry-mirror comparison rejected it against accepted A01/A02 custody.
The focused regression
`A02ContentIdentityBoundaryTests.test_wrong_content_id_is_rejected_before_staging_entry`
failed before the repair with `AssertionError: wrong source ID reached staging` and
passes after `bc5c524e`. The repaired entrypoint compares the requested ID to the
accepted `VocabularyPrior.source_selection.source_bundle_id` before invoking the
shared staging helper.

The gated A02 production witness now contains an unmocked byte-verification path.
It creates a real source bundle, binds its content ID into the accepted snapshot,
and stages through `stage_vocabulary_extension_from_source_id`. A second fully
valid bundle placed beneath the same approved root is rejected because its source
ID does not equal the accepted snapshot's source ID. The successful staging
receipt/outbox is also checked to contain no host-root path.

Current ordinary affected ring after the ordering repair:

```text
16 PASS, 4 explicit skips, 15 subtests, 0 failures/errors
```

The skips are optional/gated source and full-topology witnesses. The first detached
content-ID full witness reached the real full staging path but failed on the host's
actual disk-staging budget before the valid path could complete. Its receipt proved
`source_mutated=false`; this was a witness-fixture headroom issue, not a production
authority failure. The fixture now supplies synthetic disposable headroom on the
valid path while deliberately supplying zero headroom to the wrong-ID path, which
must still fail on accepted source identity first. A fresh detached exact-head run
remains required before this checkpoint becomes review-ready.

Repository checks on the committed candidate:

```text
DEVELOPMENT_STRUCTURE_CHECK OK violations=0
GOVERNANCE_INTEGRITY_CHECK OK violations=0
changed-file smell audit: 6 files, 0 findings
BAMF_FLOW_CONTROL_OK (live)
BAMF contract mirrors: 43/43 PASS
git diff --check: PASS
```

Fresh independent exact-head review found the accepted-ID ordering Major described
above. That Major is repaired at `bc5c524e`; fresh independent re-review of the
repaired exact candidate remains required before human merge.

No learner, optimizer step, C07 adoption, PRIVATE_REAL input, force push or
self-merge was performed.
