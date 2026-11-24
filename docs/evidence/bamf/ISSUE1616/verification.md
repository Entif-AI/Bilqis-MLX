# #1616: Backbone compilation qualification (negative)

## Disposition

Do not activate nested backbone compilation in the production trainer.
The installed MLX 0.32.4 can reuse a separately compiled differentiated
four-layer numerical function, but the nested group boundary in the actual
ordinary trainer still retraces. A small observed throughput increase does
not establish a reusable backward graph or improved learning yield.
Keep the existing stock path. Send the differentiated-boundary finding to
parent #1614; no production changes, no policy change, no custom Metal kernel.

## Provenance

Native M3 Ultra; ordinary source base
`83671fea5420e13499d83c92b31ca96f44b2a4fc`.
The component snapshot is
`d2e3a43ddb9327bc925b4590f036b6f1ec6f412ab1148abf14336ce7e7fd77a7`.
The two-visit snapshot is
`6ee7b5254d710b88a69ffdcd474af44391a5237197848818696f996c0447967d`.
Both used separate fresh processes, temporary learner/data-plane copies,
32 logical rows, FP32 stock AdamW, the same source and teacher settings
in both arms, and route compilation enabled in both. The operator campaign
used the frozen generation 51, optimizer step 509, accepted manifest
`317f6785f99dfb6cf4ab76ccea420110ef91f9ceaef01cc47d9e2e9ca3f06dfe`.
The screened launcher receipts report unchanged source snapshots and worktrees. Full native receipts, ordered row coordinates, and raw HOW records remain in the local immutable snapshots and archived local evidence commit. Public JSON retains the aggregate measurements, source and receipt identities, exact comparison results, and digests of the omitted records.
No human-run learner was opened for mutation. Neither result is a
replicated or independently authorizing performance estimate.

## Direct group evidence

[Direct receipt](direct-parity.json) records six cases with changed weights,
activations, masks, shape, extent and source-owner identity. All 264 tested
parameter gradients, 216 cache tensors, all loss/hidden comparisons, and
264 entries in each AdamW successor field are exact. Causal prefix and reset
suffix comparisons are exact. LRU eviction and cache metadata are checked.

| Boundary | Stock cold | Compiled cold | Stock warm median | Compiled warm median | Compiled Python traces |
|---|---:|---:|---:|---:|---:|
| Nested group under outer autodiff | 17.85 ms | 16.32 ms | 16.89 ms | 19.88 ms | 4/4 |
| Standalone compiled value/gradient | 11.85 ms | 3,569.77 ms | 11.29 ms | 8.88 ms | 1/4 |

Standalone differentiated warm time fell 21.3%, but cold latency rose
approximately 3.56 seconds and measured MLX peak was 1,259,544,986 versus
900,508,792 bytes. The latter timing fixture retained result trees for
comparison and is not a production memory claim. Python function entries
count graph traces, not individual Metal shader compilations. Nested graph
construction remained on the differentiation path.

## Native component experiment

[Component receipt](component-evidence.json): one disposable B.AND candidate,
12 optimizer steps per arm, same source release, seed, parent, 32 ordered
training rows, optimizer participation and final optimizer bytes. C05
returned ELIGIBLE/PAIRED_SCREEN_WITHIN_BUDGET in both arms (2/6 to 3/6
on the same scorecard cohort).

| Measure | Stock | Nested compiled |
|---|---:|---:|
| Attempt wall (training + C05) | 33.340 s | 30.372 s |
| Attempted steps/min | 21.596 | 23.706 |
| Completed component trials/hour | 107.979 | 118.532 |
| Peak MLX bytes | 13,434,581,144 | 13,434,581,144 |
| Backbone owner misses / hits / traces | 0 / 0 / 0 | 3 / 33 / 36 |

The observed throughput increase is 9.77%; warm median wall ratio 0.9033.
All 36 nested group calls traced, so the reusable-backward gate failed.
Ordinary realized_cost is empty; the original raw summary incorrectly
counted two missing loss sequences as equal. The receipt explicitly
corrects that to NOT_MEASURED. The independent operator witness below
captures the actual numerical loss instead. Ordinary C05 does not require
independence from training; the matched six-case improvement is not the
independent competence metric.

## Native ordinary operator experiment

[Operator receipt](operator-evidence.json): 2 visits x 12 optimizer steps,
including real teacher selection, planning, training, retention, publication
to the disposable checkpoint, and operator maintenance. Both arms attempted
24 updates, rejected A.PARENT (NO_MEASURABLE_TARGET_GAIN), and accepted A.EDGE
(PAIRED_SCREEN_WITHIN_BUDGET), retaining 12 updates at generation 52 / step 521.
All 24 actual scalar losses, row and source-coordinate sequences, selected
visit identities, policy, controls, scores and final optimizer bytes match.

| Measure | Stock | Nested compiled |
|---|---:|---:|
| Operator wall | 75.294 s | 71.356 s |
| Attempted steps/min | 19.125 | 20.180 |
| Completed teacher trials/hour | 95.625 | 100.902 |
| Peak MLX bytes | 14,049,785,756 | 14,049,785,834 |
| Gradient launches / barriers / scalar fallback rows | 48 / 24 / 0 | 48 / 24 / 0 |
| Backbone owner misses / hits / traces | 0 / 0 / 0 | 27 / 141 / 156 |

Observed throughput was 5.52% higher, not a replicated speedup. Only
12 of 168 group calls avoided a Python trace; the boundary did not
establish reusable backward execution. No claim of complete elimination.

The original detached receipt is FAIL: the assertion compared selected
teacher fingerprints byte-for-byte across processes. The actual first
rejected candidate has a distinct process-local identity token (the stock
step authority hashes Python optimizer/parameter object IDs). That token
enters the rejected decision/evidence/outcome digests. HOW credit retains the
outcome digest in the teacher ledger, so the second selected teacher
fingerprint differs despite identical visit identity, policy, realized
action, loss and score records. Accepted candidate canonical identity is
unchanged. This is a custody identity difference, not proof of teacher
state equality or of a neural difference. Preserve the original failure,
raw terminal records locally; publish their digests and selected receipt identities. The corrected comparator projects
only the known receipt-specific fields out of behavioral comparison,
keeps accepted canonical identity, and retains raw receipt inequality as a
separate result. It was replayed on both actual saved event ledgers without
repeating GPU training. Two cheap regression tests cover rejected receipt
identity, meaningful policy/score drift, and accepted canonical identity.

## Competence and limitations

The same pinned 72-question Grade A assessment
(`af63c8cf6069c8960fbe5a0cae84d35e4ec6ad78445d28b31a5ed51ff79b0ded`)
fell from 44/72 to 39/72 in both arms. Ten assessment episodes overlap
with new training episodes, so the full exam is not an independent measure.
The campaign-disjoint subset excludes whole capabilities with any matching
source-family or episode identity in either arm, using the original fixed
cohort and no score-based selection. It retains A.PARENT and A.LINK
(24 questions, subset identity
`f560d466e65519cfdd9f18d16cbfe1bf41fe15ad42622aed20490adfcf407ff9`).
Both score 12/24 before and after: **0 percentage points of competence
change per operator hour**, relative to the two new visits. This is a
retrospective provenance-only subset, not a prospective independent exam
and not evidence of exclusion from the learner's earlier training history.
No general competence improvement is established.

## Reproduction

Use Python 3.14 with MLX 0.32.4 on an isolated M3 GPU. Run the direct
and component witness from the pinned source and use the detached launcher
for long work. The operator witness takes the existing #1607 frozen campaign
donor and a fresh output folder next to the frozen campaign inputs. The donor
SHA-256 is checked by the script. All long runs must use separate timing windows.

```sh
PYTHONPATH=. python3.14 -B -m scripts.bamf.profiling.issue1616.parity
PYTHONPATH=. python3.14 -B -m scripts.bamf.profiling.issue1616.training
PYTHONPATH=. python3.14 -B -m scripts.bamf.profiling.issue1616.operator \
  --donor /path/to/compare_learning.py --output /path/to/fresh-operator-output
python3.14 -B -m unittest scripts.bamf.profiling.issue1616.test_operator_receipts
```

The experimental monkeypatch and bounded LRU live entirely under
`scripts/bamf/profiling/issue1616/`; stock strict and ordinary behavior
outside those witness processes is unchanged. A larger reusable backward
boundary would require a different integration design; neither this result
nor the standalone synthetic speedup authorizes such a change.
