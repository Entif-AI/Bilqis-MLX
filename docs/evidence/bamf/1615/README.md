# #1615: Differentiable causal-prefix sharing

**Disposition:** qualify the bounded ancestor-gathered trie as an integration
candidate for parent #1614. Do not install this experiment in production.
The native result supports lower backbone work and memory with modest
component-trial throughput improvement. It does not establish a useful-learning
gain, a general break-even rule, or parity for every released task.

## Compiled-position census

The census uses the packaged Atlas and Factory release at production base
`83671fea5420e13499d83c92b31ca96f44b2a4fc`, two seeds (1615 and 2615),
32 requested specimens per capability/draw and the ordinary source compiler.
It covers 42 individual deliveries across 21 capabilities. These are direct
released-provider draws, not a census of actual mixed teacher/rehearsal visits.
Within a draw, count actual compiled positions by cumulative causal history,
task scope, position kind and admitted source ABI. A packed closure is row-private
in the conservative count, and so is its entire suffix. The optimistic count
ignores closure contents. Exact compiled cache identities are a separate
diagnostic: they are not a numerical equivalence test.

| Grade | Compiled / requested rows | Positions | Conservative repeats | Repeat fraction |
| --- | ---: | ---: | ---: | ---: |
| A | 384 / 384 | 9,280 | 3,803 | 40.98% |
| B | 512 / 512 | 11,633 | 3,672 | 31.57% |
| C | 154 / 448 | 2,930 | 830 | 28.33% |
| Total | 1,050 / 1,344 | 23,843 | 8,305 | 34.83% |

The ordinary compiler rejected 294 C specimens with
`BAMF_PREFIX_SCHEMA_NOT_RELEASED`. These are held, not silently substituted or
included in the successful-position denominator. The missing schema was
`school.op.EQ` in the tested configuration. This is not a diagnosis of the
sovereign learner or a license to modify the numeric curriculum. The optimistic
repeat count is 8,312; exact cache-identity repeats number 25. Total independent
padded positions are 29,864. See [census](prefix-census.json), including all 42
per-delivery records and a final-harness replay with identical counts and
delivery identities.

## Mechanism and scope

The isolated harness builds one live differentiable trie per eligible ordinary
microbatch. A node's identity includes its complete causal history, task scope,
capability, semantic release and policy version. RoPE uses path depth;
causal convolution uses the parent and grandparent projections. Attention
is restricted to ancestors, never siblings or unrelated paths. The dense
variant uses a masked full trie; the gathered variant materializes only
ancestral K/V arrays and avoids the unused dense mask. Every packed closure and
its descendants are row-private. Duplicate rows remain distinct logical
objectives; reconstruction gathers each original row in its original order,
allowing autodiff to sum all downstream contributions.

The prototype replaces the B04 numerical group computation in a disposable
ordinary B11 trace only, expands rows at each B05 depth-group boundary, and
retains production depth selection, adapters, typed route/readout, loss,
participation and AdamW. It does not retain hidden states or detached inference
K/V across steps. Motif-bearing, retained-cache, strict/source-authority and
unsupported traces are outside the qualified scope. Neither source-atom
coalescing nor production kernels, authority/policy, curricula, or persisted
learners were changed. The current experiment is an intentionally scoped
monkeypatch, not a production admission mechanism.

## Matched evidence

All native arms ran in separate processes on the M3 Ultra using disposable
genesis learner/data-plane state, the same ordered B.AND rows, source seed
37116, FP32 AdamW and matched optimizer coordinates. They do not measure
multi-visit operator planning, publication or maintenance. Reported trial rates
are rates for one bounded teacher-selected candidate horizon plus actual C05
evaluation, not measured whole-operator teacher trials/hour. Timing uses one
matched pair per geometry, not replicated distributions or a universal
speedup. Parent state remained unchanged in the final witness. Native source
snapshots and raw log digests are bound in the receipts.

- [Block preflight](block-preflight.json): both CPU variants reproduce the
  production-geometry CCGQA/FFN control on divergent suffixes, duplicate
  specimens, mixed lengths and distinct scopes; 19 logical positions become
  12 unique nodes. Full hidden, loss and every gradient leaf match within
  FP32 tolerance.
- [Failed CPU receipt](native-cpu-v1-failure.json): four real B.AND rows,
  all gradient/AdamW checks passed, but raw record equality failed. The
  comparator incorrectly required process-local generation authority tokens to
  match across separate learners; exact differing fields were not captured in
  that run. The revised comparator validates each token against its own
  current optimizer and compares all remaining participation fields and stable
  coordinates. V1 memory was also confounded by live control tensors.
- [Native single-step receipt](native-gpu-single-step.json): 32 actual rows,
  all per-leaf gradients, optimizer parameters, moments, counters, losses and
  normalized participation match within repository FP32 tolerances
  (atol 2e-5, rtol 3e-5). Maximum gradient absolute error is approximately
  1.00e-7. Logical positions fall from 826 to 620 unique nodes; the padded
  control executes 1,248 positions per block, so 7,536 block-position
  evaluations are avoided over 12 blocks.
- [Native horizon receipt](native-gpu-horizon.json): four updates with C05
  and a fixed held-out 18-case assessment, then a four-row single-update
  break-even observation. These timing-only arms compare every actual
  microbatch scalar loss, participation and final optimizer tensor leaf,
  not every intermediate gradient leaf. The single-step receipt supplies
  the separate full-gradient witness.

| Native scope | Stock | Gathered trie | Throughput ratio |
| --- | ---: | ---: | ---: |
| 32 rows, single step, steps/min | 19.11 | 20.05 | 1.049x |
| 32 rows, four updates, training steps/min | 20.98 | 23.34 | 1.113x |
| 32 rows, four updates + C05, steps/min | 19.06 | 21.12 | 1.109x |
| 32 rows, four updates + C05, completed component trials/hour | 285.83 | 316.86 | 1.109x |
| 4 rows, single step, steps/min | 75.38 | 78.74 | 1.044x |

The four-update training wall fell from 11.441 to 10.283 seconds. Including
C05, wall fell from 12.595 to 11.361 seconds. Peak MLX bytes decreased from
6,223,625,396 to 5,766,208,012 (7.35%); the single-step 32-row arm fell from
3,570,040,408 to 3,099,943,432 (13.17%). The four-update trie reports
30,144 eliminated block-position evaluations (including padding),
578,128 aggregate layout-array bytes over four layouts, 96,720 aggregate
ancestor-mask slots and 0.005688 seconds of host layout construction.
These are logical operation and array counts, not a hardware FLOP counter.
The gathered K/V activations still incur real graph/memory traffic.
The four-row GPU pair shows a small positive observed speed ratio despite
less prefix overlap; the earlier four-row CPU pair was slower. No universal
GPU crossover or exclusive accelerator occupancy proof is claimed.

Both four-update arms obtained the same C05 verdict
(`PAIRED_SCREEN_WITHIN_BUDGET`, B.AND 2/6 before and after).
The separate fixed cohort is row-ID and full-token-sequence disjoint from
training: seed 98318, six cases each for B.AND, B.IFF and A.IDENTITY.
Both started and ended at 4/6, 1/6 and 3/6 respectively. Fixed independent
competence change/hour was zero for both, including the retention-selected
score. This proves matched measured outcome on the sentinel, not increased
useful learning or transfer to a different source family. No disposable
candidate was published into an actual training run.

## Handoff and verification

Parent #1614 can consider the ancestor-gathered representation alongside
source preparation, padding reduction and existing B11 work-unit geometry.
Preserve exact source rows, per-position dependencies, masks, row multiplicity,
FP32 optimizer participation, depth boundaries and strict behavior. Validate
mixed scopes, closures, other admitted capabilities, motifs and refinement
before any expansion; retain the independent path for unsupported cases.
Measure a genuine multi-visit operator campaign against matched frozen teacher
and assessment inputs before promoting the mechanism. The aggregate program
goal is not an obligation for this isolated leaf to deliver 5x.

The final harness extracts the previously measured hook bodies into smaller
functions without changing their ASTs. Other native witness modules are
byte-identical to the passing four-update snapshot. The focused contract tests
exercise concrete ancestor maps, private closure suffixes, ineligible trace
rejection and patch restoration on exceptions. The production baseline did not
change during subsequent mainline synchronization; the intervening commits
add disjoint experimental scripts and evidence.

Run from the repository root using the repository's native MLX interpreter:

```sh
python3.14 -B scripts/experiments/issue1615/test_prefix_contract.py
python3.14 -B scripts/experiments/issue1615/prefix_census.py --self-test
python3.14 -B scripts/experiments/issue1615/prefix_dag.py --device cpu
python3.14 -B scripts/experiments/issue1615/prefix_dag.py --device cpu --gathered
```

For a census, use a separate temporary data plane and
`prefix_census.py --each 32 --seeds 1615 2615`.
For the native trial, use the existing detached launcher on a clear Metal
accelerator with the isolated `native_witness.py` command:

```sh
python3.14 -B scripts/experiments/issue1615/native_witness.py --device gpu --capability B.AND --rows 32 --horizon 1 --mode gathered
python3.14 -B scripts/experiments/issue1615/native_witness.py --device gpu --capability B.AND --rows 32 --horizon 4 --mode gathered --timing-only --assess
python3.14 -B scripts/experiments/issue1615/native_witness.py --device gpu --capability B.AND --rows 4 --horizon 1 --mode gathered --timing-only
```

These commands create temporary learner and data-plane copies; do not point
them at a sovereign learner. Preserve the native receipts and distinguish
their historically measured snapshot from the current reviewable source.
