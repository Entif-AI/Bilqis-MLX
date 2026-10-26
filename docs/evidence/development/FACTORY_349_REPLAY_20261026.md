# Factory 349 selective replay receipt

Date: 2026-10-26

Source lineage: `349-bouta-tree-fitty`

Target lineage: post-#324 Factory stack, isolated on
`codex/337-replay-349-20261026`.

The frozen #324 v3 control is not mutated by this replay. The replay treats the
349 branch as implementation evidence, not as a merge base or authority to
replace current Factory-v2, #333 observation, or promotion contracts.

Disposition meanings:

- `APPLY`: behavior can be replayed directly against the current owner.
- `ADAPT`: useful behavior survives, but its historical implementation or
  authority boundary does not.
- `ALREADY_EQUIVALENT`: current Factory already owns the behavior.
- `SUPERSEDED`: a later/current mechanism replaces the historical one.
- `DEFER`: potentially useful, but requires a new explicit policy/experiment
  boundary before it may affect live selection.
- `REJECT`: conflicts with current authority and is not replayed.

## Teacher and strategy-control ledger

| 349 commit | Disposition | Current replay result |
| --- | --- | --- |
| `200023f` escape rejection-only novelty loops | ALREADY_EQUIVALENT | Current capability-level rejection pressure already suppresses novelty loops. |
| `fa52630` rotate rejected teaching evidence | ALREADY_EQUIVALENT | Fresh source and weakness/retention support rotation already survive in current source selection and visit owners. |
| `3c59208` capability-local teacher/control epoch | ADAPT | Replayed the useful consecutive-interference semantics into the current capability/scope evidence owner. Geometry-specific historical assumptions were not imported. |
| `08094eb` bounded active strategies and promotion floor | ADAPT | Replayed a <=16 effective-strategy active bench with <=8 proven incumbents and rotating challengers. Did not replay the historical promotion-floor change. |
| `31389c3` fresh active strategy bench | ADAPT | Context containing only dormant/failed strategies falls back to a fresh active challenger instead of dead-ending. |
| `9662bd6` credit realized lesson delivery | ADAPT | Added `bilqis.teacher-realized-action/v1` identity from actual delivered controls, support, guidance and enrichment. #333 remains the canonical raw proposal/delivery/outcome evidence owner. |
| `13e5252` exploit retained strategy evidence | ADAPT | A retained incumbent is preferred immediately, with bounded periodic exploration under rejection pressure. |
| `7ca5b08` retire stale same-student policies | SUPERSEDED | The historical any-rejection retirement rule is not replayed. The corrected no-target-gain rule from `4246f95` is used instead. |
| `bb7a5ed` distinguish learner-state regions | ALREADY_EQUIVALENT | Current #333 observation/student-region evidence already distinguishes grade score shape, mastery debt and related state bands. |
| `4246f95` distinguish target inertia from interference | ADAPT | Candidate-step throttling now uses consecutive interference failures; no-target-gain breaks that streak. Same-student retirement requires four consecutive `NO_MEASURABLE_TARGET_GAIN` outcomes and resets on a new student checkpoint. |
| `ddf21e7` shadow rung scheduler | ADAPT | Restored the versioned 2/4/8/16 multi-fidelity ladder through current Factory visits and #333 observation envelopes. It adds target-probe inference for calibration but does not stop real candidates. |
| `96e0ba0` shadow stopping horizon | ADAPT | Restored the calibrated v2 rule: no stop recommendation before step 8; a step-8 recommendation requires no prior positive target gain. The shadow review and activation receipt are projected through #333. |
| `ee64915` bounded vNext canary authority | ADAPT | Restored bounded 1-in-4 live selection authority without restoring the historical parallel outcome store. Only evidence-backed existing executable policies inside the current post-retirement active set may override the current selector; underpowered cases fall back and novel learned parameters remain shadow-only. |

Critical prerequisite `e7f811e` is likewise SUPERSEDED: current #333
proposal -> delivery -> outcome capture is the passive observation contract.

The replayed selector has policy identity
`bilqis.mlx.teacher-selection/349-replay-v2` when the bounded vNext canary owns
the choice; the ordinary contextual path retains its existing v1 identity. The
legacy/current selector is still computed first and retained as counterfactual
metadata when vNext overrides it. #333 remains the canonical proposal ->
delivery -> outcome -> cost authority. The causal evidence schema remains v1
because compatible historical evidence is not being rewritten.

## Retention, scheduling and promotion ledger

| 349 commit | Disposition | Current replay result |
| --- | --- | --- |
| `39db37f` align teaching with fresh transfer | ALREADY_EQUIVALENT | Current fresh support and source-scored transfer evidence already own this behavior. |
| `a0970f7` respect zero weakness-replay capacity | ALREADY_EQUIVALENT | Current source lesson selection yields reserved retention/support capacity correctly. |
| `d89b139` cap nongating B effort at 20% | SUPERSEDED | Current generic `DebtCadencePolicy` bounds whole-grade debt turns without hard-coding B/C identity. |
| `d22564d` bounded full Grade-B runs | ALREADY_EQUIVALENT | Current debt cadence enters one canonical bounded-debt-grade pass after no more than four non-debt turns. |
| `5c5a0ec` preserve promotion-sweep capacity | ALREADY_EQUIVALENT | Current promotion sweep freezes the trigger vector and replaces only the freshly rescored semantic. |
| `d89bc02` bind promotion retries to learning state | APPLY | A failed promotion sweep is durably bound to the exact student checkpoint SHA plus exact introduced semantic scope. Fresh cohort flux alone cannot re-arm the unchanged student; retained learning or scope expansion can. Legacy receipts migrate neural-inertly to the conservative already-attempted state. |
| `768e36e` promotion-sweep 92/87 hysteresis | APPLY | Promotion sweeps now require >=92% fresh introduced-grade mean to enter and continue down through exactly 87%, aborting only below 87%. This preserves the stitched semantic-sweep mechanism while adding the deliberately validated noise buffer. |

These scheduler/promotion changes apply only to the post-#324 successor. The
frozen #324 v3 executable and manifest remain unchanged.

## Operator evidence and authority correction

The initial replay classified vNext, shadow multi-fidelity and hysteresis too
conservatively because the current README/ADR projection had lost the most recent
operator decisions. Contemporaneous session minutes recovered the causal sequence:

- same-student cohort flux repeatedly re-armed promotion sweeps until `d89bc02`;
- the 2/4/8/16 ladder was calibrated so step-8 shadow stopping replay saved about
  25% of candidate steps with one false kill in 125 stop recommendations;
- `ee64915` deliberately granted bounded 1-in-4 vNext canary selection authority;
- promotion replay showed the old 90% hair-trigger converting cohort variance into
  wasted sweeps, leading to the user-approved 92/87 hysteresis in `768e36e`.

The human operator additionally reports hours of live use with the vNext/shadow
lineage sustaining lesson retention above 10%, versus roughly 2-3% before these
changes. That report is accepted as operator evidence for the replay decision; it
is not misrepresented here as a newly reproduced controlled experiment.

## Dashboard and operator ledger

| 349 commit | Disposition | Current replay result |
| --- | --- | --- |
| `51f8702` preserve active champions | APPLY | Removed the six-champion display truncation; every active capability champion remains visible. |
| `c0a8a4c` numeric-scope milestones | ADAPT | Historical config/profile parsing is not current Factory authority. Scope projection should come from the executable release/semantic graph before this display is reintroduced. |
| `c9ed590` compact integer-root scope | DEFER | Cosmetic follow-on to the current-authority numeric-scope projection above. |
| `41c8b6c` retentions/hour | ADAPT | Replayed as command-local cumulative `R/H`. |
| `79efeaf` stable steps/minute | ADAPT | Replayed as cumulative command-local `ST/M`, eliminating refresh-window jitter. |
| `0fa95da` retention percentage | ADAPT | Replayed as `RTN%` over command-local visits. |
| `728f91a` whole-school GREW | ADAPT | Replayed across measured active capabilities, including capabilities withheld for stagnation; missing measurements are not fabricated. |
| `e7f811e` teacher policy health display | ADAPT | Restored the SOUP & TEACHER `HEALTH` column with the historical `PRODUCTIVE / EXPLORE / LOW-YIELD / EXHAUSTED` vocabulary. The current dashboard derives it read-only from each policy's capability/phase visit outcomes, so existing journals gain the display without restoring the historical parallel outcome-model authority. |
| `7fef150` compact dashboard presentation | DEFER | Pure presentation compaction can follow after the final metric set stabilizes. |

Prerequisite `aac2a0b` command-local counter reset is included in the dashboard
replay. Historical numeric-ceiling/profile migrations `b4397c4` and
`80a49d0` are SUPERSEDED by current declarative Factory scope ownership.

## Verification

- Dashboard: 53 presentation tests pass.
- Policy-health follow-up: 55 school-telemetry tests pass, and a one-shot dashboard
  render against the operator's already-running `microspenics-349-replay` journal
  displays `HEALTH` with live `LOW-YIELD`, `PRODUCTIVE`, and `EXPLORE`
  classifications without restarting or mutating the trainer.
- Curriculum/promotion: 69 staged-school and school tests pass, including 92% entry,
  87% continuation and same-student/scope retry regressions.
- Teacher learning/control: 56 tests pass, including five focused vNext/multi-fidelity
  replay tests and the existing learning-experiment suite.
- #333 observation/capture: 12 focused capture/replay tests pass.
- Architecture, module-size, documentation, error-control and code-smell
  baseline checks pass with zero new baseline-relative debt.
- No neural training was initiated by this replay.
- No direct merge or cherry-pick train from `349-bouta-tree-fitty` was used.
- No historical parallel `teacher_outcomes`/proposal evidence authority was
  restored beside current Factory/#333. The bounded canary is a mode of the
  current selector and its evidence is carried by the current observation path.
