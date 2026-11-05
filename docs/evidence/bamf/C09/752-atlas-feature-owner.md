# #752 partial remediation: production-owned Atlas feature correction gate

Consumed reviewed unified: `48315ee7bae3caa7d5ac279128c79217b9178d16`.

This candidate implements the independently actionable `ATLAS_FEATURE` portion
of #752 without claiming the full six-artifact remediation complete.

`bilqis_mlx.runtime.atlas_artifact_owner.AtlasFeatureArtifactOwner` derives its
`ArtifactNode` and immediate dependencies from an actual `AtlasFeatures` object
and its `FeatureSchema`; callers cannot register arbitrary nodes or supply impact,
exigency, digest, eligibility, or dependency edges. The owner retains the C09
dependency index and active hold queue across reads. It accepts only externally
qualified correction/revalidation evidence through the existing C09 authority
registry.

The real source encoder now requires that stateful owner. `source_atom_vectors`
still independently reloads the pinned A01 artifact and rebuilds the expected
feature manifest before consulting the correction gate. A caller-selected feature
object therefore cannot self-ratify by constructing a matching owner. The B11
source-backbone entrypoints also require and retain the same owner rather than
silently creating a fresh empty correction queue on each read.

With the registered A01 artifact mounted at bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`, the
real source-consumer regression proves that a source correction holds the actual
feature artifact before the next encode; equal materialized output and eligibility
clear the hold without propagation; and a changed materialized digest leaves the
old feature object unusable.

Verification on the current candidate:

- real pinned A01 source encoding and correction gate: **7/7 PASS, 0 skips**;
- C09 dependency/revalidation plus runtime grouped-module identity: **14/14 PASS**;
- real B11 source backbone and receipt callers: **20/20 PASS**.

The full #752 issue remains open. `PACKED_FRAME` integration reaches the still
oversized `semantics/frame_compiler.py` owner and must consume the canonical #347
structural repair through reviewed unified before that path is touched. Motif read,
exact-cache creation, operator-composition materialization, and initial
capability-support materialization still lack the required non-test production
wiring identified in the current owner audit. This branch does not invent those
producers or synthetic consumers and does not claim a fresh full-issue EGM.

No actual student, optimizer, teacher, champion, soup, accepted checkpoint, or
live neural lineage was mutated.
