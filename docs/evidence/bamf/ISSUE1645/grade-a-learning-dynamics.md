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

## Mechanism decomposition on the saved optimizer state

The second-moment sensitivity uses the original result, exact retained manifest,
and CAS tensor object
692f802e7c77791fadb255451e4afd30473a118fe6b93f147a90a0f9b6c2b26f.
It reuses saved clipped gradients, participation masks and retained per-leaf
clocks. The detached CPU-only receipt passed with source_mutated=false.
Result SHA-256:
72706e2b74859f46d09e742f42add01124e381f77edeece55c26594da0858bbc.
Snapshot:
c51bfc3ebf829e8d33a724132baa729c5e636cee1b6644de980139615ac890a3.
Wall 31.706 s; CPU 23.219 s; process peak RSS 8.300 GB (not MLX allocation).
The saved-matrix binding agrees for every pair. The analytic FP64 reconstruction
differs from the actual FP32 adaptive displacement by at most 1.19e-7 per
coordinate; this is a sensitivity analysis, not a replacement native equivalence
proof.

| Capability | Active clocks | Mean retained share of next v | Coordinates with >=90% retained v | Native adaptive L2 | No second history L2 |
|---|---:|---:|---:|---:|---:|
| IDENTITY | 183 | 93.39% | 82.83% | 0.31710 | 2.38776 |
| PARENT | 183 | 94.26% | 84.54% | 0.30092 | 2.09770 |
| LINK | 183 | 94.28% | 84.60% | 0.29525 | 2.01138 |
| MEMBER | 192 | 93.19% | 82.03% | 0.28933 | 1.98680 |
| EDGE | 192 | 93.73% | 83.29% | 0.32652 | 2.10380 |
| MAPS | 192 | 93.51% | 83.01% | 0.30285 | 2.17414 |

The denominator is the nonzero next-second-moment coordinates of selected
parameters only, not all model parameters. For those coordinates,
v_next = beta2*v + (1-beta2)*g_clipped^2. First-moment bias factors are 1
to reported FP64 precision; the second-moment reciprocal square-root factors
range from 1.0000000001102394 to 1.0000076539613232. Removing bias correction
alone leaves 24/36 positive predicted pairs. Removing retained second history
while keeping the next first moment and clocks would enlarge displacement
substantially; matching its adaptive L2 norm to the native norm still leaves
23/36 positive pairs. Replacing diagonal preconditioning with a uniform
denominator at matched norm leaves 25/36 positive pairs. The comparison retains
the native decoupled weight-decay vector in every counterfactual.

Subtracting the carried first-moment contribution with the native denominator
held fixed leaves 17/36 positive pairs. This is an additive decomposition,
not a restart, treatment, or prediction of multi-step AdamW dynamics. The
absolute sum of 36 native dots is 0.01308956; old moment is 0.01239132;
decay is 1.15689e-7. Shared non-output/non-identity parameters have positive
dots in 27/36 pairs, with mean 0.00018643. The epsilon-selected readout
partition has mean 0.00000790 and absolute sum 0.00272834, falling to
0.00130899 at epsilon 1e-4 while the full-model harmful-pair count rises
to 25/36. Partition absolute sums are not additive shares because signed
contributions cancel. The epsilon partition includes shared attention
projection coordinates, not only capability-exclusive outputs.

The controlled mask has 168 active leaves out of 214, and 183 or 192 active
clocks out of 26,336. The tied identity bank selects 16 or 25 rows, respectively.
The controlled norms are 0.0899-0.0947: clipping does not scale them at the
limit of 1. Masking changes the raw negative-gradient dot by at most 2.62e-6.
Frozen coordinates cannot advance their moments or clocks.

## Historical delivery and causal limits

The latest 64/68 target-stage failures (94.1%) rule out an account of the
observed rejection distribution based solely on protected-capability interference.
A.EDGE had 19 no-gain rejections; A.PARENT had 6 no-gain and 12 target-regression
rejections. No A.IDENTITY visit was selected. Other targets had mixtures of
no-gain, target regression and protected regression. Historical C05 authority
still decides whether a candidate may be retained. The diagnostic cannot infer
architectural attainability or generalization from six balanced loss probes.

| Witness | Attempted steps | Operator seconds | Attempts/min | Target failures | Protected failures | Retained steps |
|---|---:|---:|---:|---:|---:|---:|
| R2 control | 318 | 361.473 | 52.784 | 19 | 11 | 0 |
| R3 treatment | 279 | 364.265 | 45.956 | 12 | 17 | 0 |
| R4 treatment | 273 | 362.145 | 45.231 | 12 | 17 | 0 |
| Latest manual | 936 | 906.814 | 61.931 | 64 | 4 | 0 |

R3 and R4 each skipped six neutral visits. R3 had 19/33 and R4 had 16/25
independent items correct before and after; neither is a complete 72-item
qualification. R4 remains bound to 165c73a73811769a24bdaadbe61466d2c02cf286.
R2/R3/R4 delivery receipts contain authentic source seeds, direct IDs,
semantic-row hashes and realized roles; they cannot recreate the original
rejection authority or substitute for fully bound mixed source rows.

These runs delivered 32 direct rows and five retention-support rows per
recorded optimizer step, plus zero or one fresh support row. Their actual
fragile-preservation, weakness-priority, old-grade and guidance deliveries
were zero. The latest manual record likewise has 4,680 support rows, 688
fresh-support rows and no fragile preservation or guided steps. Accepted
generation 69 has no active champion adviser roles. A nonzero selected
distillation weight is therefore not evidence of realized teacher guidance.
Zero semantic-pattern delivery is not by itself a defect: R3/R4 recorded
zero required patterns for the applicable sources. Likewise old-grade rows
are not required merely because current-grade peers are protected.

The authenticated v1.0.0 and Factory oracle implementations distinguish
fresh per-step draws, protected and fragile-weakness rehearsal, capacity,
realized source controls, and gold-gated champion/soup advice. Preserve
those distinctions rather than copying their historical acceptance law.
The research document identifies optimizer displacement, semantic co-observation,
targeted rehearsal and source-gated distillation as hypotheses. The observed
momentum and shared-coordinate interference support further causal testing;
they do not authorize changes to production optimizer architecture or establish
that output-only epsilon is the highest-yield intervention.

R3/R4 each record 39 selection invocations (about 54 seconds total, median
1.22/1.19 seconds), not 39 completed assessments. Terminal candidate decision
scope counts were 19 one-capability and 11 six-capability for R2, and 12
one-capability and 17 six-capability for each of R3/R4. These are not evaluation
invocation counts. The actual manual executable identity, activated correction
set, full-visit timing, cache reuse and evaluation-only throughput/latency
remain unavailable from the surviving receipts. No process-specific swap
attribution or independently retained gain/minute is invented.

## Native selected-lesson custody and implementation repair

The relocated copy initially required authenticated cadence replay. The first
repair corrected the historical-versus-live bundle step accessor without
weakening rejection authority, receipt, generation or optimizer-step checks.
Full replay then stopped at missing historical rejection-authority object
0e59438b3a4f9db5177298dedc82a837fc1bb7b3ab5fa757984711bd8dc73f76.
A bounded read-only search of 47 database candidates and 43 object archive
packs found no matching object. No authority was manufactured.

An existing frozen #1657 witness supplies a legitimate alternate route.
Its v3 cadence projection SHA-256 is
6aab98debb0893ed8f128560fe6da1b9035e75e26b4392ec8f5b8857bd2a16e9.
The saved projection exactly matches its originating SQLite projection record
and ledger identity. All 832 indexed records cover the contiguous 99,292,738
byte prefix with SHA-256
cff08d5d7b7d5655666c6afa0edee16e8774139c90531379027cfffe02e65629.
The accepted pointer and entire prefix agree with the frozen diagnostic source.
The established detached witness owner rebinds only this verified projection
to a new isolated copy. Native replay authenticates its unseen tail through
100,899,714 bytes. This is not a reconstructed rejection authority or a bypass.
Focused tests reject altered prefix, invented projection, index gaps and payload
drift, and symlinked custody before cloning.

Successful cadence preflight exposed a real implementation defect: numeric
rehearsal allocation pressure was inserted into a semantic digest which
intentionally rejects floats. The fix binds the complete finite policy
allocation via the existing teacher-record digest and leaves non-allocation
plan identities unchanged. The actual allocation producer/plan compiler
regression checks determinism, changed pressure identity, balanced delivery
and source authority. Nineteen affected tests passed. No generic semantic
serialization or retention rule was changed.

The next execution reached the authentic native loss and source-coordinate
validation boundary, then exposed a diagnostic-only dense-gradient assumption.
Ordinary learning-first microbatches may omit frozen parameter leaves.
The repaired diagnostic passes the original sparse gradient tree to native
AdamW, requires omissions to be completely frozen, and records zero extension
only for the common measurement basis. The regression rejects a missing
participating gradient. No ordinary gradient, clipping, or optimizer
implementation was changed. For sparse delivery the raw cosine describes the
returned gradient vector on that basis, not an unmeasured dense derivative.

## Actual ordinary selected lesson

The ordinary native witness passed without source mutation, snapshot
e4021a524478382cf124e93368f35bd147b4716a5a8f63a49eb3a5eb93b4a154,
result SHA-256
96000c7607f9c9e7269ee9c6b86f0474862b416ad2b64da1acceec4304bafc12,
receipt SHA-256
705beeee52cb3227271314defc5a3ec9ad0722de1145d7b3618f275666fdfbdf.
Native selection chose A.LINK; the selected policy was contrast 0, depth 1,
distillation 0.13, learning rate 0.00013, old 8 and preview 4. With zero active
adviser roles the native first-step delivery contained 26 direct LINK rows,
four PARENT retention-support rows and two EDGE retention-support rows,
bound to their actual source authority. No candidate was returned for retention.

This natural 32-row lesson is not the 32-direct-plus-five-support geometry
of the earlier historical witnesses. Its native clipped norm is 0.04019865;
the clip limit is 1. Forty-five entirely frozen gradient leaves were omitted.
Selected-row/full-mask parameter, first-moment and second-moment maximum
absolute errors were respectively 7.276e-12, 3.638e-12 and 5.552e-17.
Clocks and frozen coordinates agree exactly.

| Protected probe | Raw cosine | Native loss dot x 1e6 | Carried first moment x 1e6 | Output epsilon 1e-4 dot x 1e6 |
|---|---:|---:|---:|---:|
| IDENTITY | 0.06631 | 491.448 | 675.337 | 512.639 |
| PARENT | 0.09401 | -134.823 | 142.937 | -174.044 |
| LINK | 0.07037 | -482.729 | -278.736 | -513.800 |
| MEMBER | 0.03479 | 94.208 | 382.044 | 115.362 |
| EDGE | -0.01223 | -35.346 | -45.922 | 20.460 |
| MAPS | -0.05577 | 919.225 | 659.347 | 873.002 |

Three of six predicted changes are harmful, including two positive-cosine
pairs. Both actually rehearsed capabilities have negative predicted loss
changes, while unrehearsed MAPS has the largest positive predicted change.
This association motivates a controlled allocation comparison; it does not
prove that changing allocation causes retained competence gain. The controlled
and mixed LINK gradients differ in composition, and are not matched arms.
Epsilon 1e-4 increases the mixed harmful-pair count from three to four.

The other five capabilities were examined only with diagnostic restrictions
holding all other eligible capabilities. Four returned NO_ADMISSIBLE_TEACHING
(IDENTITY, PARENT, EDGE, MAPS); MEMBER returned PERFECT_TARGET_SKIPPED.
Those are lawful outcomes, not missing gradients to fabricate or bypass.
The six-capability controlled witness supplies complete comparable gradient
coverage; ordinary selected-lesson evidence covers only the naturally
admissible LINK lesson at this exact checkpoint and cadence.

The detached witness took 83.550 seconds elapsed; first-step capture took
3.958 seconds, with peak MLX allocation 3.721 GB and overall process peak RSS
6.019 GB. The 0.343-second perfect-target skip is not a candidate evaluation.
No throughput or independent examination claim follows from these timings.

## Reproduction and review

On operator-authorized frozen custody, the controlled command is
`python3 -B -m scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics RUN PLANE NEW_DESTINATION`.
Reuse existing saved gradients rather than regenerate them. The
`moment_sensitivity` command consumes EVIDENCE NEW_RESULT with
`--result-sha256`. The `native_lesson_dynamics` command consumes RUN PLANE
NEW_DESTINATION with `--protected EVIDENCE --protected-result-sha256 DIGEST`
and optionally `--cadence-projection-root VERIFIED_FROZEN_ROOT`.
The ordinary witness requires native selection and prospective admission
authority, permits lawful holds/skips, and aborts before returning a candidate
to the retention horizon. It is one-step diagnosis, not historical full-visit
replay or a new training treatment.

### Design fidelity and review boundary

Issue #1645 authorizes research/conformance and preservation of legitimate
predecessor behavior, not new retention or curriculum authority. In the
scoped implementation comparison, the historical optimizer-step accessor and
finite allocation identity changes repair implementation defects: they restore
existing rejection and rehearsal contracts without relaxing validation,
changing source selection policy or changing C05 thresholds. The allocation
digest uses the existing finite teacher-record serializer inside the semantic
contract digest. The sparse-gradient extension is diagnostic-only; the native
optimizer receives the original sparse tree. All new counterfactuals run
outside the ordinary training path. The projection restoration accepts only
the exact preserved projection and its authenticated prefix; ordinary
generation/receipt checking is not disabled.

The preceding is a developer-side comparison against the governing issue
and callable contracts, not an independent EGM verdict. No completed
independent design review for this added diagnosis is established. The
previous pinned reviewer launch failed to confirm the requested model and
reasoning configuration; those failures are not substantive review findings.
The issue remains review-pending; do not open a placeholder PR, certify an
independent pass, alter the integrated acceptance head, or advance the next
experiment. No experiment is authorized by this report.
