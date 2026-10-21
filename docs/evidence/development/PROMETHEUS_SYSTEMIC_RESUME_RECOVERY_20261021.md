# Prometheus live-run recovery: source scope, custody, and restart proof

**Date:** 2026-10-21. **Repository:** `bilqis-mlx` on
`349-bouta-tree-fitty`. **Live run:** `runs/codex-0001-prometheus`.
This is a bounded, source-backed engineering record, not a claim that the
trainer has achieved curriculum mastery, universal fault tolerance, or a
successful release. No remote push, pull-request merge, or issue closure is
authorized by this report. Formal incident-ledger registration is separate.

## Proven failure mechanisms

1. **Mismatched historical cohort ABI.** Multiple consumers recomputed the
   content digest of a v2 stored cohort using `schema` as its rubric, although
   v2 signs the distinct `rubric_sha256`. The same mistaken assumption affected
   diagnostics, replay, frontier, and championship evidence. A shared
   schema-aware verifier now retains distinct v1/v2 semantics and rejects
   altered cohort content or source/release metadata.
2. **Unlawful authority supersession.** Resume-time migration treated the
   latest routine examination's scope as the only lawful historical rubric,
   erased leaders earned under other valid scopes, and reset all active
   championship roles. That speculative repair has been removed. A genuinely
   contradictory *source witness* now invalidates only the affected capability
   role and grade soup; unrelated titles and permanent matchups survive.
3. **Destroyed settled-matchup authority.** At saved generation **13332**, the
   valid school epoch contained **2,957** settled matchups. The former repair
   published generation **13333** with the settlement map emptied. Recovery
   checked the immutable source and reset generations, exact school identity,
   run ID, committed and published event ID, and the absence of intervening
   match outcomes. It restored precisely those **2,957** decisions in a new
   immutable generation **13352** under the exclusive operator lock, without
   modifying earlier states or the model/optimizer bundle. Ten live roles and
   two live grade soups were unchanged at that restoration boundary.
4. **Unbounded live diagnostic query.** Historical-trend processing decoded
   unrelated archived examination states on the first current examination. A
   read-only census counted **2,371** historical exam events, only **15** with
   the current rubric and generator. The live trend query now filters by
   trusted, complete event headers *before* reading large state snapshots,
   then still verifies selected state, cohort, outbox, and exact comparison
   contracts. Missing/malformed event headers remain fail-closed; the default
   unfiltered full audit is unchanged. New regressions verify skipped-header
   tampering and cache separation by comparison contract.
5. **Scheduling mistaken for qualification.** After a stagnation quarantine,
   an incomplete cumulative exam legitimately moved ordinary teaching to a
   different grade. That grade transition was mistaken for authorization to
   perform a graduation/promotion assessment, causing
   `ASSESSMENT_NOT_GRADE_SEALED_RUBRIC`. Promotion now requires complete
   assessment scope, separately from a scheduler transition. Withheld
   capabilities remain explicit mastery debt, never synthetic perfect scores.
6. **Predecessor-v2 and source-witness authority gaps.** Expanding the semantic
   catalog could rebaseline the prior v2 exam without preserving its signed
   release identity. Historical v2 recovery now requires the exact immutable
   direct predecessor named by the successor release, structural lineage
   verification, successor admission, semantic graph and student binding, and
   intact scope/rubric/source/cohort pointers. v2 structural autonomy evidence
   supplies the canonical typed curriculum to its registered witness adapter
   rather than `course=None`; older v1 Course witnesses remain supported.

## Live execution evidence

The real primary student was retained, not reset. The observed protected
checkpoints and session outcomes are:

| Boundary | Result | Evidence |
| --- | --- | --- |
| Restoration, generation 13352 | 2,957 original settlements restored | Same student and AdamW **138616**, 10 unchanged active roles; immutable source/repair event verified |
| First post-history-optimization session | Exit 0 after **171 seconds**, 27 visits | Eight completed exams; no operator block; normal `STAGNATION_REVIEW_REQUIRED` stop |
| Qualification-guard reproduction before repair | Exit 2 after **101 seconds** | Exact `ASSESSMENT_NOT_GRADE_SEALED_RUBRIC` callstack identified; no checkpoint reset |
| Post-qualification repair session | Exit 0 after **225 seconds**, 35 visits | Twelve exams; AdamW **138712**, 11 active roles, 3,002 settlements |
| Final measured post-release session | Exit 0 after **262 seconds**, 33 visits | Twelve exams; normal `STAGNATION_REVIEW_REQUIRED` stop |
| Current sealed state, generation **13533** | 10,205 cumulative visits, AdamW **138792** | **11** live roles, **3,040** settled matchups; `state.json` equals `states/0013533.json` |

The successful sessions' longest measured examinations were approximately
**10.6** and **13.7** seconds in the observed runs, replacing the earlier
multi-minute cold scan. This is a measured throughput improvement, not a
permanent upper-bound guarantee. The student underwent accepted retention
updates during these supervised training sessions; the ledger-restoration
transaction itself performed **zero** neural updates.

The operator's source-verifying dry-run after the earlier extended session
returned **zero blockers**, `VERIFIED_ALL_PUBLISHED` outbox custody, and
`VERIFIED_EXISTING_V2_WITH_SAVED_EVIDENCE` compatibility. No trainer process
remained active after the final session.

## Regression and scope limits

Every critical correction has a red-before/green-after regression, including
valid different-scope evidence preservation, valid and corrupt v2 cohort
readback, capability-local title invalidation, settlement restoration event
custody, historical-diagnostic event-header tamper detection, incomplete-exam
qualification prohibition, predecessor-v2 lineage tampering, and real v2
composition/prerequisite witness generation. Historical system tests were
updated to exercise the actual executable factory instead of removed v1
adapters. There were **18** full-suite failures in the initial sweep; a later
1,162-test sweep had **two** obsolete fixture failures, repaired in their own
tests. After the systemic evidence-ABI and quality refactors, and the later
runtime-provider compatibility regression below, the final repository-wide
`npm test` run is **PASS**: **1,168 total, 1,130 passed, 0 failed, 0 errors,
38 skipped**; **193.556 seconds** of test execution. The 38
default skips are deliberate legacy/full Grade-B opt-ins. They were separately
enabled and executed as a 43-test compatibility/trainer set: **43 passed, 0
failed, 0 skipped** after the compatibility repair. Evidence is retained in
`/tmp/bilqis-351-adapter-full-suite.log` and
`/tmp/bilqis-351-adapter-grade-b-optin.log` on the operator machine.

The final `npm run quality:check` also **passes**. The static inventory still
contains acknowledged historical findings, but there are **0 new
baseline-relative findings**; the baseline itself was not regenerated or
weakened. The factory architecture/docs checks included by that command,
`scripts/check_semantic_boundaries.py`, `release:check`, and `git diff --check`
all completed successfully. Release checking is not proof of remote
deployment.

## Repeated disposable lifecycle stress

The final agent-safe endurance pass repeated three production-owner scenarios
in **12 fresh-process rounds** without touching the Prometheus student:

- the full disposable Grade-B `B -> A -> B` training lifecycle with a real toy
  MLX student and its own AdamW, 18 optimizer-changing visits and three exams
  per round;
- staged Grade-C toy updates across seven capability stages, with a fresh exam
  and source-verified `_resume` readback after each stage; and
- championship source-context repair, including capability-local invalidation,
  permanent settlement preservation, and repeat-call idempotence.

All 12 rounds passed. Across the repeated B/C scenarios this exercised roughly
**300 optimizer-changing disposable visits, 120 exams, and 84 post-exam
restart/readbacks**, plus repeated source-context repair/idempotence checks.
This is deliberately stronger than a one- or two-minute smoke test: it stresses
the exact custody, curriculum, assessment, championship, persistence, and
restart combinations that produced the reported failures.

It is **not** represented as a literal 180-minute wall-clock run of the
canonical Prometheus student. Ordinary and long-running training remains
human-operated. The user's standing repair authorization separately permits
short, explicitly finite agent-run trainer sessions when required to reproduce
or verify a defect without resetting or replacing the current student. A full
180-minute `npm start` remains a separate human-owned operational endurance
observation if that wall-clock claim is required.

## Live B.AND provider-refactor drift and bounded repair verification

A later operator restart exposed
`FACTORY_EXECUTABLE_GENERATION_ADAPTER_DRIFT:B.AND`. A bounded reproduction
failed immediately at generation **13,534** with the optimizer still at
**138,792**. The admitted B.AND provider descriptor and the current registered
descriptor agreed on adapter identity, generator, oracle set, profile domain,
variation axes, and teaching options. Only the implementation digest differed:
the admitted release carried `345f484b...`, while the current shared Boolean
identification adapter computed `c065d0cf...` after later source refactoring.

The exact current B.AND implementation then reproduced the admitted release's
sealed B.AND verification specimens at the release's own verification seed:
the specimen-ID digest and complete specimen-content digest matched
byte-for-byte. The blocker therefore conflated a shared provider's source-code
fingerprint change with capability-level semantic drift.

Executable generation now keeps exact descriptor identity as its fast path.
When only implementation/cohort-code evidence changed while the declared
adapter contract is otherwise identical, the current implementation must first
reproduce the affected capability's immutable sealed verification specimens.
Only then may it execute the older admitted release. A changed implementation
whose sealed specimen behavior differs still raises
`FACTORY_EXECUTABLE_GENERATION_ADAPTER_DRIFT`. Released teaching options use
the same compatibility proof rather than a second, contradictory digest-only
interpretation.

The regression was demonstrated red-before/green-after. Adjacent generation,
evidence, autonomy, prefetch, and executable-assessment tests pass **36/36**.
The complete repository suite and Grade-B opt-in suite pass as recorded above.

Under the user's standing authorization for small trainer repair tests, **six
consecutive bounded Prometheus sessions** then completed without an operator
block. The first committed **4 visits**, advanced AdamW **138,792 -> 138,808**,
and stopped normally at its explicit visit limit. Three chained restart
sessions then committed **15 more visits and 7 exams**, crossed between Grades
B and C, advanced the live student to AdamW **138,824**, and grew the permanent
settlement ledger from **3,040 to 3,061**. After the repair was committed, two
additional restarts committed **11 visits and 4 exams** with normal
`TIME_LIMIT_REACHED` exits; they advanced AdamW to **138,840** and the
settlement ledger to **3,072**.

Across those six bounded sessions the repaired live path therefore committed
**30 visits**, at least **11 explicitly counted exams**, multiple B/C scheduler
transitions, and **48 retained optimizer steps** without reproducing adapter
drift or another operator block. The final saved state is generation **13,582**,
cumulative visits **10,236**, stage `RECOVERY_1`, active status
`ACTIVE_GRADE_C`, **11** active championship roles, and **3,072** permanent
settled matchups. `state.json` matches immutable `states/0013582.json`. A fresh
post-commit source-verifying preflight exits **0**, reports
`VERIFIED_ALL_PUBLISHED` outbox custody at AdamW **138,840**, and the quality
gate reports **0 new baseline-relative findings**.

The earlier `STAGNATION_REVIEW_REQUIRED` stops listed above were subsequently
shown to be **premature policy stops**, not merely intentional review
boundaries. The old controller could quarantine a capability after two failed
recovery visits even when fresh held-out exams had shown recent improvement,
and it had no elapsed-time requirement at all. In the same operator session,
the dashboard's `GREW` baseline could also be re-anchored twice at the same
session start, visibly resetting all growth percentages to zero.

The repaired controller now requires **20 full minutes of capability-local
measured no-progress** before quarantine is eligible. Any fresh measured
accuracy improvement resets that capability's no-progress clock, including
transfer gains caused by training another capability. The two failed recovery
rounds remain necessary but are no longer sufficient by themselves. The live
dashboard also refuses to re-anchor the same execution baseline twice at the
same optimizer step.

Live proof from the exact deferred Prometheus state: a bounded three-minute
resume completed **26 visits and 7 exams**, advanced AdamW **139,016 ->
139,080**, committed generation **13,769**, and stopped on
`TIME_LIMIT_REACHED` after **180.442 seconds** with **zero stagnation
quarantines and zero stagnation alerts**. During that run, fresh exams showed
measured gains including B.AND **5/12 -> 9/12**, B.IFF **6/12 -> 9/12**, C.ADD
**12/33 -> 14/33**, and C.COUNT **19/33 -> 20/33**. The final `state.json`
matches immutable `states/0013769.json`.

`STAGNATION_REVIEW_REQUIRED` therefore remains a legitimate review boundary
only after the sustained no-progress window **and** repeated recovery failures
are both proven. It is still not evidence that the student mastered its
remaining B/C debt. The source hashes, immutable states, exams, event ledger,
and timing traces remain in the existing protected run. Do not overwrite
those artifacts, rebase the student's optimizer, or claim a new graduation.
