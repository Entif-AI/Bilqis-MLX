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
adapters. There were **18** full-suite failures in the initial sweep; the
subsequent 1,162-test sweep had **two** obsolete fixture failures, repaired
in their own tests. The completed final `npm test` run is **PASS**:
**1,162 total, 1,124 passed, 0 failed, 0 errors, 38 skipped**;
**194.316 seconds** of test execution. The 38 skips are reported, not
converted into proof of the skipped conditions. Evidence is retained in
the operator's local test log
`/tmp/bilqis-systemic-closure-full-suite-20261021.log`.

The separate `npm run quality:check` static smell audit reports **75
baseline-relative review findings** and does not pass. Those require their
own source-scoped triage rather than an unreviewed baseline blessing. The
factory architecture check, docs check, semantic-boundary check, and
`release:check` completed successfully; release checking is not proof of
remote deployment.

`STAGNATION_REVIEW_REQUIRED` is an intentional human-review boundary after
rejected recovery attempts, **not** evidence that the student mastered its
remaining B/C debt. This work repaired evidence custody, restart behavior,
scope authority, and examination throughput; it did not turn rejected
candidate updates into successful learning or eliminate the need to review
the teaching policy. The source hashes, immutable states, exams, event ledger,
and timing traces remain in the existing protected run. Do not overwrite
those artifacts, rebase the student's optimizer, or claim a new graduation.
