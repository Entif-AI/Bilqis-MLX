# SPEC-0002: Bilqis championship, graduation reset, and frozen-mentor specification

**Status:** Normative user-directed contract, revision 2 (2026-10-18).
**Scope:** Bilqis MLX human-run school; source-oracled grade exams, champion roles, cross-grade promotion, soups, curriculum epochs.
**Authority:** User's 2026-10-17 and 2026-10-18 corrections, refined by the explicit empty-championship reset, staged grade-completion instructions, experiment-baseline challenge and cross-grade specialist voting; ADR-032 through ADR-035, ADR-041, ADR-044, ADR-047, ADR-051 through ADR-058, ADR-062 and protected IPR-0220. This supersedes conflicting historical champion and active-mentor rules but never rewrites their evidence. Document approval is separate from runtime conformance.

## 1. Definitions and state boundaries

The **causal student** is one complete FP32 neural checkpoint with **its own matching native AdamW**. Only the human launches actual neural updates. Candidate admission, graduation, championship promotion and mentor eligibility are different decisions.

- **Capability best:** A source-scored per-capability high-water result. It may be below 100% and remains useful archival/diagnostic evidence even when it is not active teaching authority.
- **Capability champion:** The one active best-scoring owner of that capability within the current championship epoch, on a complete student with its own AdamW. A champion may be below 100%. One checkpoint may hold many roles.
- **Maxed capability champion:** An active capability champion whose comparable score is already 100%. Because no larger numerator exists, replacement of that role uses the stronger tie-breaking/takeover rules below rather than ordinary strict score gain.
- **Grade championship:** The active collection of the grade's individual capability roles. One student that scores perfectly on all of that grade's capabilities can contend for a complete-grade takeover under section 3.
- **School score:** Correct answers across **every admitted capability in the cumulative school assessment scope** on one complete checkpoint. Record numerator and denominator, never a bare percentage.
- **Epoch baseline:** The one complete graduation checkpoint, or its exact geometry-compatible post-admission clone, retained as a provenance, custody, and progress reference when new curriculum semantics are admitted. **It holds zero active championship roles and casts zero teacher votes.** It must not become a fallback adviser when no new champion has yet been earned.
- **Frozen grade soup:** Separate immutable weights-only teacher formed from **active, earned** grade roles. It is neither the causal student nor the epoch baseline.
- **Provenance archive:** Old championship pointers, soups, rubrics, exams, roles, checkpoints and receipts. Supersession does not authorize deletion.

## 2. Graduation and the curriculum-geometry reset

The normal epoch-reset trigger is **admission of new semantics or capabilities after graduation**. Routine lessons, challenger acceptance, exams, soup refreshes, poor progress and drift MUST NOT trigger a reset. A numeric scope change is not automatically a new semantic-grade epoch.

Graduation requires **one intact causal student with its own AdamW scoring 100% on the cumulative admitted school** after the prescribed A-through-current revalidation. No combination of per-grade or per-capability champions may manufacture that result.

At the ensuing new-curriculum admission boundary:

1. Verify the graduating checkpoint, own AdamW, complete cumulative exam receipt, old and new semantic graphs and admitted grade.
2. Set **all active championship roles and all active grade soups to empty** at the new epoch boundary; save an explicit, versioned reset receipt and the single graduation-derived baseline **as a non-teaching reference only**. A post-admission clone binds exactly to that graduate and preserves existing parameter and optimizer state.
3. Remove all prior-epoch champions and frozen soups from **active teaching guidance**, regardless of historical breadth, source scores or votes. Preserve the original pointers, files and signed/scored evidence for history and recovery. Until a new complete checkpoint earns a role, **no champion and no soup offers advice**. Do not load the baseline as a fallback teacher.
4. Do not fabricate roles, mastery or voting entitlements for any previously mastered or newly introduced capability. A baseline must never masquerade as one or several earned champions. After the reset, later complete-grade scoring may establish an empty capability role at the best measured score even when that score is below 100%.
5. Continue the **causal student** from its latest legitimate committed model/AdamW lineage. Resetting active championship *references* MUST NOT change student weights, overwrite its AdamW, substitute an archive, or make optimizer updates.

Previously mastered grades can acquire new championship owners in this epoch only through section 3. New-epoch soups are rebuilt from newly earned active roles. Source-graph drift, absent graduation evidence or broken custody MUST fail closed, never revert silently to historical mentors.

**This is a simultaneous graduation-boundary reset to ZERO active championships**, not a gradual weighting schedule in which obsolete champions retain teaching influence while newer ones emerge.

**Explicit one-time experimental exception:** The human may request an administrative empty-roster reset **mid-grade** on an already isolated trial run. It is a metadata-only atomic event, not a second graduation, new curriculum admission, optimizer rollback, or model copy. Archive the trial's then-active championship roles and soups, clear all active champion/soup/baseline guidance, retain the complete existing student and native AdamW, and require a **strictly later optimizer step** before fresh examinations may earn any new role. The reset operation is idempotent and must not race an active trainer process. An ordinary training resume never implicitly resets an already established new roster.

**Explicit experiment-baseline rebase:** On direct human instruction for an already isolated trial, a previously verified complete student may replace the trial's active student as an **independent experiment-local clone**, while the canonical source bundle remains read-only. Restore only source-compatible scheduler/exam state belonging to that exact checkpoint, preserve the experiment's evolved teacher unless separately directed, archive the displaced epoch authority, and reset active roles/soups to empty. A rebase may point backward in optimizer-step history only when it remains later than the prior graduated checkpoint and is explicitly receipted as a rebase rather than an ordinary continuation.

An experiment rebase keeps the replacement baseline non-teaching and outside the active role roster. It is a custody/progress reference, not a fictitious incumbent and not a global embargo on later champions. The baseline checkpoint itself cannot immediately reclaim roles merely because it has saved scores; a strictly later eligible checkpoint must supply complete comparable grade evidence. Empty roles may then be established by the best measured capability scores under section 3, including scores below 100%. Any historical `baseline_challenge_required` field is non-authoritative for this best-score rule and MUST NOT block an otherwise valid empty-role promotion.

## 3. Current-grade and cross-origin promotion

All contenders are complete students, never ensembles or soups. Championship ownership follows comparable per-capability best score. Perfection changes the replacement rule only after an incumbent capability has already reached its maximum.

**Ordinary best-score capability championship:** First complete the checkpoint's entire relevant grade before awarding or moving any role in that grade. Reuse valid scores already obtained for that same checkpoint and comparable source cohort. For an empty role, the first complete-grade scored checkpoint establishes the active champion at its measured score, even below 100%. For a non-max incumbent, only a strictly greater comparable capability score displaces it; a tie or worse score preserves the incumbent. Scores from different cohorts, rubrics, scopes or graphs are not raw-comparable and require a same-cohort incumbent replay before displacement.

**Same-origin maxed role:** If the incumbent capability is already 100%, another 100% on that capability is a score tie, not an improvement. Same-origin replacement therefore requires the existing stricter simultaneous-perfect breadth qualification; a breadth tie does not replace the incumbent. This max-score rule does not retroactively require 100% to become champion in the first place.

**Cross-origin championship:** Origin grade supplies no exemption or penalty. Once the external target grade is completely scored on the challenger, empty roles and non-max incumbents follow the same ordinary best-score rule above, one capability at a time. A strict comparable 10/12→11/12 gain is a valid championship improvement even if another capability in that grade is not perfect. Missing target-grade scores still defer every role movement for that grade.

Only an **equal-max cross-origin replacement** invokes the stronger takeover regime: if one or more actual incumbent roles are already 100% and the challenger also scores 100% on those roles, the challenger must additionally score 100% on the complete target grade and strictly beat each displaced max-role owner on the identical cumulative school cohort/rubric/scope/graph. Failure of that maxed-role takeover leaves those maxed incumbents untouched; it does not undo any independent strict gains over non-max roles or first ownership of previously empty roles established by the same complete examination.

**Equal-max takeover example:** Assume the whole school has 216 questions, Grade B has six capabilities totaling 72 questions, and the challenged B roles are already maxed.

| Cross-origin contender B | Contender school | Incumbent B | Incumbent school | Result |
| --- | --- | --- | --- | --- |
| 72/72 | 205/216 | 72/72 | 204/216 | Eligible |
| 72/72 | 204/216 | 72/72 | 204/216 | Reject school tie |
| 71/72 | 210/216 | 72/72 | 204/216 | Reject imperfect B |
| 72/72 | 202/216 | 72/72 | 204/216 | Reject school regression |
| 72/72 | 205/216 | Historical 72/72 | Unmeasured in this school | Reject until paired re-exam |

If several checkpoints own maxed B roles, an equal-max complete B takeover must defeat **all max-role owners it would displace** on the same cumulative exam. Comparing only against the weakest max owner or the synthetic B soup is not enough. Non-max B roles remain ordinary per-capability best-score competitions.

## 4. Comparable evidence and decision order

Every promotion decision binds the intact student/AdamW checkpoint SHA and optimizer step; admitted graph and grade/capability set; versioned source and oracle; fixed cohort digest/seed; rubric and assessment scope digests; per-capability grade scores; incumbents' exact identities; and any incumbent-versus-contender same-cohort school outcomes. Cumulative numerator and denominator are mandatory **when an actual incumbent comparison occurs**; they are not invented for an uncontested, grade-only championship.

Different cohorts, school scopes, numeric test domains, source contracts, rubric versions or graph geometries are **different comparison strata**. Even matching denominators do not make two independent question sets directly comparable. A non-max best-score challenge requires comparable capability evidence; an equal-max cross-origin takeover additionally requires the incumbent's comparable whole-school evidence. If the required comparison cannot be made fairly, that displacement is unmeasured and MUST NOT be approved. Keep the older record as historical evidence.

The independent complete school exam owns graduation and may supply previously measured grade or whole-school champion evidence. Short paired parent/challenger sentinels own **provisional student update admission only**. Grade-complete championship qualification may reuse already source-scored portions of an independent exam and cannot combine scores from different checkpoint identities or cohorts. Whole-student high-water scores are separately ratcheting recovery/diagnostic references, not automatic championship ownership. A successful local teaching update is not graduation.

Order: validate provenance and custody; complete the relevant grade's scores; establish empty roles and strict gains over non-max incumbents from comparable evidence; preserve ties and regressions; then, only for equal-max cross-origin roles, require complete target-grade perfection and strict whole-school victory against the actual max-role owners to be displaced. Commit each valid role movement with immutable generation/outbox evidence and rebuild the affected soup. Never rescore valid same-checkpoint/same-cohort role evidence unnecessarily or let the challenger become its own pre-promotion reference.

## 5. Frozen soups and teaching rights

When an **earned** role changes owner or covered capability count reaches a new maximum, rebuild the affected grade's frozen weights-only soup from **active earned** championship owners. Each grade capability contributes **one vote**. A checkpoint with multiple roles receives that many ingredient shares; it is loaded once but counted by role multiplicity.

A soup's base vote count is frozen with its recipe. Same-grade advice uses the full count. Cross-grade advice divides it by the current number of admitted grades.

Each active **maxed capability champion** also contributes one direct advisory vote across admitted grades. The vote belongs to the capability role, not the checkpoint file. If one checkpoint owns several maxed roles, load it once and count one vote per qualifying role. A non-max capability champion contributes zero direct votes, but it remains a valid soup ingredient and soup vote under the existing best-role contract.

Direct and soup advice are restricted to independently source-gold-agreeing training examples, admitted answer types and the teacher's selected distillation strength with the bounded influence policy. Wrong mentor predictions contribute no advice for that example. Advice may not alter gold, exam answers, graduation, capability scheduling, the causal student's parameters or AdamW identity, or the teacher's selected lesson strategy. Never average AdamW moments, blend incompatible embedding geometries, or impose an assistant-selected prior-grade lesson proportion.

After an epoch reset, **old soups remain archived but inactive**. The baseline casts **zero votes and no direct advice**. Later newly earned roles can form new-epoch soups. A tie or refused takeover neither replaces an old incumbent in the active epoch nor silently triggers soup reconstruction.

## 6. Custody and human trial boundaries

Use existing immutable states, generation-bound outbox, protected bundle references, and post-commit retirement controls. Preserve the causal student, matching AdamW, teacher state, semantic version, source receipts, historic champions and soups. A temporary APFS experiment fork is review-pending and may only be retained or discarded after custody/provenance reconciliation. No implicit promotion of a fork into the canonical run.

Agents MAY run source checks, read-only current-run preflights, isolated disposable model and MLX fixture checks, and verified fork preparation. They MUST NOT start actual student optimizer updates or call the human-only neural training command. Only the human starts or resumes those updates.

## 7. Mandatory conformance tests

1. Reject false graduation assembled from mixed checkpoints or 99%-complete school scores. Successful graduation plus new admission resets **all active championships and grade soups to empty**, while retaining a single graduation-linked baseline as a **non-teaching** reference, without inventing mastery or deleting history.
2. Routine exams, candidate rejection and poor results **do not** reset the championship epoch.
3. An empty capability role accepts the first complete-grade measured best even below 100%; a non-max incumbent transfers only on a strict comparable capability-score gain. A score tie leaves that role unchanged.
4. For an equal-max cross-origin replacement, full target-grade perfection plus strictly better comparable cumulative school score is required against **each max-role incumbent that would be displaced**. The soup's mean or an archived out-of-scope score cannot substitute.
5. Cohort, scope, rubric or graph mismatch rejects cross-origin promotion. New or stale cohort scores never get compared as raw numbers.
6. A legitimate takeover updates exact individual roles and rebuilds the affected soup with correct vote multiplicity. A failed/tied candidate preserves role pointers and soup bytes.
7. Historic champions and soups become inactive at curriculum admission; **the baseline supplies zero adviser models and zero votes**. Newly earned maxed capability roles advise across grades at one direct vote per role. Newly earned soups advise with full same-grade base votes and the foreign-grade divisor. Non-max roles remain soup-only advisers. A non-training reset also clears then-active experimental titles and soups and leaves old artifacts archived.
8. The complete student, matching AdamW, teacher history and optimizer step remain unchanged by role reset, promotion or soup creation. Interrupted outbox delivery replays the same event without duplicate promotion.
9. The existing isolated fork passes read-only resume and source-bound inference before the human receives a test command. A locked atomic mid-grade empty-roster reset preserves native AdamW and all prior generations. No extra 8 GB copy is required. Fixture checks cannot establish real neural retention.
10. A capability, perfect or not, **cannot** mint or move a title before the complete relevant-grade candidate checkpoint is scored. Missing peer scores produce a named deferral, not a provisional champion.
11. A cross-origin candidate that has tested only five of B's six capabilities receives zero B role movements. Once all six are scored, it may establish empty roles and strictly improve non-max roles individually even at B=71/72. Equal-max B roles require the stronger complete-perfect-grade and whole-school takeover evidence.
12. Only unscored members of a proposed grade require additional qualification tests, at their exact checkpoint/cohort identity. Testing, scoring and retaining a local provisional learner does not automatically trigger an expensive all-school championship sweep.

## 8. Runtime implementation and test-readiness rule

The historical `capability_frontier.graduation_perfect` retains its original breadth-only record format. The **active post-reset championship** is governed by `epoch_championships`: ordinary roles are best-score roles, while `championship_policy` is invoked only for equal-max cross-origin takeovers. In `grade_a_trainer._take_exam`, only independently earned epoch roles and their newly frozen soups enter active advice. Each active maxed role contributes one direct capability vote across grades. A frozen soup gives one vote per active capability role, including a best-below-max role, with the existing foreign-grade divisor. Shared direct-role checkpoints are inferred once and weighted by qualifying role count. All advice remains independently source-gold-gated. Old `graduation_perfect` and `grade_soups` stay archived and protected from retirement. A-to-B and B-to-C admission initialize a **non-teaching** graduation baseline with no titles. An explicit administrative reset archives any current-epoch roles and starts empty. The teacher and single causal student still own their original policy, parameters and AdamW.

For the current isolated issue #340 recovery, the intended next-run roster starts empty except for the explicitly authorized recovery roles proven by the preserved 230216-versus-230232 fixed exam: B.AND, B.IMPLIES and B.NOT belong to the 230216 checkpoint because it strictly outscored 230232 on exactly those capabilities. Other roles remain empty until later complete-grade evidence establishes their bests. This explicit preload does not declare those three capabilities mastered and does not fabricate roles for tied capabilities.

Do **not** label a human neural learning outcome proven from synthetic acceptance tests. Human launch requires the exact committed source SHA, zero-blocker read-only preflight of this existing run, no concurrent human trainer, and an explicit `--human-run --resume --run-dir` against the isolated folder. Compare observed school scores on their actual cohort identities, the count of earned active roles, soup ingredients and outcomes. The human decides the trial's final keep/discard disposition. Do not prune unique experimental or canonical evidence beforehand.
