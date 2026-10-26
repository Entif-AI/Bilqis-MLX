# Teacher vNext portable contract v1

Issue: [#321](https://github.com/Entif-AI/Bilqis-MLX/issues/321)

## Purpose

Teacher vNext separates **truth/admission authority** from **proposal intelligence**.
The teacher may estimate which pedagogical intervention is likely to produce durable
learning and may recommend how much disposable compute to spend testing it. It may not
define source truth, waive retention, mutate the retained student on a rejected trial,
or turn its own confidence into promotion/qualification authority.

This document defines the architecture-neutral evidence and shadow-control contract
shared by the current Prometheus teacher and the divergent developmental teacher in
#130. Shared implementation code is optional. Conformance to these semantics is not.

## Portable candidate observation

Schema: `bilqis.teacher-outcome-observation/v1`.

One observation binds:

1. a coarse `StudentRegion` known before the intervention;
2. the proposed action known before lesson construction;
3. exact realized-delivery evidence retained separately by the owning runtime;
4. target/protected/cost outcomes from the authoritative retention evaluation;
5. optional shadow multi-fidelity recommendations;
6. exact provenance in the ordinary event/run ledger.

The portable observation records these outcome dimensions separately:

- retained versus rejected;
- rejection reason;
- target-correct delta;
- protected-net delta;
- worst protected-capability loss;
- attempted optimizer steps;
- retained optimizer steps;
- wall-clock candidate cost.

Do not collapse these dimensions into one opaque reward when training or evaluating a
future proposer. Existing reward signals may remain compatibility surfaces.

## StudentRegion

Schema: `bilqis.teacher-student-region/v1`.

The region is intentionally **coarser than checkpoint identity**. It currently contains:

- capability;
- phase;
- lesson grade;
- curriculum/geometry scope;
- numeric scope where applicable;
- capability-score band;
- grade-score band;
- rejection-pressure band;
- attempts-since-retention band;
- mastery-debt band.

Exact student/checkpoint SHA, cohort SHA, batch SHA, source-cohort SHA, and generated
lesson identity are forbidden as region keys. They remain provenance in their owning
receipts. This prevents the predictor from manufacturing a new one-sample context for
every batch or checkpoint.

The architecture-neutral fixture is:

`bilqis_mlx/learning/fixtures/teacher_vnext_conformance_v1.json`

Both teacher architectures must be able to project equivalent learner/action/outcome
semantics through this fixture or an explicitly versioned successor.

## Outcome model

State schema: `bilqis.teacher-outcome-model/v1`.

The v1 implementation deliberately uses interpretable sufficient statistics rather
than a neural meta-model. For each region × action context it maintains:

- trials and retained trials;
- empirical retention probability plus a Wilson interval;
- target-delta mean and standard error;
- protected-net-delta mean and standard error;
- mean worst protected loss;
- attempted/retained optimizer cost;
- wall-clock cost and standard error;
- rejection-reason distribution.

An unseen action is uncertain, not bad: its retention prediction is an uninformative
`0.5 [0, 1]` until evidence arrives. Calibration is measured through prediction/outcome
pairs using the Brier score in teacher-health telemetry.

Exact realized-action receipts remain forensic subrecords of the current teacher.
They are not the primary predictive key because their exact post-construction identity
is not knowable when the next action is being selected.

## Teacher health

Health is an operator diagnosis, never a retention or promotion gate. The v1 states are:

- `UNCERTAIN_EXPLORING`;
- `PRODUCTIVE`;
- `LOW_YIELD`;
- `SEARCH_NEIGHBORHOOD_EXHAUSTED`.

The current default policy is versioned in code and may be replaced by evidence. It
exists to make a long zero-yield search visible, not to decree a universal optimum
retention percentage.

Telemetry includes:

- candidate retention rate;
- retained/attempted optimizer updates;
- visits per retention;
- optimizer steps per retention;
- wall seconds per retention;
- Brier calibration score;
- proposal-family allocation;
- shadow early-stop recommendations;
- shadow false kills/false continues;
- hypothetical shadow steps saved.

## Multi-fidelity shadow controller

Schema: `bilqis.teacher-multifidelity-shadow/v1`.

The initial ladder is `2 -> 4 -> 8 -> 16` optimizer steps, clipped to the actual
candidate horizon. At non-final rungs the current runtime performs a source-bound
target probe against the same parent predictions. **It does not stop the candidate.**

The shadow record reports:

- first rung at which it would have stopped;
- whether the full candidate ultimately retained;
- false-kill and false-continue status;
- actual steps spent;
- hypothetical steps spent/saved if active;
- `actual_authority_changed: false`.

Intermediate probes are experimental screening evidence only. They cannot retain a
candidate, alter AdamW, promote a grade, or certify qualification.

## Early-stop activation gate

Schema: `bilqis.teacher-multifidelity-activation/v1`.

Active early termination is intentionally **not enabled by this v1 implementation**.
The runtime computes a versioned qualification receipt from recent shadow reviews.
Qualification requires sufficient support, bounded false-kill rate, and material mean
compute savings. Even a `QUALIFIED` shadow receipt does not itself switch authority.
Turning early stopping on requires a separately reviewed policy epoch after human-run
evidence is available.

## Proposal families

Teacher vNext separates the *way a proposal is generated* from the exact parameter
vector:

- `INCUMBENT_REPLAY`: reuse a retained contextual policy;
- `LOCAL_INCUMBENT_MUTATION`: change one bounded knob near a retained incumbent;
- `NEIGHBOR_TRANSFER`: reuse retained evidence from the same capability/scope in a
  neighboring phase;
- `GLOBAL_CHALLENGER`: sample the bounded active archive where local evidence is weak;
- `LEARNED_LOCAL_DISTRIBUTION`: sample from the empirically productive local action
  distribution once that distribution has enough observations.

Local mutation and learned-distribution proposals are shadow-only in v1. They may
describe interventions that are not already one of the 512 historical strategy IDs,
but they do not mutate that historical archive.

## Shadow acquisition

Schema: `bilqis.teacher-proposal-shadow/v1`.

The v1 acquisition controller uses Thompson-style retention sampling plus explicit
target gain, protected risk, candidate cost, and uncertainty. It ranks a bounded set
of proposal-family candidates and records the winner. The ranking is diagnostic only:
`actual_authority_changed` is always false.

This replaces the conceptual need for an arbitrary enormous novelty score while
retaining principled exploration through posterior uncertainty.

## Learned local proposal distribution

Schema: `bilqis.teacher-learned-distribution/v1`.

Once a region has enough outcome observations and retained examples, v1 fits a
cost/risk-weighted local distribution over observed productive interventions. Numeric
learning rate is modeled in log space and may be sampled between historical grid
values; categorical teaching geometry remains constrained to legal modes. The result
is still a proposal to the deterministic lesson builder, never source truth.

This is the first concrete step from "choose a book from the shelf" toward "write the
next page." It remains shadow-only until its predictions and interventions are
validated against human-run outcomes.

## Authority invariants

Nothing in Teacher vNext v1 changes these contracts:

- source/oracle gold remains authoritative;
- full candidate retention remains final student/AdamW admission authority;
- rejected trajectories own no retained state;
- promotion and qualification ignore teacher confidence;
- SEALED evaluation remains inaccessible to teacher proposal logic;
- the human owns actual neural-run initiation/resume;
- historical strategy and realized-action provenance is preserved;
- the current live process is never hot-mutated by source changes.

## Porting to #130

The developmental teacher may use a different estimator, state store, proposal engine,
or runtime. It must still prove:

1. an equivalent anti-overfragmented StudentRegion projection;
2. separate retention/target/protected/cost evidence;
3. uncertainty/calibration accounting;
4. the same shadow-versus-authority boundary for multi-fidelity decisions;
5. proposal-family and fallback provenance;
6. final retention as the only durable candidate-admission authority;
7. compatibility with the architecture-neutral conformance fixture.

If later evidence changes these semantics, version the contract and fixture rather than
silently letting Prometheus and #130 drift apart.
