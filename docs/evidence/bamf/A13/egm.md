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
