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
| `ddf21e7` shadow rung scheduler | DEFER | May be rederived offline from #333 replay evidence. It does not receive live selection authority in this replay. |
| `96e0ba0` shadow stopping horizon | DEFER | Same boundary as `ddf21e7`; requires a separate measured experiment before live authority. |
| `ee64915` bounded vNext canary authority | REJECT | Would reintroduce a parallel control/outcome authority beside current Factory/#333. No live canary authority is replayed. |

Critical prerequisite `e7f811e` is likewise SUPERSEDED: current #333
proposal -> delivery -> outcome capture is the passive observation contract.

The replayed selector has an independent policy identity,
`bilqis.mlx.teacher-selection/349-replay-v1`, carried in selection metadata,
#333 proposal receipts and visit events. The causal evidence schema remains v1
because compatible historical evidence is not being rewritten.

## Retention, scheduling and promotion ledger

| 349 commit | Disposition | Current replay result |
| --- | --- | --- |
| `39db37f` align teaching with fresh transfer | ALREADY_EQUIVALENT | Current fresh support and source-scored transfer evidence already own this behavior. |
| `a0970f7` respect zero weakness-replay capacity | ALREADY_EQUIVALENT | Current source lesson selection yields reserved retention/support capacity correctly. |
| `d89b139` cap nongating B effort at 20% | SUPERSEDED | Current generic `DebtCadencePolicy` bounds whole-grade debt turns without hard-coding B/C identity. |
| `d22564d` bounded full Grade-B runs | ALREADY_EQUIVALENT | Current debt cadence enters one canonical bounded-debt-grade pass after no more than four non-debt turns. |
| `5c5a0ec` preserve promotion-sweep capacity | ALREADY_EQUIVALENT | Current promotion sweep freezes the trigger vector and replaces only the freshly rescored semantic. |
| `d89bc02` bind promotion retries to learning state | DEFER | Current ADR explicitly allows a later fresh >90% assessment to retry. A same-student retry latch would be a new promotion policy and must be versioned deliberately. |
| `768e36e` promotion-sweep 92/87 hysteresis | DEFER | Conflicts with current ADR-084/093 authority: strict >90% entry and >=90% continuation. Not silently imported. |

No scheduler/promotion threshold change in this replay alters #324's frozen
evaluation criterion.

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
| `7fef150` compact dashboard presentation | DEFER | Pure presentation compaction can follow after the final metric set stabilizes. |

Prerequisite `aac2a0b` command-local counter reset is included in the dashboard
replay. Historical numeric-ceiling/profile migrations `b4397c4` and
`80a49d0` are SUPERSEDED by current declarative Factory scope ownership.

## Verification

- Dashboard: 53 presentation tests pass.
- Teacher learning/control: 51 learning-experiment tests pass.
- #333 observation/capture: 17 focused tests pass, including capture-enabled vs
  capture-disabled learner/AdamW behavioral equivalence.
- Architecture, module-size, documentation, error-control and code-smell
  baseline checks pass with zero new baseline-relative debt.
- No neural training was initiated by this replay.
- No direct merge or cherry-pick train from `349-bouta-tree-fitty` was used.
- No historical `teacher_outcomes`, `teacher_proposals` or live canary owner
  was restored beside current Factory/#333.
