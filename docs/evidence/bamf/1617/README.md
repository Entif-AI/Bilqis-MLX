# #1617: Invariant registry preparation

Disposition: **qualify the measured residual for parent #1614; do not install the experimental monkeypatch or a new persistent cache in production.** This is a narrow experiment on unchanged production training code, not a new authority or a claim of improved learning yield.

## Result

The native M3 Ultra ordinary-mode campaign used isolated copies of the same generation-51, optimizer-step-509 learner and the same cadence projection. Each arm attempted three visits of twelve optimizer steps, logical batch size 32, two source-prefetch workers, stock FP32 AdamW and a 24 GiB MLX memory limit. Strict scoring used a fixed 72-question cohort. The two source snapshots share production base `83671fea5`; the differences are confined to the experimental harness. The initial launcher failed after completing the baseline; the corrected prepared arm passed, and the baseline result was preserved rather than rerun. [Machine-readable evidence](experiment.json) binds the exact source snapshots, original receipts, local donor scripts and raw profiles by digest. These are one matched-start campaign, not replicated timing estimates or an exclusive-accelerator occupancy proof.

| Measure | Baseline | Prepared |
| --- | ---: | ---: |
| Ordinary campaign wall seconds | 111.854 | 92.441 |
| Attempted steps/minute | 19.311 | 23.366 |
| Completed teacher trials/hour | 96.555 | 116.831 |
| Attempted / retained steps | 36 / 12 | 36 / 12 |
| Peak MLX bytes | 15,904,622,512 | 15,904,622,512 |
| Fixed exam correct / total | 39 / 72 | 39 / 72 |
| Fixed-exam change / hour (questions) | -160.924 | -194.718 |

The observed throughput ratio is 1.210. The independently measured initial score was 44/72, so both arms lost five correct answers. Faster processing of unsuccessful teaching is not improved useful competence. The six final capability scores match exactly. Both arms accepted only A.EDGE and retained precisely the same 856-tensor state object (953,848,264 bytes, SHA-256 `ae707574460592fec6622941377281d8eb702f468528be24cea8644f31296297`) at step 521, with identical optimizer metadata, extents, topology and training objective. This is exact **retained state** evidence, not a proof that every speculative gradient matched.

The first two visit projections match. The third rejected A.MEMBER candidate differs: parent/candidate score 4/6 to 2/6 in the reference versus 4/6 to 3/6 in the prepared arm. Its selection policy and realized delivery counts match, but the accepted generation's baseline-evidence, outbox and teacher-state sidecar digests differ. Thus the next accepted manifest and visit identity differ. The runtime derives step seeds from the visit ID and fresh C05 seeds from the accepted manifest/candidate; equal initial state and configuration do not guarantee an identical third cohort. The evidence does not isolate the cause of every sidecar difference. Both third attempts reject for TARGET_BASELINE_REGRESSION. Do not claim complete trajectory, ordered-row or gradient parity from this campaign.

## Residual operation counts

The following measurements come from the training-only `profile.json` captured before strict fixed-exam scoring. Inclusive time overlaps nested calls and can span multiple threads; do not sum the rows or equate them with GPU wall time.

| Operation | Reference calls / seconds | Prepared calls / seconds |
| --- | ---: | ---: |
| Cognitive operator implementation digest | 19,284 / 9.828 | 124 / 0.109 |
| Cognitive operator default registry | 660 / 9.891 | 1 / 0.084 |
| Ordinary task-goal preparation | 297 / 9.775 | 296 / 0.161 |
| Canonical source registry | 435 / 1.507 | 100 / 0.269 |
| Canonical graph resolution | 288 / 1.897 | 288 / 0.995 |
| Live task-goal lowerer registry | 66 / 0.100 | 1 / 0.009 |
| Factory evaluation instruments | 8 / 3.052 | 8 / 1.129 |

The prepared scope recorded 657 operator-registry hits, 706 implementation-digest hits, 335 source-registry hits and 65 lowerer-registry hits. It did not reuse assessment predictions or gold, row bindings, compiled cases, route plans or gradients. It recorded one owner scope spanning the campaign. A direct attempt to reuse the admitted context's source registry did **not** match a fresh canonical adapter/callable set; the experiment reused the freshly constructed canonical registry instead. This is a negative integration result: production must identify the actual owner rather than silently treat the two registries as interchangeable. The source lookup and evaluation compilation still perform row-dependent work.

## Ownership, invalidation and verification

- #1232 eliminated same-seed source preparation across a visit horizon; #1273 transferred already-qualified source materialization into Factory/B11; #1573 reused visit-stable row numerical inputs. The remaining cost here is rebuilding process/release-invariant operator and provider declarations *on actual row cache misses*, not preparing the same rows again.
- The experiment uses a disposable scope only at ordinary task lowering and evaluation instrument/reference-case entry. The registry is indexed by semantic release and scoped to the exact source execution context, release, graph, root and adapter registry identities. A changed context or dependency object must miss. The detached runner pins implementation/source bytes at process start and rejects a changed snapshot on return; no per-row source hashing is introduced. In-place mutation of live graph/provider internals or loaded implementation objects is **not qualified** by this spike. Strict calls bypass prepared state and retain native fail-closed verification.
- Focused native smoke tests compare actual training goals/targets and C05 case/template, compiled rows, compiler config, source AST, rights/forest receipts and exact preflight results against reference. They exercise all four reuse paths, an alternate semantic release and replacement source context, and strict bypass. The alternate release is a synthetic dependency-key adversary, not a new admitted release. The scope tests separately exercise replacement of release, graph, source root and source registry, and the existing snapshot digest on altered source/provider/operator bytes. Eight existing cognitive-operator authority tests cover native contract drift and source grant rejection. These checks are bounded; a fully admitted provider/source transition and all rejected candidate gradients remain unmeasured.
- No human learner was mutated. Both detached source mutation guards report unchanged source. Two unsuccessful experiment launches exposed a wrong relocated-package import and a mismatched attribute name; the corrected smoke now executes real ordinary training and assessment paths instead of merely importing modules.

## Handoff to #1614

First remove repeated operator implementation hashing/registry construction at the existing release-owned ordinary preparation boundary. Reuse immutable released declarations and resolve each operator without reopening source files; keep strict construction/resolve independent. Do not bypass source or route validity. The large gain is in this operator path, not in caching C05 predictions. Reuse provider and lowerer declarations only when their actual admitted owner and implementation epoch agree. Keep row-specific source authority, gold-blind goals, expected answers, C05 candidate scoring and generation-bound numerical execution fresh. The same accepted numerical state may be accompanied by a different evidence manifest; paired learning witnesses must freeze delivered rows and C05 inputs rather than infer equivalence from manifest ancestry. Verify real semantic/provider/source transitions and fixed-row numerical parity in the integration branch before activation. No production file, policy or cache schema is modified by this PR.

## Reproduction

The measured historical source is retained at `c76478498` (see the full commit and snapshot identities in the JSON). The reviewable harness is now compartmentalized under `scripts/bamf/profiling/issue1617/`; the relocation and focused smoke checks do not change the measured preparation mechanism. Run `python3 -B -m scripts.bamf.profiling.issue1617.test_scope` for the portable scope witness. Run the existing cognitive-operator authority tests with the repository interpreter. For native reproduction, use `python3 -B -m scripts.bamf.profiling.issue1617.profile --help` and the repository detached launcher with an isolated output directory. The local campaign donor and frozen generation-51 fixture are required inputs, not distributable learner data; their digests are recorded. A fresh measurement needs those exact inputs or an explicitly documented new baseline. Do not use a sovereign run as the experiment destination.
