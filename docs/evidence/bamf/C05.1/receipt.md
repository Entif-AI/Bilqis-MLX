# C05.1 | Complete-solver paired capability evidence

Issue #501; parent #378; local predecessors C03/C04 implemented provisionally.
Status: IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION.
Authority: IPR-0220. Lane C codex/bamf02-c-runtime; draft PR #550.
Consumed unified 6b5460032fc0b19115843cce95fe8be9582af141,
already contained at implementation baseline 8e88d1474be67d94f563a378ce1f74919fbcb50c.

## Owned implementation and interfaces

runtime/capability_retention.py holds the cohesive evaluator/adapter boundary.
The prescribed exam_execution.evaluate_capabilities and
candidate_evidence.retain_candidate APIs re-export it. The module contains no
optimizer or checkpoint engine. CompleteSolver invokes actual solve_task with a
per-task source context, preserving one opaque parent/candidate generation digest
while binding each actual A07 OperatorBinding separately. EvaluationCase gold,
family and episode provenance stay evaluator-side; the solver receives only its
source-lowered TaskGoal and generation binding.

Immutable EvaluationCohort/v1 and Assessment/v1 pin complete case/capability/group
coverage, rubric, taught scope, source and policy. The policy independently pins
all three full case-census digests. Raw and recomputed bilateral truncation fail.
Fresh family/episode overlap with teaching provenance fails, including paraphrase
siblings under a new episode ID. Parent/candidate cohorts, source bindings, exact
operators, route rules and budgets must match. Typed answer semantics alone earn
credit; a route's score1.0 cannot make an incorrect exact answer correct.

RetentionPolicy/v1 and PairedRetentionEvidence require fresh target improvement,
complete equal-count fresh lesson-group evidence, fixed lesson/protected-group and
whole-school non-regression, and scaled protected-capability allowances on both
fresh and fixed evidence. Opaque group labels carry no ordinal policy. Existing
native reason precedence and floor-scaled loss arithmetic were extracted unchanged
to learning/retention_policy.py and reused by learning_experiment and this adapter.
Legacy parsing and optional policy adjustments stay with the historical owner.

Decision/v1 reports ELIGIBLE or REJECT only; it does not publish a generation.
Perfect source-only targets emit scheduler-consumable REHEARSE_OR_ADVANCE.
ConfigurationOutcome/v1 reports its own observed result with zero optimizer steps;
it cannot certify retained learning or mutate a student.

## Software proof

Red: new owner test failed on the absent module. Final isolated Python3.12 test
environment combines installed NumPy with task-local RDF support; shared environments
were not modified. Solver/DAG/operator/retention owner suites: 76 passed, zero
failures/skips (tests.txt). Existing exam/candidate API imports passed. Whitespace
check passed.

Literal tests include target0/3 to3/3; fixed protected12/12 to10/12 allowed under
1/6 proportional rate; loss3 rejected; fresh protected loss above its scaled budget
rejected despite target gain; each aggregate regression reason; label permutation;
no target gain; family contamination; row truncation; rubric/budget drift; exact
versus neural equal credit; incorrect exact route credit rejected; no optimizer
candidate for a perfect exact target; and configuration receipts with zero steps.
Actual A07 source-granted role lookups return two novel ConceptRefs and the fresh
structural DAG ADD(MUL(2,3),4) returns10 using two operations. These are source/DAG
fixture proofs, not a real learned role-binding or retained-neural-gain witness.

Legacy learning_experiment suite: 70 passed, one error because mlx is unavailable
(legacy-tests.txt). The unavailable test exercises actual parent AdamW custody;
this receipt does not claim it passed. Initial missing-RDF import errors were
resolved in the isolated environment, not hidden as skips.

## Independent EGM and remaining gates

Fresh c05_1_contract_review read pinned EGM
b3a35956759bf7f024af2ff061b2e0b44b438e4c and live #501/#378/B12/B13. Its cold
interface review corrected per-task source binding, provenance splits and full
coverage; it accepted assigning retrospective translator receipts to #503.

Implementation review found two majors: fresh protected loss was absent and full
row coverage was insufficiently pinned. Incident PM-2026-10-29-002 was filed and
native Sheet row219 read back before repair. Both majors were repaired with targeted
adversarial witnesses. Independent targeted re-audit: PASS, no remaining blocker or
major within advisory interface scope. Reviewer inspected12 passing C05 tests;
final76-test combined run is author verification.

Actual B12/B13 accepted generation/optimizer interfaces remain pending, as do B06/
B10/B11 native backend integration, C02 requalification, actual teacher scheduling
consumption and disposable MLX/cold-recovery proof. Generation digests and source
fixture records are provisional boundary evidence, not accepted custody receipts.
C05.2 championship/mastery debt and C05.3 historical translation/uniform admission
remain separate uncompleted leaves. Parent acceptance stays open.
No actual student, AdamW, graph, optimizer or private source operations occurred.
Issue #501 stays open and PR #550 stays draft/unmerged. Next: C05.2 #502.
