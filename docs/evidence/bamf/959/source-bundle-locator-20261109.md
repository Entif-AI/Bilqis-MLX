# #959 Atlas source-bundle locator checkpoint — 2026-11-09

Status: **implementation checkpoint; Draft PR #961; exact-head full witness and fresh EGM pending.**

## Authority boundary

Reviewed unified base: `8b03be4881d4450f4f6cba94cfda9b21a2dd2711`.
Lane/control activation head: `1a50cfec0323dd6a5e46938e27f53a9aadc34e46`.
Semantic implementation: `236cfad999e7f6ea24dd90281af639ed161f807b`.
Current exact branch head: `4ac234c80f9dbae2c1b40cdff4d8aba4aeea74af`.

A01 remains source authority. #959 adds only host storage location beneath that authority.
`BILQIS_A01_SOURCE_BUNDLE_ROOT` selects a host-owned root; it grants no semantic,
source, training, C07 or B13 authority. The requested `source_bundle_id` must be a
64-hex content identity. The locator forms only `root/<source_bundle_id>` and then
runs the existing canonical `_verify_bundle` contract. A02's registry-mirror path
re-verifies the bundle and compares the computed ID with the source ID in the
accepted Atlas snapshot before staging.

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

The gated A02 production witness now contains an unmocked byte-verification path.
It creates a real source bundle, binds its content ID into the accepted snapshot,
and stages through `stage_vocabulary_extension_from_source_id`. A second fully
valid bundle placed beneath the same approved root is rejected because its source
ID does not equal the accepted snapshot's source ID. The successful staging
receipt/outbox is also checked to contain no host-root path.

Current ordinary affected ring:

```text
18 total: 15 PASS, 3 explicit skips, 0 failures/errors
```

The skips are the optional real A01 corpus witness and the two explicitly gated
full-topology A02 production-staging witnesses. The exact-head full witness is
running through the repository snapshotting detached runner and must be reconciled
from its terminal receipt before this checkpoint becomes review-ready.

Repository checks on the committed candidate:

```text
DEVELOPMENT_STRUCTURE_CHECK OK violations=0
GOVERNANCE_INTEGRITY_CHECK OK violations=0
changed-file smell audit: 6 files, 0 findings
BAMF_FLOW_CONTROL_OK (live)
BAMF contract mirrors: 43/43 PASS
git diff --check: PASS
```

Fresh independent EGM is pending because the Chat On Steroids worker transport is
temporarily unavailable during conversation transfer. Per project policy this is
recorded as `EGM_PENDING`; a same-context self-review is not substituted.

No learner, optimizer step, C07 adoption, PRIVATE_REAL input, force push or
self-merge was performed.
