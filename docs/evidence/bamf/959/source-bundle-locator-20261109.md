# #959 Atlas source-bundle locator checkpoint — 2026-11-09

Status: **READY_FOR_HUMAN_REVIEW; PR #961; exact-head full witness and fresh re-review PASS.**

## Authority boundary

Reviewed unified base: `eaa73be82cf1adac32786d4242868b8e360af5d2`.
Current synchronized semantic candidate: `dbd78411021b70179eb4e831770fa968b59d1ae5`.
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
must still fail on accepted source identity first.

The corrected detached exact-head witness completed successfully from the frozen
`e32b9b305e236488d7a7da4fac1ffa8eae964721` candidate:

```text
label: 959 repaired full content-id A02 staging
status: PASS
command return code: 0
test runtime: 238.071s
source_mutated: false
snapshot/source SHA-256: b70000f7ee192954efc0fea905be3f45571ccbb508850d23651ebc9fb783d7c9
```

The witness ran the real
`A02ProductionStagingTests.test_stages_from_content_id_through_real_source_bundle_verifier`
path with `BILQIS_BAMF_FULL_WITNESS=1` and finished `OK`.

After reviewed unified advanced through #460 B08/engram work, #959 was synchronized
to `eaa73be82cf1adac32786d4242868b8e360af5d2`. The nine-file base delta changes no
#959 locator/A02 source or test file; those files are byte-identical across the sync.
The synchronized focused ring passed 10 tests with 2 expected gated skips and 12
subtests. The exact synchronized frozen witness then completed successfully from
`dbd78411021b70179eb4e831770fa968b59d1ae5`:

```text
label: 959 synchronized full content-id A02 staging
status: PASS
command return code: 0
test runtime: 237.685s
source_mutated: false
snapshot/source SHA-256: 9b435dacd5544f333d95194379736badba8d93a46f770f0ec6e216207b60fc0a
```

Repository checks on the committed candidate:

```text
DEVELOPMENT_STRUCTURE_CHECK OK violations=0
GOVERNANCE_INTEGRITY_CHECK OK violations=0
changed-file smell audit: 6 files, 0 findings
BAMF_FLOW_CONTROL_OK (live)
BAMF contract mirrors: 43/43 PASS
git diff --check: PASS
```

Fresh independent exact-head re-review of `e32b9b305e236488d7a7da4fac1ffa8eae964721`
against reviewed unified `7a6c048e9325a877b9b3451c731be3545a11ee69` returned
**READY — 0 Blockers / 0 Majors / 0 Nits** in Structural, Codebase Details and
Comprehension. The reviewer independently confirmed that the repaired entrypoint
reads accepted parent custody once, rejects a valid-but-wrong source ID before any
resource or tensor staging, reuses the same accepted-parent tuple after the check,
keeps synthetic headroom test-only, and introduces no host-path or portable-authority
leakage.

Fresh differential re-review of synchronized head
`dbd78411021b70179eb4e831770fa968b59d1ae5` against current reviewed unified
`eaa73be82cf1adac32786d4242868b8e360af5d2` also returned
**READY — 0 Blockers / 0 Majors / 0 Nits**. The reviewer confirmed that #460's
B08/engram/formal-grant changes have no callable or data-authority edge into the
source-bundle resolver, accepted-parent reconstruction, accepted-ID comparison,
vocabulary planning, resource estimation, Registry-mirror verification or staging.
The prior accidental #401 Lane A closeout mutation is fully absent from the net
#959 closeout delta.

Hosted synchronized-head checks are also green: `portable`, `portable-core`, and
`semantic-abi-integrity` all PASS. The PR is cleanly mergeable. Human merge remains
a separate authority gate.

No learner, optimizer step, C07 adoption, PRIVATE_REAL input, force push or
self-merge was performed.
