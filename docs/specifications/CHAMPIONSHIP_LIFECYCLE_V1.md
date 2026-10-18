# Bilqis championship, graduation reset, and frozen-mentor specification

**Status:** Normative user-directed contract, revision 1 (2026-10-17).
**Scope:** Bilqis MLX human-run school; source-oracled grade exams, champion roles, cross-grade promotion, soups, curriculum epochs.
**Authority:** User's 2026-10-17 corrections, refined by the explicit empty-championship reset and staged grade-completion instructions; ADR-032 through ADR-035, ADR-041, ADR-044, ADR-047, ADR-051 through ADR-055 and protected IPR-0220. This supersedes conflicting historical champion and active-mentor rules but never rewrites their evidence. Document approval is separate from runtime conformance.

## 1. Definitions and state boundaries

The **causal student** is one complete FP32 neural checkpoint with **its own matching native AdamW**. Only the human launches actual neural updates. Candidate admission, graduation, championship promotion and mentor eligibility are different decisions.

- **Capability best:** A source-scored result that may be below 100%. It is not a championship or graduation.
- **Capability champion:** One active owner of a perfect-score capability role on a complete student. One checkpoint may hold many roles.
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
4. Do not fabricate perfect roles, mastery or voting entitlements for any previously mastered or newly introduced capability. A baseline must never masquerade as one or several earned champions.
5. Continue the **causal student** from its latest legitimate committed model/AdamW lineage. Resetting active championship *references* MUST NOT change student weights, overwrite its AdamW, substitute an archive, or make optimizer updates.

Previously mastered grades can acquire new championship owners in this epoch only through section 3. New-epoch soups are rebuilt from newly earned active roles. Source-graph drift, absent graduation evidence or broken custody MUST fail closed, never revert silently to historical mentors.

**This is a simultaneous graduation-boundary reset to ZERO active championships**, not a gradual weighting schedule in which obsolete champions retain teaching influence while newer ones emerge.

**Explicit one-time experimental exception:** The human may request an administrative empty-roster reset **mid-grade** on an already isolated trial run. It is a metadata-only atomic event, not a second graduation, new curriculum admission, optimizer rollback, or model copy. Archive the trial's then-active championship roles and soups, clear all active champion/soup/baseline guidance, retain the complete existing student and native AdamW, and require a **strictly later optimizer step** before fresh examinations may earn any new role. The reset operation is idempotent and must not race an active trainer process. An ordinary training resume never implicitly resets an already established new roster.

## 3. Current-grade and cross-origin promotion

All contenders are complete students, never ensembles or soups. A contender MUST independently earn 100% on each individual capability role it would own.

**Same-origin capability championship:** First test any unscored capabilities in the checkpoint's own grade before awarding **even an individual same-origin title**. Reuse valid scores already obtained for that same checkpoint and source cohort. A record covering only a subset of the grade is insufficient, even if one included capability is perfect. Once the grade is completely scored, individual perfect capability roles can be earned under the ordinary strictly-greater simultaneous breadth rule for displacement; a breadth tie does not replace the incumbent. Other capabilities in the same grade need not be perfect for those individual same-origin roles. If the entire grade cannot yet be fairly examined (for example an unintroduced semantic), defer title promotion and record the exact missing capabilities; do not fabricate evidence or test the entire school instead. This role rule does not relax graduation.

**Cross-origin championship:** A checkpoint trained while another grade is active becomes eligible to take over a different grade only after these sequential, source-bound stages:

1. **Complete target grade before attempting a takeover:** Reuse existing, same-checkpoint, same-cohort source scores for that external grade. Test only the destination-grade capabilities that have not yet been scored on that checkpoint. No partial destination-grade ownership is granted while those scores are missing; hold the proposal with an explicit missing-capabilities receipt.
2. **Perfect all target capabilities:** It must score **100% on every capability of that entire external grade** on one intact checkpoint and the complete current destination-grade rubric. One miss is an all-or-nothing denial: **zero new roles in that grade**, not a subset of perfect capabilities.
3. **Only if replacing actual incumbents: strict whole-school victory:** On the identical cumulative, source-oracled school cohort, rubric, graph and assessment scope, the challenger must score **strictly more correct answers** than **each distinct incumbent checkpoint** whose roles it would replace. Do not run whole-school takeover comparisons for candidates that have not cleared the complete, perfect destination-grade gate. If there are no active incumbent owners, the first full-grade champion needs only the complete perfect target-grade evidence; it does not need a gratuitous whole-school replay merely to defeat a nonexistent champion.

The challenger must satisfy the remaining ordinary role validity, source, custody and admission criteria. Its origin grade supplies no priority or exemption. A grade with **no active incumbent roles** can award its first new-epoch roles on fresh complete target-grade perfection, after the baseline step has been surpassed. There is no fictitious incumbent to outperform. For subsequent takeovers, including saturated grades (for example B=6/6), the full target-grade perfection and strictly greater comparable cumulative school score are mandatory. A tie, worse cumulative score, missing evidence for an **actual** incumbent, missing old geometry or incomplete current-cohort comparison MUST NOT transfer existing roles. A successful takeover atomically assigns **every role in the destination grade to the same victorious checkpoint** before rebuilding its soup.

**Example:** Assume the whole school has 216 questions, and Grade B has six capabilities totaling 72 questions.

| Cross-origin contender B | Contender school | Incumbent B | Incumbent school | Result |
| --- | --- | --- | --- | --- |
| 72/72 | 205/216 | 72/72 | 204/216 | Eligible |
| 72/72 | 204/216 | 72/72 | 204/216 | Reject school tie |
| 71/72 | 210/216 | 72/72 | 204/216 | Reject imperfect B |
| 72/72 | 202/216 | 72/72 | 204/216 | Reject school regression |
| 72/72 | 205/216 | Historical 72/72 | Unmeasured in this school | Reject until paired re-exam |

If several checkpoints own B roles, a complete B takeover must defeat **all** of them on the same cumulative exam. Comparing only against the weakest B owner or the synthetic B soup is not enough.

## 4. Comparable evidence and decision order

Every promotion decision binds the intact student/AdamW checkpoint SHA and optimizer step; admitted graph and grade/capability set; versioned source and oracle; fixed cohort digest/seed; rubric and assessment scope digests; per-capability grade scores; incumbents' exact identities; and any incumbent-versus-contender same-cohort school outcomes. Cumulative numerator and denominator are mandatory **when an actual incumbent comparison occurs**; they are not invented for an uncontested, grade-only championship.

Different cohorts, school scopes, numeric test domains, source contracts, rubric versions or graph geometries are **different comparison strata**. Even matching denominators do not make two independent question sets directly comparable. If a saved incumbent cannot be scored fairly on the entire current school, the proposed cross-origin replacement is unmeasured and MUST NOT be approved. Keep the older record as historical evidence.

The independent complete school exam owns graduation and may supply previously measured grade or whole-school champion evidence. Short paired parent/challenger sentinels own **provisional student update admission only**. Grade-complete championship qualification may reuse already source-scored portions of an independent exam and cannot combine scores from different checkpoint identities or cohorts. Whole-student high-water scores are separately ratcheting recovery/diagnostic references, not automatic championship ownership. A successful local teaching update is not graduation.

Order: validate provenance and custody; check the candidate's own already scored capabilities; fill or defer missing **same-grade** scores before current-grade role promotion; for any proposed **external** grade fill or defer its remaining scores; reject all external roles unless the complete grade is perfect; **only then** obtain whole-school incumbent comparisons if actual roles would be displaced; atomically commit every external-grade role on a victorious checkpoint with an immutable generation/outbox receipt; rebuild the affected soup. Never rescore valid same-checkpoint/same-cohort results or let the challenger become its own pre-promotion reference. Failed, tied or unmeasured proposals leave roles unchanged.

## 5. Frozen soups and teaching rights

When an **earned** role changes owner or covered capability count reaches a new maximum, rebuild the affected grade's frozen weights-only soup from **active earned** championship owners. Each grade capability contributes **one vote**. A checkpoint with multiple roles receives that many ingredient shares; it is loaded once but counted by role multiplicity.

A soup's base vote count is frozen with its recipe. Same-grade advice uses the full count. Cross-grade advice divides it by the current number of admitted grades. Individual champions advise only their own grade; **only earned grade soups** can advise another grade.

Direct and soup advice are restricted to independently source-gold-agreeing training examples, admitted answer types and the teacher's selected distillation strength with the bounded influence policy. Advice may not alter gold, exam answers, graduation, the causal student's parameters or AdamW identity, or the teacher's selected lesson strategy. Never average AdamW moments, blend incompatible embedding geometries, or impose an assistant-selected prior-grade lesson proportion.

After an epoch reset, **old soups remain archived but inactive**. The baseline casts **zero votes and no direct advice**. Later newly earned roles can form new-epoch soups. A tie or refused takeover neither replaces an old incumbent in the active epoch nor silently triggers soup reconstruction.

## 6. Custody and human trial boundaries

Use existing immutable states, generation-bound outbox, protected bundle references, and post-commit retirement controls. Preserve the causal student, matching AdamW, teacher state, semantic version, source receipts, historic champions and soups. A temporary APFS experiment fork is review-pending and may only be retained or discarded after custody/provenance reconciliation. No implicit promotion of a fork into the canonical run.

Agents MAY run source checks, read-only current-run preflights, isolated disposable model and MLX fixture checks, and verified fork preparation. They MUST NOT start actual student optimizer updates or call the human-only neural training command. Only the human starts or resumes those updates.

## 7. Mandatory conformance tests

1. Reject false graduation assembled from mixed checkpoints or 99%-complete school scores. Successful graduation plus new admission resets **all active championships and grade soups to empty**, while retaining a single graduation-linked baseline as a **non-teaching** reference, without inventing mastery or deleting history.
2. Routine exams, candidate rejection and poor results **do not** reset the championship epoch.
3. Full B=72/72 plus strictly better comparable cumulative school score permits cross-origin takeover. B=71/72, a cumulative tie, lower cumulative score or missing incumbent result leaves **every B role unchanged**.
4. A candidate must beat **each** incumbent holding a role in the target grade, including the strongest incumbent. The soup's mean or an archived out-of-scope score cannot substitute.
5. Cohort, scope, rubric or graph mismatch rejects cross-origin promotion. New or stale cohort scores never get compared as raw numbers.
6. A legitimate takeover updates exact individual roles and rebuilds the affected soup with correct vote multiplicity. A failed/tied candidate preserves role pointers and soup bytes.
7. Historic champions and soups become inactive at curriculum admission; **the baseline supplies zero adviser models and zero votes**. Newly earned same-grade champions advise only their grade; only newly earned soups advise across grades. A non-training reset also clears then-active experimental titles and soups and leaves old artifacts archived.
8. The complete student, matching AdamW, teacher history and optimizer step remain unchanged by role reset, promotion or soup creation. Interrupted outbox delivery replays the same event without duplicate promotion.
9. The existing isolated fork passes read-only resume and source-bound inference before the human receives a test command. A locked atomic mid-grade empty-roster reset preserves native AdamW and all prior generations. No extra 8 GB copy is required. Fixture checks cannot establish real neural retention.
10. A perfect current-grade capability **cannot** mint a title before the complete same-grade candidate checkpoint is scored. Missing peer scores produce a named deferral, not a provisional champion.
11. A cross-origin candidate that has tested only five of B's six capabilities, or scored B=71/72, receives **zero** B roles. A perfect B=72/72 uncontested contender may win the **entire B grade** without a whole-school incumbent replay; a contested B=72/72 candidate needs the same-cohort whole-school superiority evidence against every B incumbent.
12. Only unscored members of a proposed grade require additional qualification tests, at their exact checkpoint/cohort identity. Testing, scoring and retaining a local provisional learner does not automatically trigger an expensive all-school championship sweep.

## 8. Runtime implementation and test-readiness rule

The historical `capability_frontier.graduation_perfect` retains its original breadth-only record format. The **active post-reset championship** is governed by `epoch_championships`, using the full-cohort gate in `championship_policy`. In `grade_a_trainer._take_exam`, only independently earned epoch roles and their newly frozen soups enter active advice. Old `graduation_perfect` and `grade_soups` stay archived and protected from retirement. A-to-B and B-to-C admission initialize a **non-teaching** graduation baseline with no titles. An explicit administrative reset uses `scripts/reset_epoch_championships.py --apply` on the existing isolated run, archives any current-epoch roles, and starts empty. The committed events identify winners, denied cross-origin comparisons, and the exact zero-vote reset. The teacher and single causal student still own their original policy, parameters and AdamW.

The existing isolated issue #340 run was **previously activated mid-Grade-C** and had already advanced to optimizer step 230440 before this source correction. Its 80 trial steps and complete native AdamW MUST be preserved. A resume of that existing run tests forward learning with corrected active championship rules. It is **not** a new, historically pure B-to-C boundary experiment, and no second full-model fork is required to learn whether the corrected behavior helps from the current checkpoint.

Do **not** label a human neural learning outcome proven from synthetic acceptance tests. Human launch requires the exact committed source SHA, zero-blocker read-only preflight of this existing run, no concurrent human trainer, and an explicit `--human-run --resume --run-dir` against the isolated folder. Compare observed school scores on their actual cohort identities, the count of earned active roles, soup ingredients and outcomes. The human decides the trial's final keep/discard disposition. Do not prune unique experimental or canonical evidence beforehand.
