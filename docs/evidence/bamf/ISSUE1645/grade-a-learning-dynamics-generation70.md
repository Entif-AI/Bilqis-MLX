# Grade A learning dynamics on accepted generation 70

Issue #1645 / IPR-0220. This document extends the existing Grade A learning-dynamics
diagnostic to the accepted generation-70 learner. It is a research result, not a
retention qualification, optimizer-policy change, or authorization to run training.
All new numerical work used disposable copies. The accepted aspirant learner was not
mutated, no candidate was admitted, and no `--human-run` command was executed.

## Evidence boundary

The accepted parent is generation 70, manifest
`19d12ad8c8799440faa7757cb7417735540f8a100069a5741dc67bfeb41b0f9b`,
model/checkpoint identity
`b6a836df4f5cad03eb6590b073aa73820474aece7a82c7ccbed550f4a468a27f`,
and retained optimizer step 737. The live pointer and event ledger remained at
SHA-256 `640729092bda4209c2bbe9b6ea147fc6cfdb8a81f6c0984962738cffd04fe864`
and `66a37da56249874552329a49cc1fd328057af77a2458028e89fa776327951cd0`
through the new witnesses.

The controlled six-capability result is
`8424471db294d3d0e16489a5596d9cf2ec9567ae4c3b024806400116101da724`.
It uses actual Factory source construction, B11 loss gradients, B09 participation
authority, the retained AdamW state, and B12 update semantics. Each capability has
six fixed target rows and six separately seeded protected rows. These are
source-bound diagnostic draws, not previously issued lessons or independent exams.
The fixed diagnostic learning rate is 0.00013. Retained beta1=0.88, beta2=0.97,
epsilon=1e-7, weight decay=0.03, row clocks, moments, and parameter values are used.

The ordinary execution-path result is
`fbc7ccafe0492a654b16a655bb60c528b1d68583c7adaba6fa53854a63e98400`.
It uses the same accepted learner and the repository's `execute_selected_visit`
path, intercepts the first candidate update, and raises the diagnostic stop before
candidate admission. Its exact source snapshot is
`b1e1a6038b5870bdf65d7ee02a43c9322ed565f47116baa71f1a433d9787b132`.
The generation-70 cadence projection is independently pinned by freeze manifest
`dfc9d97f42edf18913416a1220a5a1161b832e98b16c37b1c49c58d9c6e6913c`.
The projection covers 1,037 contiguous indexed records through byte 101,200,225.

The first native attempt failed closed because the earlier #1657 cadence freeze
belonged to generation 69. No execution-path measurement was accepted from that
attempt. A read-only freeze of the already-persisted generation-70 v3 projection
then passed the existing cadence verifier before the successful witness ran.

## Six-capability numerical result

The controlled source-bound probe covers all six Grade A capabilities. Positive
loss-direction values mean that a proposed target update is predicted to increase
loss on the separately bound protected rows.

| Capability | Target mean loss | Protected mean loss | Masked gradient norm | Active clocks | Selected identity rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| A.IDENTITY | 0.688846 | 0.683829 | 0.089425 | 183 | 16 |
| A.PARENT | 0.698374 | 0.687746 | 0.093570 | 183 | 16 |
| A.LINK | 0.682867 | 0.679351 | 0.089058 | 183 | 16 |
| A.MEMBER | 0.681182 | 0.686238 | 0.089302 | 192 | 25 |
| A.EDGE | 0.686868 | 0.677339 | 0.085406 | 192 | 25 |
| A.MAPS | 0.681747 | 0.688020 | 0.088459 | 192 | 25 |

The clipping limit is 1.0. None of the six masked gradient norms exceeds 0.094,
so clipping is part of the exact calculation but does not scale these probes.
All six updates have 168 active leaves. Selected-row and equivalent full-mask
AdamW agree to at most 1.46e-11 on the saved state, with exact clock equality.

The 36 pairwise comparisons contain 18 harmful raw negative-gradient directions
and 13 harmful actual AdamW displacements. Nine pairs change sign between the raw
descent direction and the actual optimizer update. Gradient cosine or raw dot
products therefore do not predict the retained optimizer's compatibility reliably.

### PARENT, MAPS, and IDENTITY

| Target -> protected | Raw negative-gradient dot | Actual AdamW dot | Carried-moment contribution | Current-gradient + rounding | Weight decay |
| --- | ---: | ---: | ---: | ---: | ---: |
| IDENTITY -> PARENT | -0.000393855 | -0.000646587 | -0.000502884 | -0.000143703 | -1.56e-10 |
| IDENTITY -> MAPS | +0.000531841 | +0.000595642 | +0.000216050 | +0.000379593 | -1.07e-9 |
| PARENT -> IDENTITY | -0.000458321 | -0.000431114 | -0.000071756 | -0.000359358 | +1.76e-10 |
| PARENT -> MAPS | +0.000140241 | +0.000155911 | +0.000205252 | -0.000049339 | -1.07e-9 |
| MAPS -> IDENTITY | -0.000146472 | -0.000150099 | -0.000088971 | -0.000061129 | +1.76e-10 |
| MAPS -> PARENT | +0.000213426 | -0.000256258 | -0.000521607 | +0.000265349 | -1.56e-10 |

The MAPS -> PARENT pair is the clearest optimizer-history reversal. The raw
negative-gradient direction is harmful to PARENT, while the actual retained-state
AdamW update is beneficial at first order. The carried first-moment term is larger
than the opposing current-gradient term. PARENT -> MAPS and IDENTITY -> MAPS show
the opposite pattern: carried history reinforces a harmful final direction.

Weight decay does not explain these effects. Across all 36 pairs, the sum of the
absolute decay-dot terms is 9.88e-8, versus 0.00994 for carried-moment terms and
0.00792 for current-gradient plus rounding terms. The largest absolute decay dot is
7.30e-9.

## Retained second moments, bias correction, and epsilon

The saved-state moment sensitivity result is
`a6c9290140e34e1a1663fe2f648813ea21f70b8976ae582c89ab8931db890396`.
It reconstructs the selected coordinates in FP64 while preserving the native
clipped gradients, clocks, and decay vector. Maximum per-coordinate analytic
difference from the observed FP32 adaptive displacement is 1.14e-7.
The retained-second-moment percentages below use participating coordinates whose
next second moment is nonzero; coordinates with an exactly zero next second moment
are excluded from that denominator.

| Capability | Mean retained share of next second moment | Coordinates with >=90% retained second moment |
| --- | ---: | ---: |
| A.IDENTITY | 93.10% | 84.38% |
| A.PARENT | 91.75% | 80.82% |
| A.LINK | 92.77% | 82.72% |
| A.MEMBER | 91.53% | 80.38% |
| A.EDGE | 91.60% | 80.27% |
| A.MAPS | 93.79% | 85.54% |

Retained second-moment history dominates most participating coordinates. The
first-moment bias factor is 1.0 to reported precision at these clocks. The
second-moment bias factor ranges from about 1.000000000086 to 1.000006. Bias
correction is therefore included but is not a material source of the observed
pairwise sign changes.

The output-specific epsilon counterfactual changes only the dedicated-readout
partition. Epsilon values 1e-5 and 1e-4 produce zero full-model sign changes across
all 36 pairs. For IDENTITY -> MAPS, the dedicated-readout dot falls from
+5.29e-5 at epsilon 1e-7 to +4.72e-5 and +2.46e-5. PARENT -> MAPS falls from
+4.06e-5 to +3.61e-5 and +1.81e-5. MAPS -> PARENT remains beneficial in the
readout partition, moving from -9.08e-6 to -7.09e-6 and -2.36e-6. The measured
epsilon range attenuates readout effects but does not explain or remove the
full-model PARENT/MAPS/IDENTITY interference pattern.

## Ordinary Factory execution boundary

The native witness does not force every capability through the scheduler. It
records the lawful outcome for each capability and measures a proposed update only
when the real execution path reaches that boundary.

| Capability | Native result | Selection scope | Lesson/update evidence |
| --- | --- | --- | --- |
| A.EDGE | PERFECT_TARGET_SKIPPED | natural selection | Issued parent preflight only; no lesson update |
| A.IDENTITY | CAPTURED | other capabilities diagnostically held | 32 Factory rows; 26 direct IDENTITY, 6 retention support |
| A.PARENT | NO_ADMISSIBLE_TEACHING | other capabilities diagnostically held | No update manufactured |
| A.LINK | CAPTURED | other capabilities diagnostically held | 32 Factory rows; 20 direct LINK, 12 retention support across all six capabilities |
| A.MEMBER | CAPTURED | other capabilities diagnostically held | 33 Factory rows; 26 direct, 6 retention support, 1 fresh support |
| A.MAPS | NO_ADMISSIBLE_TEACHING | other capabilities diagnostically held | No update manufactured |

The captured policies use their actual selected learning rates: 8e-5 for IDENTITY,
3e-4 for LINK, and 8e-5 for MEMBER. Their masked gradient norms are 0.03801,
0.04274, and 0.03747, again below the clipping limit. All three stop before
candidate admission. The natural EDGE path stops earlier because the issued parent
preflight is perfect.

The IDENTITY mixed lesson independently reproduces the important MAPS direction:
its raw negative-gradient dot against the protected MAPS probe is +0.000128655 and
its actual AdamW dot is +0.000163227. Against PARENT, the same mixed lesson is
beneficial at first order (-0.000430137 actual AdamW dot). This is an ordinary
Factory execution-path observation, not the balanced six-row target probe.

The prepared native rows carry observed source digests, Factory source-family and
episode identities, source and optimizer-step seeds, and validated training
coordinates. Per-row `authoritative_source_sha256` is absent on this ordinary path,
and mentor supervision is absent. The diagnostic records those facts as null or
ABSENT rather than manufacturing stronger provenance. Source authority remains
bound at the accepted Factory release and source-authority layer.

Generation 70 also has authentic historical rejected PARENT, MAPS, and EDGE visits
against the same retained parent at step 737. Their teacher visits, selected
policies, source-binding digests, realized support counts, terminal decisions, and
C05 evidence survive. Exact delivered row objects and gradients do not. The
repository has no authenticated contract that recreates the exact old mixed batch
from those receipts, so this diagnostic does not relabel regenerated rows as the
historical lesson.

## Forward-loss validation

The forward-only finite-loss replay is a controlled check on the saved protected
rows. It reconstructs each proposed AdamW displacement, verifies exact native
displacement replay, and measures the protected losses before and after the
displacement. It does not run new gradients, assessments, admissions, or learner
publication. The result SHA-256 is
`e0c7e8181a1631fd9707e7b6d6fdcffde68f0b7e1e4be65dec59c46d72a24b56`.
All six native displacements replay with zero maximum error. Observed forward-loss
direction agrees with the first-order prediction in 35 of 36 pairs. The maximum
absolute Taylor residual is 0.000115254 and the mean absolute residual is
0.000030312.

All six PARENT/MAPS/IDENTITY directions agree in sign:

| Target -> protected | Predicted loss change | Observed loss change | Taylor residual |
| --- | ---: | ---: | ---: |
| IDENTITY -> PARENT | -0.000646587 | -0.000623852 | +0.000022735 |
| IDENTITY -> MAPS | +0.000595642 | +0.000589053 | -0.000006589 |
| PARENT -> IDENTITY | -0.000431114 | -0.000450522 | -0.000019408 |
| PARENT -> MAPS | +0.000155911 | +0.000177622 | +0.000021710 |
| MAPS -> IDENTITY | -0.000150099 | -0.000129372 | +0.000020728 |
| MAPS -> PARENT | -0.000256258 | -0.000227670 | +0.000028589 |

The only sign disagreement in the 36-pair matrix is MEMBER -> IDENTITY, where the
first-order value is -1.75e-5 and the observed mean change is +2.03e-6. This small
near-zero reversal is consistent with a local Taylor approximation limit. It does
not affect the PARENT/MAPS/IDENTITY conclusion.

## Execution economics and unavailable counters

The six-capability protected numerical capture took 89.87 seconds and peaked at
about 3.72 GB MLX allocation and 3.99 GB process RSS. The three native captured
lesson boundaries took 4.83 seconds (IDENTITY), 4.45 seconds (LINK), and 4.36
seconds (MEMBER). The natural EDGE perfect-target preflight took 0.36 seconds.
The complete detached native process also includes cloning, cadence verification,
context construction, scheduler work, and the two no-admissible decisions; it is
not an ordinary visit-throughput measurement.

The latest authenticated training observation preserves complete visit times for
visits 13-19: 15.676, 21.289, 18.455, 17.844, 0.805, 13.704, and 19.444 seconds.
It preserves one accepted A.LINK candidate, five rejected candidates, and one
acquisition-rearm event. The accepted learner remains at optimizer step 737. The
rejected candidates reached attempted step 753 but retained zero of those steps.
The enclosing five-minute run-stop receipt records 17 visits in 310.362 seconds,
with one accepted and 16 rejected. This is 3.29 terminal visits per minute. It is
not an evaluation-call rate.

Candidate-evaluation call counts, evaluation-only latency, evaluation-only
throughput, and cache-hit counts are not persisted in the surviving generation-70,
R2, R3, R4, or R5 evidence used here. Null cache fields are not zero counts.
Evaluated-capability counts, scheduler-selection invocations, terminal decisions,
and attempted optimizer steps are different quantities and are not substituted.
This diagnostic therefore cannot produce an honest evaluation-calls-per-second or
cache-reuse rate retrospectively.

The diagnostic overhead is measured separately from training. The protected probe
took 89.87 seconds. The CPU-only moment analysis took 28.60 seconds. The finite-loss
replay took 141.79 seconds, with about 2.29 GB peak MLX allocation and 2.39 GB peak
process RSS. The native detached process ran for about 78 seconds end to end,
including clone and cadence work; its captured lesson boundaries account for about
14 seconds of that total. These are research costs outside ordinary training. No
production slowdown is inferred from them.

## Scientific interpretation

The evidence supports optimizer-state interference as a real mechanism. Nine of 36
pairs change compatibility sign between raw descent and the actual AdamW
displacement. The retained first and second moments are large enough to change the
direction and scale of proposed updates. MAPS -> PARENT is a direct sign-reversal
example, while PARENT -> MAPS and IDENTITY -> MAPS remain harmful after the exact
optimizer transformation.

The evidence rules out clipping and weight decay as material explanations for this
specific one-step matrix. Clipping is inactive in every controlled probe. Weight
decay is orders of magnitude smaller than the adaptive terms. The tested
output-specific epsilon changes attenuate the readout partition but do not reverse
any full-model pair sign.

The evidence does not show that optimizer interference is the sole cause of the
retention failures. Historical generation-70 visits include target ties and target
failures that stop before broad protection can decide the outcome. Current
PARENT/MAPS teaching is not admissible under the diagnostic restriction, and EDGE
is currently perfect at parent preflight. Instructional sufficiency, scheduler
state, mixed rehearsal composition, and optimizer history remain viable interacting
mechanisms.

This work also does not establish retained learning. The measured displacements are
one-step proposals or pre-admission captures. The controlling outcome remains
independently retained competence per wall-clock minute on a legitimately retained
learner.

## Next matched experiment

The highest-value next experiment is a matched disposable **optimizer-history
ablation pilot**. It screens whether the combined retained AdamW moment state has a
large immediate effect under the exact generation-70 condition without changing
model architecture or C05. A single matched pair is not a general falsification of
optimizer history as a learning mechanism.

Both arms start from accepted generation 70, manifest `19d12ad...`, optimizer step
737, run seed 543, the same model weights, Factory release, source authority,
cadence, curriculum, candidate horizon, assessment identities, and wall-clock
budget. The control arm uses the exact retained AdamW state. In the treatment arm,
the first authorized candidate update is prepared normally on a disposable copy;
immediately before that update is calculated, the retained first and second moments
are zeroed only on the exact coordinates selected by that update's participation
mask. Weights, row clocks, hyperparameters, participation authority, and the
weight-decay law stay unchanged. Later scheduler or exposure divergence is recorded
as a downstream consequence of the intervention rather than artificially corrected.
Because the intervention changes first and second moments together, this pilot tests
combined optimizer history and cannot by itself attribute an effect to one moment
family. It is a research treatment and requires explicit human authorization before
execution.

Use the existing independently scored Grade A fixed assessment at the same earned
complexity before and after each arm. Keep C05, rollback, acceptance, and retained
learner publication rules unchanged. Run one neural lane. A practical first budget
is one historical five-minute session per arm plus the matched assessments; prior
five-to-six-minute runs show that this is enough to exercise several terminal
visits without claiming a plateau. Use the existing one-lane resource guards: 12
GiB MLX budget, 18 GiB process-RSS guard, and at least 25% host memory free. The
expected neural-training cost is about ten minutes total plus setup and the matched
before/after assessments. Persist actual candidate-evaluation call boundaries,
elapsed time, cache hits/misses, delivered exposure, terminal decisions, retained
steps, and realized lesson allocation prospectively.

The primary outcome is independently retained Grade A competence gained per
wall-clock minute. Secondary outcomes are PARENT/MAPS/IDENTITY score changes,
protected-regression frequency, terminal-decision mix, and evaluation throughput.
Pre-register the pilot's large-effect hypothesis as: after equal five-minute wall
time, the treatment yields at least one additional net independently retained
correct answer on the 72-item fixed assessment (1/72 assessment resolution) versus
control, with no newly lost protected-capability answer. Meeting that threshold is
a pilot-positive signal that combined optimizer history is a useful causal lever
worth replicating. Failing to meet it, or causing a protected regression, falsifies
only that **large immediate effect in this exact generation-70 five-minute
condition**; it does not falsify smaller effects, longer-horizon effects, or
optimizer history in general. Evaluation throughput and cache behavior are reported
as costs, not converted into an invented slowdown gate. This pilot has strong
discriminating power for a one-item-or-larger immediate combined-history effect
because the starting weights, clocks, source authority, curriculum, C05, assessment,
seed, and wall time are matched. Its power is limited for subtler effects and it
cannot distinguish first-moment from second-moment causality. A pilot-positive result
would still require matched replication before any production learning-strategy
adoption.

Do not launch this experiment without explicit human authorization.
