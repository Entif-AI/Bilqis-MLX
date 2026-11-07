# C03 true teacher-visit identity checkpoint — 2026-11-07

## Scope

This scoped C03 integration repair defines the true teacher-visit identity required by B06 refinement determinism. It does not reopen completed C03 children, does not mint run authority, and does not reinterpret `run_id`, `episode_id`, or `optimizer_step_seed` as the B06 seed/visit contract.

## Exact identity

- reviewed unified consumed: `bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`
- preserved branch: `codex/bamf02-c03-376-20261107`
- synced merge checkpoint: `c3297ec4ba4d8c4a91a1bc2757d49c7d8ba27ec1`
- visit-identity implementation: `ee8c6ef916826be2b991294371ee55e3211f3ba1`

## Owner contract

`TeacherVisitIdentity` is a deterministic C03 identity record, **not** an authorization capability. It binds:

- authenticated B13 run-identity digest,
- exact integer operator `run_seed`,
- accepted generation and manifest digest,
- C03 teacher identity and epoch,
- current retained student identity,
- C03-persisted selection seed and cursor,
- selected capability and policy key.

`derive_teacher_visit_identity(...)` does not accept caller-supplied teacher/student/selection seed/cursor values; those are read from the validated C03 teacher-state custody projection. `record_teacher_visit_identity(...)` only records the identity when it is exactly derivable from that current state. A rewritten selection seed therefore cannot be recorded even if a caller recomputes a syntactically valid identity digest.

The optional `last_visit` record is backward-compatible with historical teacher state. On the same teacher epoch it must match the active teacher/student. After an accepted student/teacher epoch advances, the prior visit remains historical evidence and cannot claim authority over the new epoch.

## Proof

Exact-head M3 snapshot at `ee8c6ef9...`:

- focused C03 teacher-lineage + visit-identity suite: **9/9 PASS** in 0.062s.
- deterministic visit identity uses persisted `next_seed=42` and `cursor=lesson:7` in the fixture;
- run seed, run identity, generation, accepted manifest, capability and policy changes all change the visit ID;
- rewritten selection seed rejects at C03 recording boundary;
- accepted teacher successor preserves the prior visit as historical evidence while advancing next seed/cursor.

Repository/static gates:

- `quality:changed`: PASS after repairing stale C03 legacy-trainer provenance;
- zero new changed-file smell findings;
- legacy-trainer static check + 6 tests: PASS;
- flow-control + 15 tests: PASS;
- module-size: zero violations;
- `git diff --check`: clean.

The local workstation could not import the focused test because `rdflib` is absent; no test body ran there. The exact-head M3 result above is the execution proof.

## Remaining authority boundary

C03 is not merge-ready until B13.6/#904 run identity arrives through reviewed unified. The current owner contract intentionally accepts the frozen upstream run-identity digest/seed interface without importing a sibling branch. After #904 is accepted, C03 must wire this derivation at the real visit-selection event and B13.2 must persist/cold-resume the resulting record. C02 then transports both `run_seed` and `visit_id` as separate provenance to B11.1.

No fresh EGM or PR is justified while that reviewed dependency is absent.
