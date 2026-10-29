# A13.1 independent EGM source-authority review

Initial immutable target: `926385cbf7089a1bf1c7114ba55a210f7b008341`
Repair immutable target: `7895cea9b36e9b04ef085be2b0c3de4002cae257`
Reviewer: fresh-context Goldfish worker-4, read-only
Prime tests: `test_context_eligibility.py`, 14 passed, 0 failed, 0 skipped

The first review found a **Blocker**: live source grants were
associated with opaque handles but not with immutable frame/member
evidence. A caller could relabel revoked content under another live
handle and obtain an approved view. The failing-before test reproduced
that bypass.

The repair requires each source-owned grant to bind a semantic release
and canonical evidence digest. Frame evidence includes the complete
immutable frame and source lineage. Member evidence includes the
specific frame occurrence, full role binding and source reference,
plus the source-authorized visibility prefix. The gate rejects
duplicate handle reuse, evidence mismatch, revoked grants and
unobservable members before returning approved handles.

Independent targeted readback at `7895cea` found **zero remaining
Blockers or Majors**. The reviewer inspected the repaired source and
three discriminating negative tests: revoked-evidence relabelling,
source-reference substitution with unchanged semantic content digest,
and backdated visibility. The reviewer did not execute tests.

Disposition: **A13.1 EGM PASS**. This is not an A13 parent integration
or a grant of neural, source-release or merge authority.

## A13.2 independent approved-projection/source-admission review

Initial immutable target: `e959100c6b2f820c726cb6f73b86a2686eb704cb`.
First repair target: `25928fc295dae402c8e3d3a91c7d0d23ff5a708d`.
Final repair target: `f4245d5edf681467ff24c0854b47158a7cecec69`.
Reviewer: Goldfish worker-3 initial, worker-2 targeted readback;
both read-only. Prime context/adapter tests: 28 passed.

The initial review found one Blocker: first-admission
PUBLIC_FORMAL grants could be minted from a forged adapter
checker or caller-backdated span. The first repair pinned
the canonical source registry checker, source root and graph,
and derived the formal span from verified row tokens. The
targeted readback found one remaining Major: row ID/source_id
could be forged while the canonical checker still accepted
the record and tokens. The second repair requires exact
canonical source redraw with declared seed/count/profile
before admission, binding source identity as well as content.
Tests forge id/source_id on fresh A/B/C frontiers and reject.

Independent final readback at `f4245d5` returned
**A13.2 EGM PASS, zero remaining Blockers/Majors**.
The reviewer inspected immutable source and tests; 28/28
is prime executed evidence. A13.3 and parent integration
remain open, and no neural/optimizer or source promotion
was authorized.

## A13.3 independent C09 contextual invalidation review

Initial target `982ba51127b7e851cd795039644565bc3625ebaa`
consumed unified `6e83c0f`. Independent Goldfish
worker-5 executed the focused context suite from a
disposable immutable archive: 20/20 passed, but found
one Major. The new frozen C09 event and transition
records lacked constructor boundary validation and
accepted invalid digests, actor/scope, epochs, duplicate
handles/reasons and schema versions.

Repair `d23c5999e2783a99617871dc69a1484d764d7011`
added ErrorBus-backed validation for both records and
table-driven negative tests. The targeted independent
readback returned **A13.3 typed-record subreview PASS**,
zero remaining Blockers/Majors in that scoped check,
and independently executed 21/21 focused tests.
The separate full-issue fresh-context review on #432
also required purpose/jurisdiction/release isolation and
PR closing-link evidence. Those findings are being
reconciled before full-issue EGM PASS. C09 durable
outbox delivery, reverse
dependency propagation and Akasha routing remain
Lane C ownership. No live training or merge occurred.

The full-issue final re-review at immutable
`b3bea14fe241f5f11c68d11a41af3d938aebd8ae`
returned **A13.3 EGM PASS**, zero remaining
Blockers/Majors. Goldfish independently executed
21/21 context tests, verified cross-principal,
tenant, purpose, jurisdiction, semantic-release and
scope isolation, and confirmed both typed boundary
validators. PR #546's Development section contains
`Closes #432`; native GitHub
`closingIssuesReferences` readback returned #411
and #432. PR receipt comment 6487365093 is present.
Parent A13 remains open.
