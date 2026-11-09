# #752 partial remediation: production-owned PackedFrame correction gate

Consumed reviewed unified: `6e12e5a077183713241bb9b2b0d0762d8d95fa47`.
Preserved predecessor: `codex/752-artifact-owner-prime-20261102` / `1fa01dce344f720cdd25b742bd3a288c4d0c990a`.

This checkpoint extends the independently actionable production-owner surface of #752 from the already integrated `ATLAS_FEATURE` path to the actual `PACKED_FRAME` path. It does not claim the remaining artifact families are implemented when their production materializers or consumers do not exist.

`PackedFrameArtifactOwner` derives immutable C09 nodes from the real `PackedFrame` objects produced by the A05 frame compiler. Stable artifact identity comes from the packed frame sidecar occurrence identity; materialized content comes from the packed projection digest. Immediate source, release, policy and rights/correction dependencies are derived from the compiled row and packed sidecar rather than accepted as caller-supplied abstract nodes.

`CompiledEncoderInput` retains one owner across repeated validation calls. Before the B03 compiled-frame path reconstructs or unpacks a closure, `_compiled_groups` requires the corresponding real packed-frame node through that owner. A source correction therefore holds the real packed closure before its next consumer read. Source-authenticated equal-output revalidation clears the hold without downstream propagation; changed output remains governed by the existing C09 revalidation engine.

Verification with the pinned A01 bundle `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`:

- focused PackedFrame + source-encoding + C09 dependency/revalidation proof: **18/18 PASS, 0 skips**;
- broader frame compiler, real frame encoder/source path, source-backbone receipts and boundary chaining: **59/59 PASS, 0 skips**;
- `npm run quality:changed`: structure, governance integrity, code-smell, flow-control and flow-control tests all PASS; flow-control tests **15/15**;
- BAMF workstack validation: schema/integrity valid with only pre-existing dependency holds;
- BAMF contract mirror verification: **43/43** exact checked-in issue mirrors pass and the recursive registry is valid;
- error-control and `git diff --check`: no new debt / clean.

Remaining #752 gaps are kept explicit. The retained motif read surface has no non-test production consumer. The exact-cache and operator-composition implementations do not have non-test production materializers, and their current owner modules exceed the repository structural threshold before behavioral edits may be added. Capability-support requalification has no non-test initial materializer carrying actual support-artifact provenance. This branch does not create synthetic publishers, fake consumer chains, or unsupported artifact-to-artifact dependencies to make the six-kind fixture topology look production-complete.

No fresh whole-issue EGM is spent on this partial candidate. No real student, optimizer, teacher, champion, soup, accepted checkpoint, or live neural lineage is mutated.
