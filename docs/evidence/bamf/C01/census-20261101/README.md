# C01 recursive child census repair — 1 November 2026

Consumed Lane C/unified: `70e37ae27214061dcc1712503eae6741a2e3781e`.

The census mistakenly interpreted owner-only follow-ups #637 and #641 as two
children named C10. Its key regex also accepted a partial prefix of malformed
nested keys. Separately, it could report `complete` when a registered key was
absent from the live search. These are executable census defects, not authority
to close C01 or to register guessed dependency contracts.

The repaired census requires a complete recursive child key and reports missing
registered keys as incomplete. Existing closed duplicate detection stays intact:
#587 remains visibly separate from canonical #586. No issue body, dependency,
registry baseline, architecture, learner state or quality threshold changed.

## Proof

- Four existing tests passed before repair.
- Three new regressions failed before repair: owner follow-up misclassification,
  malformed nested-key truncation, and false completeness with missing search data.
- Seven census tests plus 27 existing workstack validator tests pass after repair:
  34 passed, zero failures, zero skips.
- Run:
  `python3 -B scripts/run_tests.py scripts/tests/bamf/test_audit_child_registry.py scripts/tests/bamf/test_check_bamf_workstack.py`
- Live observation:
  `python3 -B scripts/bamf/audit_child_registry.py`
- Strict mode must return 1 for this observed incomplete registry; it must not
  suppress the real gaps merely to obtain a green audit.

The attached `live-audit.json` is an observation, not a new canonical registry.
The registered inventory remains 157. The live census has 172 matching child
issues, 15 missing issue records across 14 unique keys, and the acknowledged
B11.1a #586/#587 duplicate. Compared with the earlier 29 October observation,
#635 adds the B10.5 child and #559 now has the distinct C14.4 title. #636 is the
merged PR for issue #635, not a second issue to register. The census correctly
excludes owner-only structural follow-ups #637/#641 from child identity.

## Remaining work

C01 #347 remains open. Actual registry expansion must preserve all 14 canonical
child contracts, direct prerequisites, exact live-body fingerprints, mirrored
bodies and ancestry hashes. Short-format prerequisites need a lossless supported
representation; this patch does not guess them or rewrite upstream contracts.

The initial EGM_PENDING observation from reviewer-credit exhaustion is superseded
by fresh independent review of exact source776898fa. Reviewer
`/root/c679_review_fresh` read all four target files and the pinned EGM Codex,
Codebase Details and Comprehension standards at
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. No Blocker, Major or Nit findings.
The review was read-only and did not rerun tests or hosted checks. The scoped
census repair is acceptable; full C01 reconciliation remains open. Human review
and merge remain required.
