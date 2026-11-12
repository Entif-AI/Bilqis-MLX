# C01 dependency normalization follow-up — 12 November 2026

Issue: #347 (`BAMF-0.2 C01`)

Reviewed-unified base: `009263acb78662f9933469ebf9f666722c1c7679`

This follow-up preserves the 1 November rule: dependency edges are not guessed and
implementation closure is not treated as complete dependency normalization. It
changes only a hold whose original unresolved condition has now acquired exact
accepted evidence.

## B13.6 changed condition

B13.6 #904 already declares exactly two direct issue prerequisites in its immutable
body: B13.1 #478 and B13.4 #481. The 1 November evidence packet kept B13.6 held
because the required accepted B13.1 receipt did not yet exist. That condition has
changed without changing the issue body or its dependency meaning:

- B13.1 PR #885 is MERGED, head
  `f166cac5db1e217880ce706efb51408001c7231e`, merge
  `9301e41ef215b9d035449c3260c7cd0f8ee0b5a7`.
- B13.4 PR #802 is MERGED, head
  `4e19623217b20a79f38ba30e79dfc14294171740`, merge
  `05e31a576e3432e4238c9b4477a70d70ec4fc487`.
- Both prerequisite issues are CLOSED after accepted integration, and B13.6 itself
  later completed its own bounded acceptance. The latter is not used as proof of
  the prerequisite edges; it only confirms no later B13.6 amendment superseded
  the declared prerequisite contract.

The canonical dependency-evidence record now retains exact snapshots of PR #885 and
PR #802 as source evidence. They are provenance for the previously missing accepted
receipts; they are not new graph nodes. The known issue edges remain exactly
`B13.1,B13.4`.

## Parser scope

The dependency grammar gains one narrow, issue-specific form: the exact immutable
B13.6 `## Direct prerequisites` clause already present in #904. It validates the
canonical issue numbers for B13.1 and B13.4 and rejects any textual variation; it
does not introduce a general bullet parser, interpret descriptive prose, or infer
prerequisites from closure.

## Remaining holds

This increment does not alter A03.4, A05.4, A05.5, A08.1b.2, A08.1b.5, B02.4 or
B11.1a. Their source/specification/receipt-granularity questions remain held until
each is resolved against its own controlling evidence.

## Independent review repair

Two fresh read-only reviewers independently found the same two material defects in
the first candidate. First, a generic bullet-prefix parser could accept ambiguous
or negated prose while silently ignoring an additional issue-shaped prerequisite.
Second, the retained PR snapshots were source-hash checked but not passed through
the dependency receipt validator, so their MERGED/head/merge fields were not
mechanically enforced.

The repair removes the generic bullet grammar. The parser now accepts only the exact
B13.6 direct-prerequisite clause already present in its immutable issue body, with
canonical issue-number lookup for B13.1 and B13.4. Tests reject a forged issue
number, a same-line hidden second prerequisite, negation, and a second bullet block.
PR #885 and #802 are now also registered in `external_receipts` as implementation
receipts for the prerequisite-owner implementations. That makes `_receipts` verify
their number, MERGED state, URL, head SHA and merge SHA while leaving the parsed
issue-edge set unchanged.

A pinned EGM comprehension pass found one further causal-binding gap: merely
validating #885/#802 when present did not make them mandatory for B13.6 resolution.
The exact B13.6 clause grammar now returns both issue edges and required PR receipt
numbers `(885, 802)`. Those records use the existing `prerequisite` receipt role,
which remains receipt provenance rather than an issue-graph node. A regression
removes both receipts from an otherwise exact packet and requires `INVALID`.

## A03.4 changed condition

A03.4 #578 names one issue-graph prerequisite, A01, and separately requires
**accepted A03/A04 schema serialization**. Treating A03 or A04 parent identity as a
new graph edge would manufacture semantics and can create parent/child cycles.
Merged PR #551 is the accepted serialization integration receipt. Its reviewed Lane A cut is rooted at `fadbe684...`, which contains the final reviewed A03.1/.2/.3 and A04.1/.2/.3 repair/evidence commits before the cut entered reviewed unified. The original leaf receipts and EGM outcomes remain preserved in that ancestry.

PR #551 is pinned at head `fadbe684140220776f906627a1c4ec28b41ba216`
and merge `6b5460032fc0b19115843cce95fe8be9582af141`. The exact A03.4
handoff clause now resolves to issue edge `A01` plus required receipt `#551`.
B07.1/B08.1 remain downstream consumers and A13 remains an independent authority;
none is promoted to a direct prerequisite by this normalization. Removing #551 or
changing the exact clause fails closed.

Pinned EGM codebase review rejected an earlier draft that used PR #546: the A03/A04 repair/evidence commits were already ancestors of #546's base, so #546 inherited rather than accepted them. The candidate was corrected to the causal reviewed-unified integration PR #551 before commit.

## A05.4 changed condition

A05.4 #575 declares direct dependencies on A03, A04 and A13, plus a separate
requirement to consume **current A05 compiler receipts**. B03.3 #444 is named only
as the downstream consumer that must rerun its proof after A05.4, so it is not
promoted to a prerequisite.

The compiler condition is causally bound to the implementation receipt, with the later parent audit retained as corroboration:

- PR #546, head `74be2874bd6a4f4163878ebc547e2cfabde890e4`, merge
  `ac498099b56a38f3b669e16d30f8bab580709f49`, contains the final reviewed A05.1-.3
  compiler code including the source-grant repair at `de5bb9c...`.
- PR #571, head `eec0e4323d1535173361d786fc4611135a8043ae`, merge
  `7d88957bf9dd48eb0e6e18428c17d3080dc1df31`, is retained as non-gating
  corroboration: it is explicitly a documentation-only independent A05 parent
  acceptance crosswalk over code that was already in reviewed unified.

The exact A05.4 handoff clause therefore resolves to graph edges `A03,A04,A13`
plus required receipt `#546`. Removing #546 fails closed. Removing the #571 audit
source does not change resolution, because the audit did not land the compiler.
Neither source creates an A05 parent edge or turns B03.3 into a prerequisite.

## A08.1b.2 changed condition

A08.1b.2 #554 already names the complete issue-graph prerequisites
`A08.1a,A07.1,A07.2,A13`. Its checked-in child specification adds one narrower
turn-in obligation: consume an **A13.1 receipt**. That receipt is now pinned without
changing the graph.

A13.1 #430 reached reviewed implementation and independent EGM PASS at
`7895cea9b36e9b04ef085be2b0c3de4002cae257`. PR #551 did carry those bytes into
reviewed unified as part of an explicitly historical A07.3 cut, but it was not the
A13.1 integration authority: #430 closed after #551 had already merged and still
recorded A13 parent/downstream integration, draft PR #546, and human merge approval
as outstanding. PR #546 later merged with an explicit `Refs #430` entry naming the
A13.1 repair and final review receipt. Its head is
`74be2874bd6a4f4163878ebc547e2cfabde890e4`; merge
`ac498099b56a38f3b669e16d30f8bab580709f49`.

The exact #554 body clause therefore resolves to the four existing issue edges plus
required receipt `#546`. Removing #546 or changing the clause fails closed. PR #551
remains useful ancestry evidence, but it is not substituted for the issue-scoped
acceptance/integration receipt. The receipt supplies the named A13.1 granularity; it
does not replace the broader A13 issue edge with an A13.1 graph edge.

## B02.4 changed condition

B02.4 #576 already declares issue edges `B01,A05.4` and separately requires
**actual A05 compiled child handles**. The missing handle receipt is now identified
without adding an A05 parent edge.

PR #546 is the causal compiler integration: its head contains A05.1
`CompiledPosition.frame_handle`, A05.2 `ExpansionHandle` / `PrefixMaps` occurrence
and content bindings, and the final A05 source-authority repair `de5bb9c...`; merge
`ac498099b56a38f3b669e16d30f8bab580709f49` lands those interfaces. A05.4 is a
separate validator over an already accepted `CompiledFrameBatch`. Its reviewed
cross-lane integration PR #592 (merge `c3fab66c5da2d20704a7aeb6cd80def07337bce6`)
is retained as corroboration for the existing A05.4 graph edge, but it inherited
the compiled handles from #546 and is not the missing handle receipt.

The exact #576 handoff clause therefore resolves to issue edges `B01,A05.4` plus
required receipt `#546`. Removing #546 or changing the exact clause fails closed;
removing the #592 corroborative source does not change the dependency meaning.
B03.3 remains a downstream consumer, not a prerequisite.

## B11.1a changed condition

B11.1a #586 is intentionally cycle-breaking. Its immutable dependency-cycle rule
consumes B01, B04 and the **already-implemented B05 numerical selector contract as
a downstream numerical operation**, while explicitly forbidding B05.4 provenance
acceptance and final B13 custody as prerequisites. A later source-owner amendment
adds A05.5 #594 and states exactly that #594 must reach unified before #586 producer
acceptance.

The B05 numerical receipt is PR #552, not later PR #780. PR #552 merged as
`d486b33a178cf868374cfeb3a78ec15103525975` and contains the existing B05.1
numerical selector plus its source-feature repair while deliberately retaining the
summary-origin provenance Major. That is precisely the contract #586 was carved
out to consume and then repair with execution-owned producer provenance. PR #780
merged only after accepted B11 producer integration and explicitly references
#586/#577; requiring it would invert the dependency and recreate the cycle.

The evidence clause remains the exact #586 dependency-cycle body. Resolution also
requires pinned source record `B11.1a.comment-6505193864`, whose source-owner
amendment names A05.5 #594 and requires it to reach unified before #586 producer
acceptance. The packet resolves to issue edges `B01,B04,A05.5` and requires receipts
`#552,#618`. PR #618 is the
already-pinned accepted A05.5 source-ingress receipt. Removing either receipt, removing the pinned amendment source, or changing the
cycle clause fails closed. No B05, B05.4 or B13 graph edge is added.

## Remaining deliberate holds after this pass

Six of the eight 1 November C01 dependency holds now have exact source-backed
normalization. Two remain held deliberately; neither may be cleared from issue
closure or implementation references alone.

### A05.5 #594

No canonical source declares a complete direct inbound prerequisite list. The
issue body and checked-in spec describe A01 semantic identity, A13 rights and
corrections, B01-derived B02/B03 embedding behavior, inherited A05/A03/A04
requirements, and downstream B11/B05.4 consumers, but they do not classify those
references into a complete direct-edge set. Accepted PR #618 proves the
implementation and source-owner result; it does not establish the missing graph
semantics. Preserve `known_edges=[]` as unknown, not as an assertion of zero
prerequisites.

### A08.1b.5 #557

The issue body explicitly names A08.1b.1-.4, but the checked-in specification also
requires the A08.1a frozen census and a source-owner program spanning exact row
bytes, released SKOS/Ithkuil-to-A03 frame adaptation, per-edge relation evidence,
A13 grant issuance, and a fresh ApprovedContextProjection crosswalk. Those
obligations were intentionally surfaced by independent review and are not mapped
to one canonical direct-prerequisite edge set. PR #657 proves the owned
constructive-family implementation; it does not retroactively classify the missing
source-owner dependency graph. The range therefore remains held until authority
normalizes those additional obligations explicitly.

With either hold present, C01 correctly retains `order=[]`. This follow-up does not
claim #347 complete.
