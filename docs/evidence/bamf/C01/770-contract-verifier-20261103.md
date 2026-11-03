# C01 #770: accepted late-child contract verification

As of 2026-11-03, this bounded tooling repair consumes reviewed unified
`aa828eb5cb8822a5614aa3353864bf187f83444d` on
`codex/bamf02-c-770-contract-verifier-20261103`. The feature starts from Lane C's
remote integration branch and merges unified; the separate local Lane C worktree
and its unpublished commits are preserved.

## Observations and repair

The actual baseline verifier exits 1 with fourteen failures: seven legitimate
late-child mirrors lack the original generator's marker, and seven owner dispatch
lists contain accepted late children absent from that historical generator.

The verifier now uses the existing `workstack_dependencies` source-evidence
checker for the pinned late-packet form and the existing `validate_workstack`
owner for registry integrity. A generated packet still requires its exact marker.
A marker-free packet requires its pinned matrix, exact body/source hashes,
identity, parent, dependency clause and evidence records. A held packet can have
valid provenance without acquiring scheduling authority.

Direct dispatch must equal the canonical registry in order, retain the original
source partition in order, contain no duplicates, and add only independently
pinned later children. The historical source-clause coverage check remains.
The reported specification count derives from 43 owners plus 171 children rather
than the stale literal 200.

No mirror, registry, issue map, dependency evidence, body fingerprint, source
contract, dependency edge or normalization hold changes. Live native GitHub
readback of all fourteen affected child/owner bodies matches their exact pinned
SHA-256 values.

## Reproduce

```sh
python3 -B scripts/verify_bamf_0_2_contracts.py
python3 -B scripts/run_tests.py \
  scripts/tests/bamf/test_verify_bamf_0_2_contracts.py \
  scripts/tests/bamf/test_check_bamf_workstack.py \
  scripts/tests/bamf/test_workstack_dependencies.py \
  scripts/tests/bamf/test_workstack_clause_formats.py \
  scripts/tests/bamf/test_bamf02_groom_contracts.py
python3 -B scripts/check_bamf_workstack.py docs/tasks/bamf-0.2/workstack.json
```

Observed: all fourteen original failures disappear; **58/58 focused tests pass,
zero skips**. New adversaries reject absent/changed pinned sources, wrong child or
parent identity, wrong generated markers, missing original clauses, reordered or
duplicate dispatch, and unreviewed extra children. The actual CLI is tested.

Registry integrity remains `valid`, child count 171, dependency status `held`, and
executable order empty. The same eight holds remain: A03.4, A05.4, A05.5,
A08.1b.2, A08.1b.5, B02.4, B11.1a and C14.4.

## Boundary

This is mechanical contract verification, not evidence of a runnable graph,
full #347 completion, source admission, or learning. Parent integration and its
aggregate EGM remain separate. Issue-owned turn-in requires available PR capacity
and the scoped merge-readiness review. Historical ABI enforcement remains advisory
without an external expected fingerprint. IPR-0220 governs. No actual student, matching
AdamW, teacher, champion, checkpoint or human-run state changes.
