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
