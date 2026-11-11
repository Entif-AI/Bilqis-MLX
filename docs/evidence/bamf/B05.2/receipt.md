# B05.2 scoped boundary candidate

Issue #450, parent #355. Status: NUMERICAL_PROOF_ONLY; SCOPED_EGM_PASS.

Reviewed unified baseline: 7ad8f8a. Lane B source: ae08c4a.
Candidate branch: codex/bamf02-b05-2-20261029.

The private numerical helper executes three group boundaries. At group
one it captures normalized g1 after the second motif-read fixture.
Each group applies the rank-eight B01 adapter after depth selection.
Future groups are not visible to earlier selectors. Public optional
alpha diagnostics use the existing A13/B02 source-feature and B01
parameter views; the tensor-returning depth_select API is unchanged.

The B01 tensor ledger already owns four shared selector projections
and three boundary gate vector/bias pairs. No second parameter registry
or new trainable tensor was introduced.

Focused MLX tests: 19 passed, 0 failed, 0 skipped. Git diff check
passed. Module-size check retains three inherited unrelated findings.

Unclosed: B08 must issue a source-authorized motif read; B11 must bind
real backbone capture and causal summaries; B13 must prove checkpoint
roundtrip; B05 source-summary authority and parent integration remain
open. The numerical callback is private and not source permission.
No live student, optimizer, source release or integration merge changed.

## Independent review

Fresh-context Goldfish worker-19 reviewed immutable code head
`cb22592c7bf07494b865152cf7dd3f1255926bb9` and returned
**EGM PASS, zero Blockers/Majors for the scoped numerical/diagnostic
claim**. It independently checked the issue and direct source
contracts, boundary ordering, sealed B01 parameter identities,
negative tests and the explicit source-integration exclusions.
The reviewer ran `git diff --check` successfully but could not
execute tests in its isolated environment because rdflib was missing.
The 19/19 focused and 59/59 combined MLX totals are prime-run
evidence, not a second Goldfish execution.

## Final integrated closeout — 2026-11-10

The opening `NUMERICAL_PROOF_ONLY` status above records the original 2026-10-29
scoped candidate and remains historical provenance. It is no longer the current
integration disposition.

Issue #450 is now technically complete on reviewed unified
`4d7599086c2aed283a25ac24f6cc35271f4dc9ce`. The original B05.2 candidate
`eef9ed83dba729c7d1095537c1e33cea93c0f955` is an ancestor of current unified,
and the source/custody seams that were intentionally deferred by that candidate
have since landed through their owning issues.

### Integrated authority closure

- B05.1 prerequisite #449 is closed and integrated.
- The real retained B11 producer executes B08 site 1 after layer 4 and before the
  g1 boundary capture; source-owned g1 receipts record the retained motif result.
- B05.2a #863 / merged PR #981 proves the production source producer applies the
  existing B01 rank-8 adapter after boundaries 1 and 2 and applies the third
  adapter to the final boundary result without executing a fourth backbone group.
- B05.3 #451 proves the B01 ledger owns one singular set of shared selector
  projections plus three distinct gate vector/bias pairs and that B13 cold custody
  round-trips parameters, moments, update counts, diagnostics, and selector output.
- B08.2 #461 supplies the integrated retained placement/reporting witness. The
  broader B11/B13 parents may retain unrelated aggregate work; their OPEN state is
  not a blocker for these exact B05.2-owned seams.
- Public diagnostics expose generic `output`, `alpha`, and `gate` observations
  without assigning fixed cognitive functions to layers.

No second parameter registry, checkpoint owner, source grant, motif authority,
optimizer authority, or production neural implementation is introduced by this
closeout.

### Exact-head requalification

On exact reviewed-unified head `4d7599086c2aed283a25ac24f6cc35271f4dc9ce`:

```text
runtime/tests/depth/test_block_attnres.py
2 passed, 0 failed, 0 skipped

learning/source_atoms/tests/test_backbone_source_adapters.py
learning/source_atoms/tests/test_backbone_retained_motif.py
6 passed, 0 failed, 0 skipped

runtime/tests/depth/test_selector_custody.py
1 passed, 0 failed, 0 skipped
```

The real-A01 run used both `BILQIS_A01_ATLAS_BUNDLE` and
`BILQIS_ATLAS_REAL_ARTIFACT` bound to the pinned bundle identity
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`.
The selector-custody witness ran with `BILQIS_BAMF_FULL_WITNESS=1`.

Repository guards on the same head:

```text
BAMF contract mirrors: 43/43 exact mirrors and API/acceptance fields PASS
B05 owner-mirror reconciliation: no-op
Governance integrity: 0 violations
Factory architecture: OK
Semantic boundaries: OK
BAMF flow control: OK
```

Independent read-only integrated audit of exact head `4d759908` found
0 Blockers / 0 Majors. Its sole Nit was this stale historical receipt, repaired by
this append-only closeout. No production-code change is required for #450.
