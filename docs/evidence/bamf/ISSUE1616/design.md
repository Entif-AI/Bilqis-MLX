# #1616 experimental backbone-group compilation

Status: research only; no default runtime change. Base: 83671fea5420e13499d83c92b31ca96f44b2a4fc.
Parent #1614; #1609 and #1579 remain independent owners.

The actual ordinary B11 vectorized objective invokes _source_producer(trace=True)
then _finalize_source_hidden, which runs BackboneTraceSession.advance for
each of three groups. Source embedding, motif reads, source depth selection,
adapters, refinement, route loss, and optimizer admission remain stock.

Create scripts/bamf/profiling/issue1616/backbone.py: one experiment-local
compilation cache, scoped to a fixed source release. Wrap the stock
run_backbone_group_trace numerical equations rather than duplicate them.
Key by group, topology digest, extents digest, concrete tensor signatures
and explicit sequence-start presence. Inputs are group-local parameter
mapping, hidden, scope ids, valid and starts. Do not capture changing weights,
mask values, hidden or actual generation/prefix identity in the compiled
function. Trace stock equations with placeholder metadata and return only
hidden and cache tensors; reconstruct each AttentionCache with the caller's
real generation, prefix, parameter weakrefs and digest outside compilation.
Validate input geometry before cache lookup. A bounded LRU owns compiled
functions; count lookups and Python traces separately, not Metal kernel
compilations. The experiment patch applies only to the trace module binding
called by BackboneTraceSession, within a disposable ordinary-mode run.
Unadmitted numerical/strict evidence and all production defaults remain stock.
On compile error, preserve the failed evidence and use the stock control,
not a silent fallback in the measured compiled arm.

Create scripts/bamf/profiling/issue1616/parity.py: direct M3 GPU comparison
of stock and compiled real four-layer groups using seeded FP32 parameter
trees and multiple distinct inputs, scope boundaries, padding, shape changes,
changed weights, generation/prefix and extent/source transitions. Check hidden,
all cache tensor values, loss, gradients for hidden and every group parameter,
and native _adamw_update parameters, moments and counts. Use exact comparison
for integer/boolean and record FP32 absolute/relative deviations, with the
predeclared comparison rtol=1e-4, atol=1e-6; report exact equality separately.
Require finite outputs, materialize before timing, record cold/warm wall
and peak MLX bytes, and verify trace/cache reuse and invalidation.

Create scripts/bamf/profiling/issue1616/training.py: independent fresh-process
matched arms using current real source-owned C16/C05 harness, 32 logical
rows, 12 optimizer steps and identical source/seed/teacher/optimizer policy,
with #1576 route compilation held constant. Run retention target comparison
with stock evaluator on the same independently scored source cohort; record
completed trial/hour and fixed target change/hour, attempted steps/min,
per-step loss and timings, source identities, optimizer participation/state
and peak MLX memory. If the bounded source fixture or candidate trial is
inadequate for production claims, report that rather than extrapolate.
Use isolated temporary run and data plane; no live student mutation.
Serial GPU arms, cache disabled for freed buffers and explicit memory cap.
Create docs/evidence/bamf/ISSUE1616/verification.md with exact source,
commands, measurements, failure modes and disposition. Negative results
are legitimate. No activation PR for unqualified compilation.

## Deterministic experiment protocol (EGM finding resolutions)

- Capacity 12 per release-scoped owner; LRU evicts oldest on the thirteenth
  distinct key. Inputs: sorted group-local parameter dict, hidden [B,T,W],
  scope int32 [B,T], validity bool [B,T], starts bool [B,T] (all false when
  omitted); presence remains a static key bit. Outputs: hidden and, per layer,
  K, V, convolution Q/K/V history, last scope, scope IDs, sequence IDs,
  validity. Reconstruct stock AttentionCache with QKVConvolutionCache,
  actual parameter weakrefs, _attention_parameter_digest, zero start offset,
  and actual generation/prefix. Instantiate actual AttentionScope before
  lookup to preserve validation. Source-release change uses a new owner;
  extent/topology/group/shape/presence changes miss; weights, masks, values
  and generation/prefix changes hit. Compilation trace count is the count
  of Python numerical-function entries during MLX tracing, not a Metal
  compilation counter.
- Direct seed 587, Gaussian FP32 weights SD .01, unit RMS norms; group 1,
  extents (1,1,a*64,b*64,c*64). Hidden/masks vary across cases: [2,4,W]
  full validity, then changed weights/hidden/scope/padding with same shape,
  then [2,5,W], then explicit starts, then changed factor-map extent digest,
  then same geometry with new source owner. Generation/prefix change on
  second case. One initial miss, second case hit, then one miss for each
  new key/owner. Report actual trace counts; require at least one reuse
  without new trace. Scalar objective mean(hidden**2); differentiate hidden
  and all 44 group leaves. Initial AdamW m/v zero and scalar uint64 counts
  zero, HP (.00013,(.9,.95),1e-8,.01); all group leaves participate, decay
  enabled for matrices only. Compare outputs, caches, metadata, actual
  parameter references, gradients, loss and successor state. Check causal
  prefix and sequence-start isolation. Any parity failure stops training
  qualification; no activation.
- Native candidate stage uses current retention_throughput_profile._prepare_run,
  _execution_context, C16 real_candidate_training_horizon and C05
  evaluate_factory_retention_candidate; checked-in 5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7
  Atlas and vendor/legacy-v16. One fresh isolated process per arm, B.AND,
  source_each=32, horizon=12, existing C16 SOURCE_SEED, teacher learning
  rate C05_TRAINING_LEARNING_RATE. BILQIS_MLX_COMPILE_STABLE_KERNEL=1 for
  both; strict=False. Use native memory cap 32 GiB and no free-buffer cache.
  Count completed candidate/C05 trials (including rejects) / attempt
  seconds * 3600, attempted steps / attempt seconds * 60. Report
  source-gold scored comparable target delta in percentage points / attempt
  seconds * 3600 only if the exact common cohort is proven; do not infer
  retained competence from a rejected candidate. Also record selected
  source/seed, retention decision, full optimizer digest and counts.
  The C16 fixture is a production-component trial, not a complete
  teacher-selector/accepted-publication witness. A follow-up matched
  ordinary operator witness uses the existing #1566 disposable baseline
  clone helper with two visits x 12 steps each per arm, identical parent,
  teacher and fixed cohort, no retirement-policy patch. No mutation of
  actual student, and no parallel GPU timing arms.

### Fixed fixture and timing details

Each tensor signature is (shape tuple, dtype string); parameter signatures
are sorted (name, shape, dtype) tuples. The key also includes source release
through owner scope, topology/extent digests, group index and starts presence.
A 12-entry cache stores keys for lengths 1..12; refresh length 1 then insert
length 13: length 2 is evicted. Test this bookkeeping using a fake compiler
without evaluating 13 graphs. For numerical cases use seeded NumPy RNG 587
for the initial parameter arrays and fresh hidden/weight perturbations; the
second case adds .001 to every weight, .2 to hidden, sets scope row 0 to
[0,0,1,1], and masks row 1 final position. Other cases use zero scopes and
full validity unless explicitly testing starts (row 0 position 2). Change
factor digest from c*64 to f*64. For causality append one value of 100 after
the four-position prefix and compare first four outputs; for reset isolation
change positions 0..1 by 100 and mark position 2 as a start, compare
positions 2..3. Measure one cold call and three repeated warm calls per
mode after input materialization; synchronize immediately before start and
after loss/gradient materialization. Reset peak before each measured mode.
Record individual durations, median warm and cold totals, not a purported
exact Metal compiler time. Candidate attempt wall starts immediately before
the first C16 training step and ends after C05 scoring/decision materializes;
setup wall is separately recorded. Native operator wall includes planning,
training, retention and publication for two visits, not clone setup. The
operator witness is necessary for a positive production adoption claim;
a negative parity or candidate-stage result may conclude the isolated
spike without further GPU work. Record matched cohort IDs or mark independent
competence change NOT_MEASURED. The reference score is parent accuracy on
that exact same cohort.

Disposition is intentionally research-only; #1616 never activates a production
toggle. Stop with negative or incomplete qualification on any parity failure,
unequal C05 disposition/score, absent actual cache reuse, or less than 5%
improvement in both warm candidate step median and total candidate-attempt wall;
also stop on more than 10% peak-memory increase or exceeding 32 GiB. Two equal
C05 rejections count as completed trials, not retained learning. If the candidate
stage satisfies these thresholds, run the two-visit operator comparison. Require
at least 5% higher attempted steps/minute and completed trials/hour, no lower
fixed independently scored competence change/hour, unchanged matched
instruction/retention outcomes and at most 10% peak-memory increase before
recommending further integration to #1614. A missing common cohort, mismatched
trajectory, or noisy timing is inconclusive, not a positive qualification.
No result in this spike authorizes activation.

## Measured design evolution: supplemental operator witness

The component arm is faster but graph reuse fails (36 traces for 36 calls);
the positive qualification gate remains failed. The issue's reporting contract
still calls for a complete ordinary teacher trial and fixed independently
scored competence rate, not just C16/C05 candidate components. Execute the
supplemental two-visit comparison for evidence, not promotion. Reuse the exact
#1607 donor compare_learning.py (SHA256
e87bb2598c6a15657a328cae86f97c00f6b55af5c9136c728b5fc4a0e01446ed)
and the already frozen generation 51 / optimizer step 509 / 44-of-72 exam
baseline used by #1614. Both arms use identical current main-based snapshot,
32 logical rows, 12 steps per visit, two visits, ordinary strict=False, and
existing route compile enabled. No physical cap changes. Only the compiled arm
installs the experimental backbone owner. The stock C08 loss scalar is captured
in both arms after candidate-plan execution with actual row coordinates; this
avoids falsely treating empty ordinary realized_cost loss fields as equal.
Record wall and MLX peak before the fixed strict-scored Grade A assessment,
then compare exact exam, attempted/retained outcomes, row coordinates,
loss trajectory and final optimizer digest. Report exact episode overlap
between this fixed exam and the two new visits, and known source-family overlap;
a fixed seed does not establish family independence or prior-training exclusion.
No production activation is authorized even if operator performance improves.

### Closeout clarification

The rejected candidate decision uses process-local authority, not a
cross-process content digest. Preserve original terminal HOW records and
raw receipt comparison, project only the receipt-specific fingerprints and
rejected opaque candidate identity out of behavioral comparison; keep
accepted canonical candidate identity and every other HOW field. Compare
actual teacher visit identity, policy, context, realized action, rows,
loss and scores. Behavioral equality never asserts full teacher ledger
equality. For an exploratory campaign-disjoint exam subset, use the original
fixed cohort and baseline per-capability scores. Exclude whole capabilities
with any source-family or episode collision against the union of training
coordinates in both arms, using the same source-family fallback as the
ordinary compiler. The selection is independent of scores but retrospective.
Preserve the full exam, overlap inventory, and original failed receipt.
No production activation or new acceptance is proposed.

The behavioral projection removes exactly these paths from a copy of each
terminal attempt: `teacher`, `how_outcome.selected_teacher_sha256`,
`how_outcome.outcome_sha256`, `how_outcome.decision.decision_sha256`,
and `how_outcome.decision.evidence_sha256`. It additionally removes
`how_outcome.decision.candidate_generation` only when the terminal event
is exactly BAMF_CANDIDATE_REJECTED. All other fields remain compared.
The matched rejection fixture in test_operator_receipts.py changes these
six receipt fields and must compare equal behaviorally while raw records
remain unequal. Changing selected_policy.lr or a score must fail behavioral
equality; changing an accepted candidate_generation must also fail.
