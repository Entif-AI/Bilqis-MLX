# B08.1 source-bound categorical gate inputs

`BAMF_0_2.md`'s tensor-ledger gate uses
`mean(type128, role128, schema128)` before projecting to768 channels.
The experimental read helper previously accepted only an anonymous feature128.
`frame_embeddings.motif_gate_features(parameters, projection, frame_handle,
features, *, extents)` now computes that input from the existing B02 source
coordinates and categorical tables. It returns `MotifGateFeatures/v1` data with
the frame/context, feature digest, semantic release and exact member requests.
The record is computed data, not an admission credential.

The constructor reuses existing released categorical gathering, child-frame
binding and overflow rules. Type alternatives within a source member are averaged,
then member type vectors and role vectors are averaged separately, followed by the
three-way type/role/schema mean. Absent bindings do not become zero-padded members.
Empty legal frames use existing NONE type/role rows and their exact schema.
Child frames retain typed ChildFrameRequest coordinates without a ConceptRef or
invented ABI row. Atomic fallback and unsupported non-value/non-child bindings
do not invent categorical meaning and fail at this frame-only boundary.

Known source, release and extent mismatches fail through the existing model
boundary. Selected nonfinite values reject. No projected768 features, graph
channels, feature gates, local slots or identity-bank rows affect this gate input.
The existing projected composer and frame encoder reuse the same raw gathering
helpers, preserving their previous equations and gradients.

Red: the new focused tests failed on the absent constructor import.
Green: nine new CPU tests cover literal0.75 mean, raw-only dependence, exact
table-row gradients, inactive-row isolation, forged ABI/type and feature digest,
nonfinite input, nested-child typing, empty NONE and independent SHA overflow.
Affected source+embedding suite39/39 passes with zero skips before real-A01 intake.

The exact repo-pinned A01 artifact was then located and independently loaded by
the existing source pin checker. With `BILQIS_ATLAS_REAL_ARTIFACT` supplied, the
combined source, embedding and guarded-read suites pass49/49, zero skips. This
executes the existing real source/schema/rights/revocation/cache no-hit adversary;
it does not make the synthetic gate-feature cases real source admission.

Fresh isolated pinned EGM reviewer `b08_gate_feature_egm` read the actual Codex
guide, codebase-details/comprehension personas, reimplementation standard,
architecture gate equation, patch, prior B02 helpers and tests. It returned zero
Blockers/Majors/Nits for this computed-data slice; it did not rerun tests. The
scope-limited disposition preserves public quarantine and all source/retained
generation gates. EGM pin remains b3a35956759bf7f024af2ff061b2e0b44b438e4c.

This advances #460 while the public read remains QUARANTINED_NO_HIT. Wiring the
source-bound input and actual source/retained-parameter bindings into production
reads, then source/hit adversaries and fresh EGM, remain required before #460
turn-in. B08.2/B11/B13 own placement and accepted-generation publication.
No source semantic release, student, own AdamW or teacher is changed.
IPR-0220 OPEN; PM-2026-10-30-005/RC-014/PAT-036 requires continuing after checkpoints.
