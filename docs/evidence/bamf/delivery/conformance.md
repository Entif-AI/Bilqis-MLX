# BAMF-0.2 delivery conformance projection — 13 November 2026

Issue: #539 (`C15.2`)

- Manifest digest: `fcf4be4f9157e3fb3545e039d3d9b3c48e7bf1fcecc87df656fc0aca89870572`
- Conformance digest: `a9073b1b1666bad164b4e2c285cbe52dfdc063ad82e90abf04c2f0eecce856a3`
- Software delivery: **IN_PROGRESS**
- Student full-atlas mastery: **NOT_CLAIMED**

## Global refusal gates

| Gate | State | Witness | Observation |
| --- | --- | --- | --- |
| GRADE_NEUTRAL_INVARIANCE | CODE_PRESENT | `bilqis_mlx/learning/tests/teaching/test_c03_parent_acceptance.py` | explicit grade-ID permutation witness present; fresh current-head run pending |
| NO_LEGACY_BAV_RUNTIME_NAMESPACE | CODE_PRESENT | `bilqis_mlx/runtime/delivery/tests/test_no_legacy_bav_namespace.py` | runtime namespace refusal witness present; fresh current-head run pending |

## Requirement and negative-fixture matrix

| Claim | Normative obligation | Owner issue | State | Literal fixture / blocker | Observed | Fresh receipt | Reviewer |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| BAMF-REQ-001 | single semantic authority and identity | #345 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A01/A02/A12.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-002 | single semantic authority and identity | #345 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A01/A02/A12.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-003 | reversible frames and 64-bit codec | #349 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A03/A04/A05.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-004 | reversible frames and 64-bit codec | #349 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A03/A04/A05.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-005 | causal prefix | #357 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A05/B04/B06/B08/B11/C13.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-006 | Rosetta meaning/identity | #349 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A03/A10/C10.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-007 | topology and CCGQA | #346 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B01/B04/B11.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-008 | topology and CCGQA | #346 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B01/B04/B11.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-009 | Block AttnRes | #355 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B05.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-010 | motif and active semantics | #356 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B07/B08/A02/B13/A13.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-011 | motif and active semantics | #356 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B07/B08/A02/B13/A13.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-012 | local/dependency refinement | #365 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B06/C04.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-013 | local/dependency refinement | #365 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B06/C04.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-014 | derived cache | #375 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B14.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-015 | Factory teaching | #371 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| BAMF-REQ-016 | rollback | #370 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| BAMF-REQ-017 | replay teacher | #376 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| BAMF-REQ-018 | salience | #379 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:C06.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-019 | correction chronology | #362 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| BAMF-REQ-020 | descendants | #377 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:C09/C10.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-021 | source-family independence | #361 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A10/C05/C12.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-022 | resources/commands | #374 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:C08/C11/C16.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| BAMF-REQ-023 | history | #347 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| BAMF-REQ-024 | actual capability | #378 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| F01 | negative fixture F01 from BAMF-0.2-SPEC-001 | #349 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A03/A11.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F02 | negative fixture F02 from BAMF-0.2-SPEC-001 | #349 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A03/A04.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F03 | negative fixture F03 from BAMF-0.2-SPEC-001 | #349 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A03/A04.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F04 | negative fixture F04 from BAMF-0.2-SPEC-001 | #349 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A03/A04.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F05 | negative fixture F05 from BAMF-0.2-SPEC-001 | #357 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| F06 | negative fixture F06 from BAMF-0.2-SPEC-001 | #361 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A10/C09.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F07 | negative fixture F07 from BAMF-0.2-SPEC-001 | #377 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:C09.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F08 | negative fixture F08 from BAMF-0.2-SPEC-001 | #354 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A13/C06.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F09 | negative fixture F09 from BAMF-0.2-SPEC-001 | #354 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A13.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F10 | negative fixture F10 from BAMF-0.2-SPEC-001 | #361 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A10/C05.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F11 | negative fixture F11 from BAMF-0.2-SPEC-001 | #356 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B07.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F12 | negative fixture F12 from BAMF-0.2-SPEC-001 | #356 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| F13 | negative fixture F13 from BAMF-0.2-SPEC-001 | #375 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B14.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F14 | negative fixture F14 from BAMF-0.2-SPEC-001 | #346 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:B01/B13.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F15 | negative fixture F15 from BAMF-0.2-SPEC-001 | #377 | REQUALIFICATION_REQUIRED | `bilqis_mlx/runtime/tests/correction/test_atlas_stale_replay.py` | BLOCKED | BLOCKED | BLOCKED |
| F16 | negative fixture F16 from BAMF-0.2-SPEC-001 | #357 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |
| F17 | negative fixture F17 from BAMF-0.2-SPEC-001 | #345 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:A01/A12/C07.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F18 | negative fixture F18 from BAMF-0.2-SPEC-001 | #378 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:C05.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F19 | negative fixture F19 from BAMF-0.2-SPEC-001 | #379 | CODE_PRESENT | `docs/tasks/bamf-0.2/workstack.json:C06/C09.tests` | NOT_EXECUTED | NOT_EXECUTED | PENDING |
| F20 | negative fixture F20 from BAMF-0.2-SPEC-001 | #372 | BLOCKED | `blocked:C13/C14 accepted integrated witness` | BLOCKED | BLOCKED | BLOCKED |

Every machine row additionally binds the SPEC revision, direct-owner commit field, contract path, runner/environment, and source/contract/issue digests. Pending commit or execution fields are intentionally visible and prevent `EXECUTED_PASS` admission.

`EXECUTED_FAIL` and global refusal gates have precedence over otherwise-green evidence. Source/contract/issue identity drift forces `REQUALIFICATION_REQUIRED`. `READY_FOR_OWNER_MERGE` or `DELIVERED` is structurally impossible until all 44 rows and both refusal gates are `EXECUTED_PASS`.

The current environment lacks `rdflib`, so the existing full grade-neutral behavioral witnesses cannot be rerun here and remain `CODE_PRESENT`, not `EXECUTED_PASS`. The dependency-light no-legacy-runtime-namespace witness is runnable locally. Protected `PRIVATE_REAL` evidence remains excluded from public artifacts; see `c15-2-evidence-boundary.json`.
