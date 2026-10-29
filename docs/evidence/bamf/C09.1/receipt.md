# C09.1 | Direct correction dependencies and lazy revalidation

Issue: #516, parent C09 #377. Lane C branch:
`codex/bamf02-c-runtime`. Reviewed unified baseline consumed:
`6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
Candidate implementation: `d0fd5ab5a7586ce57f1b14cf767acf448145a584`.
Draft human-review PR: #550.

## Exact owned behavior

- The immutable `bilqis.c09.dependency-index/v1` records direct reverse
  edges for atlas features, packed frames, motifs, exact caches,
  operator compositions and learned capability support.
- Each artifact declares immediate source, operator, release, policy,
  time, rights or artifact dependencies. Missing artifact owners and
  cycles reject before the index is usable.
- `bilqis.c09.correction-event/v1` binds a source-owner receipt and
  separate source/effective/observed/recorded times. A correction
  holds its direct dependents before reuse.
- `bilqis.c09.revalidation-queue/v1` orders lazy work by exigency,
  impact and stable ID, subject to upstream dependency holds.
  Descendants cannot be read through a held or ineligible ancestor.
- `bilqis.c09.state-transition/v1` propagates to immediate consumers
  only when content identity or eligibility changes. Equal results
  stop propagation; immutable prior nodes remain available as history.

## Verification and limits

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_revalidation.py
bilqis_mlx/runtime/tests/test_error_control_plane.py`:
**12 passed, 0 failed, 0 skipped** (8 C09.1, 4 error-control).
The C09.1 test module first failed because the implementation was
absent, then passed after implementation. Adversaries cover held
ancestor readout, revoked motif eligibility, topological priority,
cycles, missing recomputation evidence, and exact reverse edges.

Static error-control and module-size scans showed no new C09.1
findings; inherited repository debt remains outside this leaf.

This is a source-owned recomputation *consumer*, not a new rights
issuer. Source correction qualification and actual upstream
A01/B07/B13/C04 interfaces require later integration requalification.
C09.2 owns concurrent alternatives and learned requalification;
C09.3 owns time projections and stale-remediation escalation.
The C09 parent acceptance, live learner, and downstream integration
are **not** claimed complete. Independent Goldfish EGM is pending.
No neural/optimizer state, live run, or private source was changed.
