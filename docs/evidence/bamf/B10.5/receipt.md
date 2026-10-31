# B10.5 bounded typed prediction composition — #635

## Exact lineage and status

Feature branch `codex/bamf02-b10-5-635-20261030` was cut from synchronized Lane B
`9104ce733e04fb9c82420428b18dfdbf5db49535`, also the consumed reviewed unified head.
The lane is checked out in another clean worktree and already equals unified;
no no-op merge was manufactured. Same-lane prerequisite #633 is consumed at
`ab54b9d00836fffe4250574f437ef41ff9ae5850`; #634 at
`035607123645fc113f9040c3cda1ce339e3aa4e9`. Both remain separate draft turn-ins;
this child does not close #469/#470 or qualify their independent review gates.
No main or sibling-lane merge occurred.

Semantic composition is at `e0919794` plus exact prerequisite refresh `3b6edd15`;
the final evidence/test commit and remote SHA are recorded by issue/PR readback,
not recursively embedded into this file. This is a scoped software proof and
**DEPENDENCY_PENDING** candidate, not producer admission or complete B10 acceptance.

A second worker's live #633/#634 receipts became visible during recovery. Their
helper/census ownership is preserved. The recovered full decoder is now #635's
missing parent API composition rather than a competing #469 implementation.

## Behavior and schemas

Public `atlas_readout.predict_typed` and `answer_loss` compose the existing
AnswerPlan/v2, source heads and state machine. `DecoderMemory` binds supplied
FP32 H, actual A05 compiled prefix row identities, context digest, source release,
generation and explicit legal anchors. Future rows and current/descendant targets
cannot enter earlier decision states. No backbone is run by this module.

The composition reuses #633 `encode_feedback_value`, `decision_hidden` and
`typed_decision_loss`, plus #634 `bind_readout_parameters`; it adds no competing
feedback encoder, loss primitive or tensor ledger. Shared role/occurrence inputs,
B01 state gamma, causal K/V192 attention and output gamma complete the equation.
Concepts use actual tied active identity rows. EPISTEMIC requires an explicit
five-label source registry binding, including exact artifact/source-bundle IDs.
Synthetic fixture labels are not a production taxonomy.

Stable independent batches commit before descendants. Teacher forcing commits a
current target only after its logits, for subsequent parent feedback. END commits
alone. Budget exhaustion stays PARTIAL; invalid source/neural output requests
UNRESOLVED fallback. Complete frames pass the existing source publication gate.
ModelOutput replays the committed prefix and requires exact typed candidate/order/
kind receipts. Failed-batch logits are discarded. Loss accepts only executed legal
labelled decisions; missing auxiliary labels retain differentiable zero. Weights
remain primary1.0, ROLE0.10 and EPISTEMIC0.10.

Schema identities: `bilqis.mlx.decoder-memory/v1`,
`bilqis.context-approved-projection/v1`, `bilqis.mlx.answer-plan/v2`,
`bilqis.mlx.readout-semantics/v1`, and `bilqis.mlx.model-output/v1`.
Current scalar/native value heads remain their existing source-bound owners;
this composition consumes the existing structured AnswerPlan boundary. No source
meaning, empty-set identity, additional auxiliary label or live curriculum is invented.

## Changed ownership

- `learning/atlas_readout/decoder/{inputs,feedback,math,heads,execution,prediction,losses}.py`
  and mirrored `decoder/tests/`, plus existing package exports.
- Mandatory encountered-file repair: `semantics/atlas_projection.py`, cohesive
  `atlas_projection_parts/`, historical fixture facade and mirrored projection
  tests. See the separate structural receipt in B10.3 for baseline AST, artifact
  parity, helper extraction, public record/pickle and durable fsync proof.
- Same-lane dependency files remain owned by #633/#634, including their issue
  mirror/registry evidence. `git diff --name-only 9104ce7...HEAD` is the exact
  complete changed-path inventory; no shared trainer or runtime file changes.

## Proof

Final focused CPU union: **95 passed, zero failures/skips/errors**: 24 decoder,
57 existing/shared readout, and14 actual-source projection tests. A fixture-only
projection run intentionally skips its real-corpus witness when the pin is absent;
this turn-in supplied the actual pinned conformance bundle. The real source test
pins the original release, artifact and every published payload hash.

Red tests reproduced acceptance of unexecuted/missing/reordered/truncated loss
receipts and same-release foreign classifier artifact/source bundles. Repairs
reject those inputs. Other literal witnesses cover the independent NumPy decoder
equation, structural-vector golden, future-H/gold invariance, predicted-vs-prior-
target feedback, UNKNOWN/alternatives, nonfinite/source fallback, exact independent
batches/END-only receipts, missing-label zero gradient and gradient flow through
identity/role/control/feedback/attention/norms/H. Future H gradients are zero.

```sh
BILQIS_ATLAS_REAL_CORPUS=/path/to/f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec \
node ~/.codex/hooks/validation-output-runner.mjs -- python3 -B scripts/run_tests.py \
  bilqis_mlx/semantics/tests/atlas/projection \
  bilqis_mlx/learning/atlas_readout/tests \
  bilqis_mlx/learning/atlas_readout/decoder/tests
python3 -B scripts/check_module_size.py --changed-from 9104ce7
python3 -B scripts/quality/check_governance_integrity.py --base-ref 9104ce7
python3 -B scripts/code_smell_audit.py --changed-from 9104ce7 \
  --check-baseline docs/evidence/development/code_smell_baseline.json
python3 -B scripts/quality/check_docs.py
python3 -B scripts/verify_bamf_0_2_contracts.py
git diff --check 9104ce7...HEAD
```

Structure/governance/hygiene/diff are clear; no baseline expansion. Docs and BAMF
contracts pass. A first docs command used the nonexistent `scripts/check_docs.py`;
the actual `scripts/quality/check_docs.py` was then run successfully. Initial
relative-import load errors were corrected to use the repository's actual loader.
The unchanged integrated architecture gate still fails at
`runtime/model_topology_v2.py:280 GENERIC_GRADE_IDENTITY_DISPATCH A,B`, owned by
#621/#622; this PR does not touch that source or claim aggregate acceptance.

## Independent review and remaining work

Fresh Goldfish used pinned Google EGM
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Its two original decoder Majors
(unexecuted supervision and stale module mirror) were repaired and re-audited.
Structural extraction/helper hygiene received independent source and exact old/new
artifact review. The final #635 reuse review found no Blocker/Major; its minor
B10.3 title was corrected to B10.5. This qualifies only the reviewed composition
and structural scope, not the independent #633/#634 acceptance gates.

Next: consume qualified #633/#634 receipts and any updates through their actual
owners, rerun affected proof, reconcile remaining parent B10/source/B11/C02
acceptance, and obtain human integration. IPR-0220 remains open. No actual student,
own AdamW, teacher, champion, checkpoint or human-run state changed.
