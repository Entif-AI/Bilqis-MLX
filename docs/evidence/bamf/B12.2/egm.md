# B12.2 independent EGM

Pinned tool: Google Elephant-Goldfish Model
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
Reviewer: fresh-context native subagent `/root/b12_475_goldfish`, launched with
`fork_turns: none`. The reviewer confirmed reading codebase-details and
comprehension personas, implementation-readiness standard, issue packet,
target evidence, candidate/optimizer/plasticity/motif sources and moved tests.
The reviewer did not compile, edit or access session memory.

Initial review: two Majors, no reported Blocker.

1. Public transaction construction could inject arbitrary optimizer or motif
   proposals. The new adversary failed with `BilqisError not raised` before
   repair. Transaction construction/replacement now rejects; only private
   owner issuance from `begin_candidate` and `candidate_step` creates a handle.
   Each transition checks the process-local issuance marker. This is an
   internal Python API contract, not isolation from arbitrary private-module
   mutation or a serialized generation authorization.
2. The evidence document referenced separate receipts which did not exist.
   This file and `validation.md` now provide those declared receipts.

PM-2026-10-31-001 was filed and read back from the canonical native ledger at
recognition, before repair. Existing RC-139 / PAT-100 were reused; no new
Governance rule or abstraction was created. The incident concerns a contained,
uncommitted prototype with no production caller or actual student mutation.

Targeted independent re-review: SCOPED CLEAR, zero remaining Blocker/Major.
The fresh reviewer confirmed both repairs and the explicit internal-API boundary. This receipt does not grant #475
completion, B11/source mask authority, B13 publication or persistent training.
