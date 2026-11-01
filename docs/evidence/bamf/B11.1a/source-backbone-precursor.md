# B11.1a | Execution-owned backbone producer qualification

Issue #586; parent B11.1 #471; consumer B05.4 #577. IPR-0220 remains
governing. This receipt records implementation and local verification only. It
does not authorize live training, retained-generation publication, semantic
promotion, or self-merge.

## Intake and source authority

Lane B consumed reviewed unified `db85d745c2202d6813361ffecf7562f548d41bec`.
The producer implementation checkpoint is `604d2ee9be9fa61ae4758399ffc74eba9291bb28`;
the structural ownership checkpoint is
`68e8524105d754f61b142e234bef62c4e25aecfc`; and the current live-authority
hardening checkpoint is `65b50ea4949d0f0e36d2604faa67fb51d93186d9`.

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
B01 topology, a staged execution-generation identity derived from topology plus
the complete declared BAMF parameter tree, exact parameter-tree content digest,
compiled prediction-prefix digest, execution scope/input/output digests,
cache-chain digest, numerical execution digest, ordered predecessor receipt,
source id, completed layer, and boundary-transform disposition. A live
producer-issued capability registry is required in addition to those
execution-derived contents; the registry is an issuance check, not a substitute
for provenance. B05 independently revalidates the receipt contents and requires
the exact producer-issued object before selector math.

The receipt order is `h0,g1,g2,g3`. At group 1 the producer executes B08's
existing guarded read at the actual post-layer-4/pre-capture tensor using the
current source/rights policy, Atlas selection, execution-generation identity and
full parameter-tree identity. Only the source-qualified
`QUARANTINED_NO_HIT`/`MISS` result is accepted. Its dispositions and context/cache
witnesses are folded into `motif_read_digest`, then the producer records the
external disposition `NO_HIT_QUARANTINED` at
`AFTER_LAYER_4_BEFORE_CAPTURE`. A held or hit-like B08 disposition fails closed.
Groups 2 and 3 record `NOT_APPLICABLE`.

The public `depth_select` / `depth_select_with_diagnostics` path accepts only the
execution-owned producer receipt chain. It verifies that its `current` tensor is
the terminal produced boundary, that its `DepthParameterView` represents the same
complete parameter tree and execution-generation identity, and that the ordered
producer chain is source/topology/prefix/tree consistent. Completed group captures
are RMS-normalized before B05 selection, matching the accepted B05 numerical
contract. Naked-summary selector math is private test/numerical support only. The
older `admit_compiled_backbone_producer` stub has been removed, leaving one
production producer authority. Historical source-bridge helpers remain
numerical/fail-closed and cannot mint producer receipts.

This issue deliberately does not claim final B13 retained-generation custody.
The staged execution-generation digest is content-derived from the B01 topology
and complete current parameter tree. It intentionally does not equate one
source-local feature manifest with the model generation and does not claim B13
retained custody. Issue #586 explicitly permits this leaf to proceed without
waiting for final B13 custody; later retained-generation publication must compose
with this producer rather than retroactively fabricate custody here.

## Adversarial proof

The real-source acceptance tests prove:

- literal twelve-layer execution and ordered group boundaries;
- nonzero gradients from public B05 selection through the produced group state
  into executed backbone parameters and source identity rows;
- revoked source, changed source tokens and incomplete B01 state reject before
  producer execution;
- caller hidden/generation/prefix injection is outside the producer API;
- g2 cannot be relabelled as g1 or substituted into the g1 selector chain;
- changes outside `blocks.*` (including identity rows) change the complete
  parameter-tree and execution-generation identities;
- two B01-compatible trees with identical extents cannot share receipts or a B05
  parameter view;
- test-only mutation of generation, prefix or cache-chain identity rejects before
  B05 selector computation;
- a copied receipt whose public content digest is recomputed still fails the live
  producer-issued capability check;
- foreign `current` bytes reject before B05 selector computation;
- B08 rights revocation is re-evaluated at the actual group-1 read and fails
  producer issuance;
- public B05 output matches the accepted normalized-capture numerical oracle;
- public B05 rejects anonymous/naked depth summaries and preserves exact source
  order with no future-group admission.

## Verification

With the pinned A01 Atlas bundle mounted, source encoding, numerical backbone,
producer receipts and the guarded B08 read pass 19/19 tests with zero skips. The
current backbone/depth selection passes 21/21 tests with zero skips.
Development-structure and governance checks report zero violations; factory
architecture and documentation checks pass; base-aware error control reports
`new debt 0`; `git diff --check` is clean. During review, the new receipt/depth
owners crossed the repository structure threshold; the feature task was preserved
in Work Stack, the production/test owners were split along receipt/selection
boundaries, and every resulting owner is below 240 LoC before feature work resumed.

An independent non-EGM adversarial review found four authority Blockers and two
Majors in the first implementation: copy/re-hash forgery, unbound B05 `current`,
decorative rather than executed B08 disposition, partial parameter-tree identity,
foreign B05 view acceptance, raw rather than normalized B05 captures, and public
numerical selector helpers. The code checkpoint above addresses each finding; a
second pass over that exact repair is required before this additional review can
be called clean.

No actual student, native AdamW, teacher, checkpoint, retained source release,
admission lease, human-run state or live training process was modified.

## Remaining integration gate

Issue #586 requires a fresh independent Google EGM review with zero
Blockers/Majors before integration and before B05.4 #577 removes its public
fail-closed hold. The current ChatGPT execution surface exposes no Google EGM
runner, so this receipt does not claim that review. Additional non-EGM read-only
review may improve defect discovery but cannot satisfy the pinned EGM requirement.
