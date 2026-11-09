# C02.5 / #905 fresh turn-in EGM

## Reviewed candidate

- issue: #905
- branch: `codex/905-c02-5-visit-provenance-20261107`
- reviewed unified: `2c26d4aca90f275e1c255aa6a197ab63e0528480`
- reviewed qualification head: `d76063fd2a79cfd0d15aba8f1eeb87a15828bce1`
- bounded review-repair head: `e78e44a6bafa6c078f039b902254e48bfe01ba4b`
- pinned EGM checkout: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`

The review used the live #905 contract, its parked/resume authority, exact candidate
diff/source/tests, and the accepted #904/#376 interfaces now present in reviewed
unified. Unrelated #930 history, historical #904/#376 review findings, Session
Minutes, and general repository debt were excluded from acceptance authority.

## Fresh review round 1

**FAIL — 0 Blockers / 1 Major / 0 Nits.**

The implementation already rejected visit-capability mismatch in production at the
C02 adapter/provenance/Factory boundaries, but the live #905 Proof clause required a
focused negative witness and the exact candidate did not contain one. No production
defect or authority-boundary defect was found.

The same review independently confirmed:

- `BamfVisitProvenance` parses the exact C03 record, validates its canonical
  `visit_id`, and cannot be caller-constructed;
- B13 run identity, integer `run_seed`, generation/accepted-manifest identity,
  teacher/student/selection fields, policy key and capability are transported as
  non-authorizing provenance;
- `run_seed`, `visit_id`, `optimizer_step_seed`, and source `episode_id`
  remain distinct meanings;
- every `BamfDeliveryProvenance` carries the visit envelope and the issued batch
  authority digest covers the complete portable provenance record;
- current C09 `immediate_dependencies` custody remains intact;
- accepted #904/#376 owner interfaces are consumed through reviewed unified, with
  no sibling-merge shortcut and no minted B11/B06/C03/B13 credential;
- the candidate-step extraction preserves execution order and authority;
- the Grade-A fixture repair to balanced `each=2` is legal; and
- the error manual/catalog delta is path-only.

The current Factory candidate-execution generation-zero fixture remains outside
C02.5 acceptance: exact reviewed unified is independently red there with
`BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED` before #905 provenance participates.

## Bounded review repair

Repair head `e78e44a6bafa6c078f039b902254e48bfe01ba4b` changes two test files only:

1. `test_visit_provenance_transport.py` now constructs an `A.IDENTITY` visit,
   supplies `B.IDBOOLOPS` as delivery capability, and asserts
   `VISIT_PROVENANCE_CAPABILITY_MISMATCH`.
2. `test_atlas_training_visibility.py` replaces lambda objects used only as
   `subTest(...)` display values with stable string labels. The same lambdas still
   execute and all assertions remain unchanged. This closes an xdist/execnet
   serialization failure exposed by the repository differential runner.

No production source changed.

Passing repair evidence:

- targeted repaired-file xdist ring: **21 passed / 4 subtests**;
- repository differential leaf gate after repair: **6 passed / 4 subtests**;
- aggregate quality gate: governance, Factory architecture, docs, error-control
  `new debt 0`, code-smell `0 new changed-file findings`, legacy-trainer
  authority + tests, and BAMF flow-control + tests all PASS.

## Targeted re-audit

**PASS — 0 Blockers / 0 Majors / 0 Nits.**

Disposition: **READY_FOR_HUMAN_REVIEW**, subject only to the repository's normal
pre-merge/hosted-CI turn-in gates.

The same independent reviewer inspected only the exact
`d76063fd2a79cfd0d15aba8f1eeb87a15828bce1..e78e44a6bafa6c078f039b902254e48bfe01ba4b`
repair delta. It confirmed that the sole Major is closed, the xdist label repair is
test-harness-only, no production source changed, and no new relevant Blocker, Major,
or Nit was introduced.

No live learner, durable optimizer update, source promotion, accepted production
generation, sibling merge, or self-merge was performed. Human review and merge
remain separate authority gates.
