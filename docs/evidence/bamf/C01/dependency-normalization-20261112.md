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
