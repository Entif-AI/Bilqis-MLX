# B09.1b detached cadence policy

Issue #464 remains open for retained-generation integration. Consumed unified
`da0431bee37c0e4f766f05cc94ceb6b23ac7d054`; Lane B predecessor
`7080d6445404411c7d64ee26680d73cff06ce11f` includes reviewed #463 static
eligibility and row-age code from `8ba5b8ae3c24221ab3e317a805ffcce62baa7b37`.

`PlasticityPolicy` defaults to FOUNDATION and serializes mode, accepted FAST
counter, row ages, policy version and state schema. Exact schemas are
`bilqis.mlx.plasticity-policy/v1` and
`bilqis.mlx.plasticity-policy-state/v1`. Its strict reader rejects missing,
extra, incompatible and malformed fields; it never infers clocks from grades.

`next_update_mode` returns FULL in FOUNDATION. In ADAPTIVE it returns FULL
when the existing teacher requests it or accepted_fast_since_full >= 8;
otherwise FAST. Acceptance advances the FAST counter once or resets it on
FULL. Rejection returns the identical parent. Existing row-age arithmetic
advances each supplied participating row once per retained candidate, capped
at establishment age; unused rows remain unchanged. Teacher targets, learning
rate and pedagogy are outside this policy.

The record and update are detached proposals. The existing checkpoint owner
must bind and persist them with actual retained candidate evidence. Constructing
or loading ADAPTIVE does not authorize a running student's transition.
Promotion-receipt transitions belong to #466; actual mask/source/B05/B08/B11,
AdamW and B13/C publication integration remain open. No new production caller,
live student update, checkpoint write or source admission was introduced.

Red: four new cadence tests failed on absent APIs while six existing tests
passed. Green: 11/11 focused policy/adapter tests pass; combined with the optimizer
seam, 21/21 pass with zero skips.
Tests cover eight accepted FAST candidates across JSON cold reads, rejected
FAST/FULL, teacher-early FULL, FOUNDATION, exact age changes, malformed records
and the contract's explicit overdue >=8 behavior.

Pinned independent EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`: scoped PASS,
no Blocker/Major, independently reproduced initial 10/10. Reviewer proposed
rejecting counter9, then retracted after checking the authoritative >=8 clause:
9 schedules FULL, rejection preserves it, acceptance resets0. An explicit
regression now preserves that behavior. Full #464/B09 acceptance is not claimed.

Operator audit adds no debt; three inherited numeric-guard sites in the
existing adapter/row-age helpers remain unchanged. Exact-head hosted checks on
predecessor7080d64 still fail the inherited frame_adapters.py import boundaries
at12/13/654; no guard/baseline was weakened. IPR-0220 and prior
PM-2026-10-29-001/002/003/004/006 controls remain. Actual learning/retention
unmeasured; human owns unified integration and durable training initiation.
