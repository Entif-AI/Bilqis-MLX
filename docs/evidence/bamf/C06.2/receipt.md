# C06.2 — grade-neutral priority, teacher delegation and local history

Status: **IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION**. Issue #505 stays open.
Lane `codex/bamf02-c-runtime`; cumulative PR #550 stays draft and unmerged.
Consumed reviewed unified `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4` through
merge `d93e9587dfd5ccb6d6895d8556ddb13b39b56299`.
Authority: IPR-0220, C06 #379 and child #505. No persistent learner, own AdamW,
source admission, graph or accepted-generation mutation occurred.

## Owned behavior

1. `propose_attention_options(frontier, history)` delegates the existing signed
   dispatcher. History cannot manufacture a teaching option. The selected WHAT
   supplies three independent, verified ordinal features to the actual replay
   teacher's existing diagnostic context. Stable features include known masks and
   the metric-policy digest; per-event receipt identities do not fragment learning.
   `choose_priority_teaching` clones the actual `TeacherEpoch`, validates replay,
   student and source-context identities, and invokes native `select_visit_policy`.
   Unique selected-capability membership in the digest-matched actual
   `ScheduleProgram` determines the grade used by existing population/canary
   filters. It never infers membership from a capability name. Correction actions
   return ACTION_REQUIRED; held options return NO_ADMISSIBLE_TEACHING. Neither
   consumes the teaching RNG. Native teacher knobs and canary ownership remain
   with their existing implementations; the wrapper reports native metadata
   without claiming diagnostic consumption when the native selector did not.
2. Signed history preserves all observations. Fixed nonoverlapping windows close
   every 20 accepted events within capability epoch, scope, source binding/family,
   release, rights and correction generation. Neural/teacher generation changes
   retain per-event provenance without restarting that capability window. Late
   events append with explicit lag and never reorder a closed window. Exact event
   replay is idempotent; divergent reuse fails closed. A signed versioned window
   policy declares the independent-lineage threshold. Analogous observed LOW
   impact/LOW exigency defects can nominate one stable investigation candidate;
   paraphrases from one lineage cannot mint independence. Candidates carry
   source_gold=False and qualified_for_teaching=False.
3. Signed row bindings cover actual C02 batch release, generation, delivery digest,
   row identity, model input and complete delivery provenance, plus salience basis.
   Source/outcome bins derive from verified metric rules. Missing head labels stay
   absent; an explicit verified UNKNOWN supplies class zero. Existing non-salience
   auxiliaries require their owner's verifier and survive attachment. Unchanged
   rows retain their original objects/order. Native inference receives inputs and
   targets=None, including when training auxiliaries exist.
4. Later action/route changes link an exact prior accepted-lesson receipt within
   comparable scope/structure/defect. Correction followups distinguish explicit
   recurrence, measured nonrecurrence and NOT_MEASURED. Observation time must be
   strictly later, in addition to later append order. These are associated measured
   observations, not causal proof or a promise that a defect stopped forever.

Schemas: bilqis.c06.window-policy/v1; salience-event/v1; salience-window/v1;
teacher-priority-features/v1; priority-teaching/v1; row-salience-binding/v1;
auxiliary-label/v1. All use the bilqis.c06 prefix.

## Proof and independent EGM

`tests.txt`: **74 passed, zero failures/errors/skips** across C06 salience,
history/teacher/auxiliary and native C03/C02 affected owners, using
`/tmp/bamf-c05-tests/bin/python -B scripts/run_tests.py`.
Direct actual-selector comparison checks identical policy, metadata, updated
teacher state and preserved prior JSON from identical teacher/RNG inputs.
The cross-grade witness resolves the selected capability's actual roster grade.

Independent Goldfish `/root/c06_1_goldfish`, pinned Google EGM
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`, accepted the cold interface then
reviewed implementation. Three majors: consuming-time fact/policy signer
revocation, simultaneous followups counted as later effects, independent caller
grade diverging from selected capability. All repaired; targeted re-audit PASS,
no remaining blocker/major. Reviewer inspected source and 14 focused / 74 owner
green receipts; reviewer did not execute tests. PM-2026-10-29-005 enriched and
native Sheet read back before time/grade repairs. Red followup receipt includes
one fixture scope-order setup error alongside the real failing assertion;
both were repaired. Red grade receipt proves missing roster-aware interface.

## Frozen upstream assumptions and remaining requalification

Actual accepted C03 teacher, C02 adapter, A06 policy contracts and C09 scoped
signature registry are reused. Event retention/admission and current rights
claims are signed small protocol fixtures pending accepted A09/B13 custody;
they do not authorize actual learner updates. A05 is now on unified, but this
C02 fixture proof still uses its existing fixture prefix seam. Actual B11 backend,
auxiliary loss masking and serialized disposable MLX integration remain pending.
No production B11 class or alternate optimizer was invented. Reconcile actual
accepted interfaces, repeat affected EGM if behavior drifts, and run real
integration witnesses before completed receipts or issue closure.
