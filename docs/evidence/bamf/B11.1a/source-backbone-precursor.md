# B11.1a | Execution-owned backbone producer qualification

Issue #586; parent B11.1 #471; consumer B05.4 #577. IPR-0220 remains
governing. This receipt records implementation and local verification only. It
does not authorize live training, retained-generation publication, semantic
promotion, or self-merge.

## Intake and source authority

Lane B consumed reviewed unified `db85d745c2202d6813361ffecf7562f548d41bec`.
The producer implementation checkpoint is `604d2ee9be9fa61ae4758399ffc74eba9291bb28`;
the current authority-hardening checkpoint is
`d2bb818f8852b384aa969db9c46d5165715e2b0f`.

A05.5 #594 is accepted through PR #618. Reproducing its source chain yields
source bundle `f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`,
Atlas bundle `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`,
and semantic release `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`.
The conformance reproduction passes all four source gates.

## Producer contract

`start_source_backbone_producer` replays and revalidates the actual source rows,
derives h0 through the accepted source encoder, and owns the subsequent fixed
B01/B04 numerical execution. Callers provide the source selection and B01
parameter state; they cannot provide h0/g1/g2/g3 bytes, a generation label,
prefix digest, group number, predecessor result, cache-chain digest, or hidden
digest as producer credentials.

Every `ProducedBackboneBoundary` binds the verified source-handoff closure,
B01 topology, staged execution-generation/extents identity, exact parameter-tree
content digest, compiled prediction-prefix digest, execution scope/input/output
digests, cache-chain digest, numerical execution digest, ordered predecessor
receipt, source id, completed layer, and boundary-transform disposition. The
internal constructor seal is only an issuance guard; B05 independently
revalidates the receipt contents and canonical receipt digest before selector
math.

The receipt order is `h0,g1,g2,g3`. Group 1 records the declared post-layer-4,
pre-capture motif position as `AFTER_LAYER_4_BEFORE_CAPTURE` with disposition
`NO_HIT_QUARANTINED`. This is an honest fail-closed disposition while upstream
B08 hit authority remains quarantined; it does not fabricate a motif hit.
Groups 2 and 3 record `NOT_APPLICABLE`.

The public `depth_select` / `depth_select_with_diagnostics` path accepts only the
execution-owned producer receipt chain. The former naked-summary math is retained
only under the explicit `numerical_depth_select*` helpers for bounded numerical
verification. The older `admit_compiled_backbone_producer` stub has been removed,
leaving one production producer authority. Historical source-bridge helpers remain
numerical/fail-closed and cannot mint producer receipts.

This issue deliberately does not claim final B13 retained-generation custody.
`compiled.extents.digest` is the execution-observed staged generation binding at
this bounded producer seam. Issue #586 explicitly permits this leaf to proceed
without waiting for final B13 custody; later retained-generation publication must
compose with this producer rather than retroactively fabricate custody here.

## Adversarial proof

The real-source acceptance tests prove:

- literal twelve-layer execution and ordered group boundaries;
- nonzero gradients from public B05 selection through the produced group state
  into executed backbone parameters and source identity rows;
- revoked source, changed source tokens and incomplete B01 state reject before
  producer execution;
- caller hidden/generation/prefix injection is outside the producer API;
- g2 cannot be relabelled as g1 or substituted into the g1 selector chain;
- two B01-compatible trees with identical extents receive distinct parameter and
  execution identities and cannot share receipts;
- test-only mutation of generation, prefix or cache-chain identity rejects before
  B05 selector computation;
- the producer constructor seal is not retained as a dataclass field and ordinary
  `dataclasses.replace` cannot silently preserve issuance authority;
- public B05 rejects anonymous/naked depth summaries and preserves exact source
  order with no future-group admission.

## Verification

With the pinned A01 Atlas bundle mounted, the source/producer package passes
14/14 tests with zero skips. The current backbone/depth selection passes 21/21
tests with zero skips. Development-structure and governance checks report zero
violations; factory architecture and documentation checks pass; base-aware error
control reports `new debt 0`; `git diff --check` is clean.

No actual student, native AdamW, teacher, checkpoint, retained source release,
admission lease, human-run state or live training process was modified.

## Remaining integration gate

Issue #586 requires a fresh independent Google EGM review with zero
Blockers/Majors before integration and before B05.4 #577 removes its public
fail-closed hold. The current ChatGPT execution surface exposes no Google EGM
runner, so this receipt does not claim that review. Additional non-EGM read-only
review may improve defect discovery but cannot satisfy the pinned EGM requirement.
