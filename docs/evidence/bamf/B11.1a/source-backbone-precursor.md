# B11.1a | Execution-owned backbone producer qualification

Issue #586; parent B11.1 #471; consumer B05.4 #577. IPR-0220 remains
governing. This receipt records implementation and local verification only. It
does not authorize live training, retained-generation publication, semantic
promotion, or self-merge.

## Intake and source authority

Lane B consumed reviewed unified `77a05ef00337e8a3773d070adad4c8874c9c1034`.
The current repair wave descends from execution-replay checkpoint
`f0dd9ddeb5b374f6038b8de350b26cc56ea7e347` and the later receipt-authentication
checkpoint `ed647441a3346cddae537e8ea1a1e012403c14ff`. The final feature SHA for this
repair is recorded only after commit and remote verification; this document does
not promote the uncommitted working tree into a checkpoint identity.

A05.5 #594 is accepted through PR #618. Reproducing its source chain yields
source bundle `f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`,
Atlas bundle `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`,
and semantic release `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`.
The conformance reproduction passes all four source gates.

## Producer contract

`start_source_backbone_producer` replays and revalidates the actual source rows,
derives h0 through the accepted source encoder, and owns the subsequent fixed
B01/B04 numerical execution. Receipt issuance independently replays the same
source authority and exact numerical boundary before materializing the boundary
evidence; a Python producer-shaped object or mutable numerical result is not
itself proof.
Callers provide the authoritative source selection and B01 parameter state; they
cannot provide h0/g1/g2/g3 bytes, a generation label, prefix digest, group number,
predecessor result, cache-chain digest, or hidden digest as producer credentials.

Every `ProducedBackboneBoundary` binds the verified source-handoff closure,
B01 topology, a staged execution-generation identity derived from topology plus
the complete declared BAMF parameter tree, exact parameter-tree content digest,
compiled prediction-prefix digest, execution scope/input/output digests,
cache-chain digest, numerical execution digest, ordered predecessor receipt,
source id, completed layer, and boundary-transform disposition. Before a receipt
can participate in production B05 selection, source encoding and group execution
are replayed from the authoritative producer inputs and exact-compared to the
presented boundary evidence. No HMAC, secret process token, issued-object registry,
Python object identity, or caller-computed hidden digest is an authority source.
Receipts are evidence objects; the execution-owning producer and deterministic
replay are the authority boundary.

The receipt order is `h0,g1,g2,g3`. Group 1 records the explicit
`NO_HIT_QUARANTINED` disposition at `AFTER_LAYER_4_BEFORE_CAPTURE` and binds that
honest quarantine witness to the source, prefix, execution generation and actual
group-1 execution digest. It does not claim an authorized B08 hit while upstream
B08 source authority remains quarantined. Groups 2 and 3 record
`NOT_APPLICABLE`.

The public `depth_select` / `depth_select_with_diagnostics` path accepts the
execution-owning producer, not a caller-supplied receipt tuple. It independently
rederives the exact receipt prefix for the requested boundary and computes from
the replayed terminal hidden state; callers cannot make a detached same-byte tensor
authoritative by embedding it in structurally matching receipt evidence. It verifies
that its `DepthParameterView` represents the same complete parameter tree and
execution-generation identity, and that the ordered producer chain is
source/topology/prefix/tree consistent. Completed group captures are RMS-normalized
before B05 selection. The selected g1 state is the actual g2 execution input and
the selected g2 state is the actual g3 input. Naked-summary selector math remains
private test/numerical support only.

This issue deliberately does not claim final B13 retained-generation custody.
The staged execution-generation digest is content-derived from the B01 topology,
the complete current parameter tree, and the exact `GenerationExtents.digest`.
This is an execution identity, not a claim of final B13 retained-generation
custody. Issue #586 explicitly permits this leaf to proceed without waiting for
final B13 custody; later retained-generation publication must compose with this
producer rather than retroactively fabricate custody here.

## Adversarial proof

The real-source acceptance tests prove:

- literal twelve-layer execution and ordered group boundaries;
- nonzero gradients from public B05 selection through the produced group state
  into executed backbone parameters and source identity rows;
- revoked source, changed source tokens and incomplete B01 state reject before
  producer execution;
- caller hidden/generation/prefix injection is outside the producer API;
- a fabricated exact-class producer shell with a substituted numerical session and
  arbitrary group bytes cannot mint a receipt because issuance replays source and
  numerical execution independently;
- g2 cannot be relabelled as g1 or substituted into the g1 selector chain;
- g2 and g3 consume the preceding B05-selected state, not the raw prior capture;
- changes outside `blocks.*` (including identity rows) change the complete
  parameter-tree and execution-generation identities;
- two B01-compatible trees with identical extents cannot share receipts or a B05
  parameter view, and different generation extents cannot share execution identity;
- test-only mutation of generation, prefix or cache-chain identity rejects before
  B05 selector computation;
- a copied receipt whose public content digest is recomputed still fails the live
  producer replay/exact-comparison check after any relabel/tamper;
- a receipt tuple is not a production B05 credential at all; the selector requires
  the execution-owning producer and independently rederives its boundary prefix;
- same-valued detached hidden bytes embedded in receipt evidence do not seize B05
  graph custody: B05 computes from replay-derived hidden state and gradients still
  reach executed backbone parameters;
- the public B05 API has no caller-supplied `current` credential;
- group 1 can only report the explicit quarantined no-hit disposition while B08
  source authority remains unavailable; it cannot fabricate an authorized hit;
- public B05 output matches the accepted normalized-capture numerical oracle;
- public B05 rejects anonymous/naked depth summaries and preserves exact source
  order with no future-group admission.

## Verification

With the pinned A01 Atlas bundle mounted, source encoding, numerical backbone,
producer receipts and source-bridge custody pass 26/26 tests with zero skips. The
current backbone/depth selection passes 21/21 tests with zero skips.
Development-structure and governance checks report zero violations; factory
architecture and documentation checks pass; base-aware error control reports
`new debt 0`; `git diff --check` is clean. During review, the new receipt/depth
owners crossed the repository structure threshold; the feature task was preserved
in Work Stack, the production/test owners were split along receipt/selection
boundaries, and every resulting owner is below 240 LoC before feature work resumed.

Independent non-EGM adversarial review repeatedly attacked receipt minting,
selected-state chaining, generation/extents identity, detached B05 current,
caller-supplied motif context, copy/re-hash forgery, fabricated Python producer
state, and the authority mechanism itself. The exact `ed647441...` review found
one Blocker and zero Majors: both issuance and verification shared a closure-held
HMAC key that ordinary in-process Python introspection could recover, allowing an
attacker to sign fabricated receipt contents without producer replay. The repair
therefore removes the HMAC/token authority entirely and makes production B05
rederive and exact-compare the authoritative producer execution before using the
boundary. This non-EGM review is defect-discovery evidence only and never
substitutes for the pinned Google EGM gate below. A fresh non-EGM pass is still
required on the final committed repair head because the reviewed code changed.

No actual student, native AdamW, teacher, checkpoint, retained source release,
admission lease, human-run state or live training process was modified.

## Remaining integration gate

Issue #586 requires a fresh independent Google EGM review with zero
Blockers/Majors before integration and before B05.4 #577 removes its public
fail-closed hold. The current ChatGPT execution surface exposes no Google EGM
runner, so this receipt does not claim that review. Additional non-EGM read-only
review may improve defect discovery but cannot satisfy the pinned EGM requirement.
