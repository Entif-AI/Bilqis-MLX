# Grade A learning dynamics: authenticated one-step diagnosis

Issue #1645 / IPR-0220. This is a diagnostic, not a retention qualification or
authorization to change the training strategy. All optimizer calculations use
disposable copies; no candidate is admitted or published. No GUI work is in scope.

## Evidence and method

The controlled witness uses the authenticated generation 69, optimizer step 729
retained checkpoint. The source checkout was b186d74171092571b05be94e257a8d296a3114fb
plus the diagnostic files, bound by snapshot
584e92fb412c572f31c37d2c45b9b15ecb9380f98db2697b0d3dfecac2601842.
Its result SHA-256 is
35eb6cf74fbd794c9e1d370c187f899fe16b1993055f51487aa6666eaa5f6213.
The detached receipt records PASS and source_mutated=false. Raw tensor artifacts,
lesson coordinates and local custody remain with the operator.

The v1.0.0 behavioral reference is a990685555cd9d5171691167ab32645a6a2835ca;
the designated Factory oracle was authenticated at d84d2ab9e2d79817c131ef7e0d4ec0d574e57b32.
The historical delivery implementation distinguishes source lessons, weakness targets,
preservation and retention support. The new witness measures actual B11 loss gradients
on six predetermined source-bound target rows and six separately drawn protected
rows per Grade A capability (72 total). These are controlled diagnostic draws,
not independently issued exams or the historical delivered mixed lessons.

B09 participation authority supplies the masks; B12 supplies the actual proposed
AdamW displacement. The fixed learning rate is 0.00013, a value observed in the
manual run, not a selected treatment. Other optimizer hyperparameters are retained.
The clipping limit is 1; the observed norms are below it. An independent
full-mask calculation agrees with the selected-row path: parameter maximum absolute
error <= 7.28e-12, first moment <= 1.46e-11, second moment <= 3.56e-15,
clock equality and frozen-coordinate equality exact. A focused regression exercises
active clipping and momentum reversal. Reanalysis of the saved tensors after
vectorizing the matrix calculation agrees on all 2,304 scalar measurements
(maximum absolute difference 2.75e-15, 26.65 seconds). No neural rerun is needed.

## First-order predicted loss change

Rows are target gradient draws; columns are the separate protected gradient draws.
Values below are the native displacement dot product multiplied by 1,000,000.
Positive means a predicted increase in protected loss. This is a local Taylor
prediction, not a measured post-update accuracy or retained-competence change.

| Target / protected | IDENTITY | PARENT | LINK | MEMBER | EDGE | MAPS |
|---|---:|---:|---:|---:|---:|---:|
| IDENTITY | 515.086 | 598.455 | -230.657 | -83.442 | -91.138 | 180.906 |
| PARENT | 322.423 | 351.237 | 72.806 | 122.541 | -25.035 | 542.846 |
| LINK | 429.015 | 269.106 | -383.075 | 520.221 | 127.309 | 341.391 |
| MEMBER | 721.120 | -502.798 | -366.834 | 540.399 | -400.015 | 686.694 |
| EDGE | 885.777 | -218.511 | -422.926 | 462.034 | 108.380 | 935.108 |
| MAPS | 109.747 | 570.812 | -250.425 | 190.508 | -83.452 | 427.327 |

24 of 36 predictions are positive, including five of six same-capability pairs.
Eight of the 19 pairs with positive raw-gradient cosine (compatible plain
negative-gradient directions) predict increased loss after native AdamW.

For PARENT -> MAPS, the raw cosine is +0.01349 and actual-displacement dot is
+0.000542846. The carried first-moment contribution is +0.000617893;
the current-gradient contribution plus rounding is -0.0000750493.
For PARENT -> IDENTITY, the corresponding values are +0.06116,
+0.000322423, +0.000630974 and -0.000308553. Both cases support a concrete
momentum-driven interference hypothesis, not a causal verdict on full visits.

The dedicated-readout epsilon counterfactual keeps all other leaves unchanged.
The readout.output attention projection participates in these probes; the control
and control-bias leaves are frozen. The tied identity bank is not altered by the
epsilon counterfactual. Epsilon 1e-4 changes the positive-pair count to 25/36,
versus 24/36 at the retained epsilon, and reduces the predicted harm in only 11
of the original 24 positive pairs. PARENT -> MAPS decreases to +0.000501752
but PARENT -> IDENTITY increases to +0.000359459. Other shared parameters,
including nonselected readout components, account for much of the interference.
This does not support treating output-only epsilon as a sufficient standalone fix.

## Manual-run binding and costs

The latest authenticated rejection suffix contains 936 attempted steps over
906.814 seconds (61.9311 attempted steps/minute), zero retained steps and 68
rejections: 37 no measurable target gain, 27 target baseline regressions, and
4 protected capability regressions. The stop receipt count matches; an explicit
launch identity is absent. Hence the actual training executable and exact
historical correction activation are not established by branch ancestry.
All 68 visits selected nonzero distillation, but delivered zero guided optimizer
steps and zero fragile-preservation rows. There were 4,680 retention-support
rows, 688 fresh-support rows and no delivered weakness targets. This is consistent
with the prior zero-retention R4 evidence; R4's 25/72 independent coverage is not
a full independent exam. The new diagnosis does not supersede R4/R5 custody.

The controlled witness took 212.507 seconds, with 3.724 GB peak MLX allocation
and a 12 GiB MLX limit. Per-capability gradient and optimizer phases took
7.71-11.91 seconds; matrix processing is offline. Observed matched manual visit
timing covers only six rows (p50 14.979 s, p95 16.790 s). There are no observed
assessment timings in that suffix. Actual candidate-evaluation counts, cache
reuse, evaluation throughput/latency, independent competence gain/minute and
process-specific swap are unavailable. The historical 66.0805 attempted
optimizer steps/minute baseline is not an evaluation-throughput baseline.
No production timing change is claimed; the diagnostic is outside training.

## Blocked native selected-lesson evidence and review

The natural selected mixed-lesson witness must use the official cadence projection.
On a disposable relocated copy the projection must be rebuilt. That rebuild
exposed a live-versus-historical bundle accessor mismatch: the authenticated
historical bundle carries optimizer_step in its manifest, not retained tensors.
The narrow compatibility correction preserves the same rejection authority,
receipt, generation and optimizer-step validation. Focused legacy and portable
rejection tests pass. The next authentic replay reached a missing generation-6
legacy rejection authority object, absent in both the source data plane and
disposable copies. It stopped before selection. No authority is reconstructed
from the event, no check is bypassed, and no mixed-lesson witness is claimed.

To reproduce the controlled diagnostic on operator-authorized custody:
python3 -B -m scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics RUN PLANE NEW_DESTINATION
The companion native_lesson_dynamics command requires --protected pointing at
the controlled result and complete authenticated historical custody. Both
commands use an isolated copy and a bounded memory limit. The native witness
must remain fail-closed until that custody is restored.

The next evidence-dependent question is whether the interference persists in
authentic mixed delivery and whether the proposed loss changes predict actual
local loss changes. Architectural attainability and independent generalization
remain unresolved. No new neural treatment is authorized by this report.
Independent EGM and the aggregate integration prerequisite remain outstanding.
