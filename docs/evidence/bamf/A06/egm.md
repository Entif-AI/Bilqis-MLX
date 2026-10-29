# A06.1 independent EGM | AtlasFeatures/v2

- Leaf: #411; parent A06 #352
- Initial candidate: `a02a64dde1c501f9e06544bf75f80852a6a83b9d`
- Reviewed unified trunk: `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
- First repairs: `335f792`, `9265f00`
- Full-issue final implementation:
  `b3bea14fe241f5f11c68d11a41af3d938aebd8ae`
- Independent reviewer: Goldfish, read-only immutable-source checks
- Disposition: **EGM PASS**, zero remaining Blockers/Majors

The first reviewer identified root-side sense count,
caller-invented role/schema categories, and foreign
predecessor lineage. The repair counts only admitted
source-attested root/sense links, binds every requested
FrameSchema to its exact A03 released source adapter
and pinned graph (including the separate C numeric graph),
and requires the A01 predecessor atlas bundle ID to
match the successor's prior ABI digest.

The separate full-issue review on #411
(comment 6486698167) identified four more gaps:
reserved UNKNOWN row 0 wrongly emitted overflow f128;
no forced signed-hash collision or complete two-overflow
goldens; network-negative did not include lookup; and
PR Development closing-link/receipt metadata was missing.
All were repaired. The signed-collision test uses two
hardcoded SHA256 signatures with opposite signs at
Graph64 channel 47. The overflow test independently
compares all 128 components for each of the two
beyond-capacity type IDs against literal SHA byte
vectors. The socket trap covers both manifest build
and `features_for`.

Independent final readback at `b3bea14` executed
**12 passed, 0 failed, 0 skipped** from an immutable
archive and returned **PASS**. PR #546's Development
section contains `Closes #411`; native GitHub
`closingIssuesReferences` readback returned #411
and #432. PR receipt comment 6487365093 records
the candidate and evidence.

A06.2 and A06 parent integration remain open.
This review does not authorize live training,
source promotion, or merging the draft PR.

## A06.2 independent EGM | local export and reference vectors

Initial immutable candidate `4a5800e0f37ae1a40107d60772aa18d8c8b2a0e6`
passed 20/20 focused owner tests, but Goldfish found
two Majors: factor-map row gaps/early overflow and
caller-optional successor lineage at the persisted
boundary; and a raw OSError escaping during failed
temporary-directory cleanup.

Repair `a4be8062988e84b3f0a053dbc5067e44471ff89d`
enforces dense learned rows, canonical initial UTF-8
allocation, mandatory predecessor proof for successor
publish/load, stable prior assignments and exact new
row allocation. Cleanup failures now raise a catalogued
ErrorBus error. Independent targeted re-review executed
**23 passed, 0 failed, 0 skipped** from immutable source,
reproduced the original adversaries, checked role/schema
maps and a valid three-generation successor chain, and
returned **A06.2 EGM PASS, zero remaining Blockers/Majors**.

PR #546 native Development closing references include
#411, #412 and #432. A06 parent integration remains
open; no merge or live training occurred.
