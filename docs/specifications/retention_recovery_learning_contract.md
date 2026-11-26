# Retention Recovery Learning Contract

Status: current repository control map for FOUNDATION_ACQUISITION retention recovery.
Authority: ADR-019, ADR-020, ADR-022, ADR-031, ADR-083, ADR-084, ADR-097, ADR-133,
ADR-134, ADR-142, ADR-145, ADR-153, ADR-154, ADR-155 and ADR-156, plus
`docs/specifications/developmental_evidence_policy.json`. Historical experiment
records remain evidence; this document controls their prospective interpretation.

## Current developmental contract

Bilqis is in `FOUNDATION_ACQUISITION`. The current job is to acquire and retain the
semantics actually taught at the learner's earned curriculum complexity. Exact taught
recall, repeated exposure, rote memorization, same-specimen replay, authorized cache or
memoized retrieval, and taught-composition replication are legitimate learning.

Generalization over untaught semantics is `MEASURE_ONLY`. It remains useful telemetry,
but it is not a current retention, promotion, graduation, experiment-admission or
intervention-ranking gate. A future fixed generalization gate requires explicit human
maturity admission.

Independent assessment means source/oracle truth is independently authorized, cohort
identity and rubric are explicit, scoring is honest and reproducible, and the scorer
does not receive gold as an input. Independence does not inherently require unseen
semantics or zero specimen, source-family, or episode overlap with instruction.

## Developmental sequence

1. Teach semantic identities and bounded answer types.
2. Establish reliable recall and replication over those taught semantics.
3. Establish retained composition over already taught constituents.
4. Expand semantic breadth and composition complexity as competence is earned.
5. Measure transfer/generalization throughout, but do not make untaught-semantics
   performance authorizing until a later explicit maturity decision.

Teaching `C = C` and then testing `D = D` before the learner has been taught the
relevant `D` semantic material is a transfer/generalization probe, not merely a harder
foundation-recall test. Its result may be scientifically interesting without defining
whether the taught `C` semantic was learned.

## Evidence vocabulary

- **Acquired / learned:** the accepted learner can produce the source-correct answer at
  current earned complexity after instruction. Taught recall counts.
- **Retained:** acquired competence survives subsequent learning and remains available
  in the legitimately accepted learner.
- **Promotion-ready:** the current grade passes its authorized promotion criteria. This
  is not synonymous with mastery.
- **Mastered:** the complete applicable grade/rubric is perfect at one intact accepted
  checkpoint under the governing mastery contract.
- **Generalized:** the learner succeeds on novel or untaught meaning-preserving
  constructions. This is currently measured but non-authorizing.

## Retention-recovery experiment law

The current product outcome is **independently verified retained foundational
competence on actually taught semantics per wall-clock minute**. A valid matched
experiment therefore reports at least two distinct surfaces:

1. **Foundation acquisition/retention:** independently scored source-correct competence
   on taught semantics at current earned complexity. Taught or previously shown
   specimens are eligible. This is the current product learning surface.
2. **Generalization/transfer:** held-out, zero-overlap, fresh-family, fresh-episode or
   novel-composition performance. This is observational telemetry until maturity
   admission.

Protected-regression requirements remain binding on the accepted competence the
retention law actually protects. C05, ADR-142 mastery-debt utility, ADR-145 canary/final
decision law, source/gold correctness, learner+AdamW custody and legitimate acceptance
authority are unchanged. The corrected learning contract changes the assessment
meaning, not those safeguards.

Historical zero-overlap v9/v10 panels remain valid transfer measurements under their
frozen protocols. They must not be relabeled as proof that foundation learning did or
did not occur. Their resource, causal-treatment and protected-regression evidence
remains usable where the measured surface is actually comparable.

## Pinned v1.0.0 behavioral comparator

Pinned comparator commit:
`a990685555cd9d5171691167ab32645a6a2835ca`.

Repository-designated legacy adaptation oracle:
`d84d2ab9e2d79817c131ef7e0d4ec0d574e57b32`.

v1.0.0 is a behavioral regression comparator, not blanket authority to restore old
architecture or supersede current C05/ADR-142 semantics. A mechanism's presence in the
pinned reference means its parity or deliberate replacement must be accounted for; it
does not establish that the mechanism independently caused superior learning.

| Learning behavior | Exact pinned v1 source | Current BAMF owner | Parity status / material gap |
| --- | --- | --- | --- |
| Weakest-capability selection | [`curriculum/scheduler.py::weakest_three`, L439-L445](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/curriculum/scheduler.py#L439-L445) | `runtime/_learning_first/priority_frontier.py::learning_first_priority_frontier` | **PARTIAL / UNDER #1628.** Current branch carries typed competence into priority ordering, but the issue remains owner for source-compatible accepted-learner evidence, recovery membership and cadence proof. Do not restore the obsolete v1 scheduler topology wholesale. |
| Foundation rehearsal | [`curriculum/foundational_rehearsal.py::rehearsal_plan`, L16+](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/curriculum/foundational_rehearsal.py#L16) | `runtime/_batch/retention_support.py`, `runtime/_source/source_prefetch.py` | **CHANGED / UNDER RECOVERY.** Current support is source-authenticated and retention-coupled. v10 proved an experimental full protected-pair reservation can alter preservation behavior; it is not production-adopted. |
| Previsit student diagnostics | [`runtime/teacher_outcome_runtime.py::build_region`, L78-L118](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/runtime/teacher_outcome_runtime.py#L78-L118) | `runtime/_teacher/teacher_policy_selection.py::ordinary_previsit_diagnostics`, consumed by `accepted_priority_visit.py` | **RESTORED IN CURRENT BRANCH; #1643 ACCEPTANCE OPEN.** Current projection includes fixed-reference/target deficits and structural debt; behavioral discrimination and native receipt remain issue-owned proof. |
| Contextual teacher-policy selection | [`learning/learning_experiment.py::contextual_pick`, L782+](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/learning_experiment.py#L782) | `learning/_learning_experiment_policy.py::contextual_pick`; `runtime/_teacher/teacher_policy_selection.py::select_visit_policy` | **PRESERVED / EVOLVED.** Current policy adds newer teacher-selection and checkpoint-local retirement semantics. |
| Fresh target source per optimizer step | [`runtime/visits.py`, per-step seed/draw L592-L702](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/runtime/visits.py#L592-L702) | `runtime/_source/source_prefetch.py`; visit source-request/seeds | **PRESENT BUT #1608 OWNS PARITY/PROOF.** Freshness is a teaching mechanism, not the definition of learning; repeated lawful specimens remain valid. |
| Weakness-target reservation and realized lesson shaping | [`learning/lesson_selection.py::reserve_weakness_targets`, L130+ and `select_source_lesson`, L323+](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/lesson_selection.py#L130) | `learning/_learning_experiment_lessons.py`; `runtime/_visits/selection.py` | **PARTIAL / UNDER #1627.** Current native priority delivery must prove that selected HOW policy materially changes delivered instruction and unresolved source-grounded weaknesses reach lessons. |
| Binary and typed/direct answer teaching | [`learning/lesson_selection.py::_choose_binary_rows`, L51+; `_choose_typed_rows`, L99+](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/lesson_selection.py#L51-L129) | `learning/_teaching/source_selection.py`; typed decoder/Factory contracts | **PRESERVED CONTRACT.** ADR-019/020 require fitting bounded semantic answer types plus complementary Boolean/evidence views. Binary-heavy recovery panels must not redefine Bilqis learning as TRUE/FALSE only. |
| Perfect-target preflight | [`runtime/visits.py`, L521-L535](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/runtime/visits.py#L521-L535) | prospective C05/native preflight owned by #1641 | **RESTORED WITH CURRENT-LAW QUALIFICATION.** Skip only when the exact current comparable measured baseline makes positive target gain impossible; a small familiar perfect probe is not certification. |
| Adviser/distillation from qualified whole-student mentors | [`learning/lesson_guidance.py::choose_lesson_batch`, L20-L53](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/lesson_guidance.py#L20-L53) and [`learning/champion_confidence.py`](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/champion_confidence.py) | current `learning/lesson_guidance.py`, championship/mentor runtime; #1609 | **PRESENT / REALIZATION UNDER #1609.** Current titles, soups, epoch reset, source-gold gating and custody law supersede any older authority interpretation. |
| Strategy retirement / bounded exploration | contextual policy state around [`learning/learning_experiment.py::contextual_pick`, L782+](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/learning_experiment.py#L782) | `learning/_learning_experiment_policy.py`, ADR-156 | **INTENTIONALLY CHANGED.** Two checkpoint-local target failures may retire an effective policy; target-positive `PROTECTED_CAPABILITY_REGRESSION` is explicitly not target-failure evidence. |
| Phase-specific proportional protected-loss budgets | [`learning/learning_experiment.py::_protected_diagnostics`, L309-L338](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/learning_experiment.py#L309-L338) | `learning/_learning_experiment_decision.py::_protected_diagnostics`; C05/ADR-142 final retention authority | **MECHANISM PRESERVED, AUTHORITY EVOLVED.** The proportional diagnostic still exists, but it cannot override current earned-baseline/mastery-debt protection or final C05 authority. |
| Adaptive candidate horizon under repeated interference | [`learning/learning_experiment.py::candidate_step_budget`, L745-L779](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/learning_experiment.py#L745-L779) | `learning/_learning_experiment_policy.py::candidate_step_budget`; `runtime/_visits/preparation.py` | **PRESERVED / EVOLVED.** Current code still shrinks disposable horizon under repeated interference; ADR-156 separately governs checkpoint-local target-failure retirement. |
| Cross-grade mastery debt and recovery spiral | [`curriculum/scheduler.py::_promote`, L638-L701; `_refresh_mastery_debt`, L770-L781](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/curriculum/scheduler.py#L638-L701) | current `curriculum/scheduler.py::_refresh_mastery_debt`; runtime custody/reconciliation | **PRESERVED / EVOLVED.** Current generated-grade scheduler retains cross-grade debt; present recovery semantics and ADR-142 protection control rather than a blind v1 rollback. |
| Stagnation detection and bounded reprobe/reentry | [`learning/stagnation_control.py`, L479-L520](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/stagnation_control.py#L479-L520) plus [`curriculum/scheduler.py::reactivate_stagnation_debt`, L1086-L1097](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/curriculum/scheduler.py#L1086-L1097) | current `learning/stagnation_control.py`; `runtime/_custody/reconciliation.py`; `runtime/operator_session/operator_stagnation.py` | **PRESERVED / EVOLVED.** Current implementation requires source-scored repeated recovery evidence and typed reentry; do not reinterpret unavailable measurement as stagnation. |
| Whole-student peak custody and comparable-checkpoint selection | [`learning/whole_student_retention.py::advance_peaks`, L17-L64](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/learning/whole_student_retention.py#L17-L64) and [`curriculum/scheduler.py::choose_best_whole_student`, L1188-L1214](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/curriculum/scheduler.py#L1188-L1214) | `learning/_retention/whole_student_retention`; `runtime/_custody/boundary_commit.py`, checkpoint retention/publication | **PRESERVED / EVOLVED.** Matching model+AdamW and same-scope comparability remain explicit; a peak is custodial evidence and never silently replaces the live learner or final acceptance law. |
| Retention/preservation economics | target/protected support in [`runtime/visits.py`, L512-L757](https://github.com/Entif-AI/Bilqis-MLX/blob/a990685555cd9d5171691167ab32645a6a2835ca/bilqis_mlx/runtime/visits.py#L512-L757) | C05, ADR-142, `runtime/_batch/retention_support.py`, current candidate-retention owners | **INTENTIONALLY REPLACED.** Do not blindly restore historical loss budgets. Current earned-baseline and normalized quadratic mastery-debt law controls. |

## Material unresolved recovery gaps

1. The historical v9/v10 72-row zero-overlap panels measure transfer/generalization,
   not the current primary foundation-learning surface. A taught-foundation assessment
   must be scored separately before those units can adjudicate retained foundational
   competence.
2. Same-workload quantitative v1 retained taught-competence-per-minute is not yet
   available. Do not fabricate parity from a version/hash alone.
3. #1627, #1609 and #1628 still own material lesson-shaping, realized adviser and
   competence-driven selection proof respectively.
4. Preservation reservation improved the v10 zero-overlap protected-loss count relative
   to control, but v10 was not production-adopted and its foundation-learning effect is
   unresolved until assessed on taught semantics.

## Historical-record rule

Do not rewrite old experiment outcomes to fit this contract. Preserve their frozen
protocols and labels. Add prospective interpretation overlays that identify which
reported quantity is foundation acquisition/retention, which is generalization, and
which is merely execution or resource telemetry. Where old terminology conflicts with
current ADR authority, the dated current policy controls future decisions.
