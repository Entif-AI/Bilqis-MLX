# C03 accepted-custody completion — 2026-11-08

Issue: #376
Branch: `codex/bamf02-c03-376-20261107`
Reviewed unified consumed: `7d9e0e8209e2d077e4fc30f65a3ebf3f29a91f3f`
Exact semantic head: `b5603ebe2587521bc0eb556904435a5006711e8a`
Status: **EGM_PASS_READY_FOR_HUMAN_REVIEW**

## Completed integration boundary

The dependency-held C03 closeout now consumes accepted B13 custody without changing ownership:

- generation zero is loaded through authenticated B13 accepted-generation custody;
- C03 initializes its replay-teacher lineage only when the accepted generation lacks an existing C03 lineage;
- current student identity is derived from accepted B13 candidate identity;
- run-identity digest, integer `run_seed`, generation and accepted manifest are read from B13 custody;
- `select_visit_policy(...)` remains the actual policy-selection owner and the selected policy key is not caller-minted;
- selector-mutated teacher state is written back into the C03 projection before the visit identity is recorded;
- `TeacherVisitIdentity` binds the exact accepted B13 and C03 state at the selection event;
- accepted successors reuse B13 `derive_successor_bundle(...)` and then advance C03 teacher state plus matching generation provenance as one validated pair;
- B13 sidecar validation runs before the successor is returned;
- cold read restores the exact C03 lineage, prior visit, next seed and cursor;
- bound visit objects are owner-issued only and stale-generation reuse fails closed;
- C03 creates neither C05 acceptance evidence nor B13 publication authority.

The caller still supplies the next selection seed/cursor because C03 authority defines no implicit `+1` or elapsed-time progression rule. This preserves the existing visit-owner boundary instead of inventing one.

## Exact-head proof

On exact semantic head `b5603ebe2587521bc0eb556904435a5006711e8a`:

- lineage + parent acceptance + real visit orchestration + exactly-once observation replay + B13 cold-custody integration: **37 passed / 27 subtests**;
- canonical C03 teacher surface + observation capture: **14 passed / 6 subtests**;
- legacy-adaptation authority contract tests: **7 passed / 2 subtests**;
- development structure: PASS;
- governance integrity: PASS;
- BAMF flow control: PASS;
- static adaptation-source authority: PASS;
- docs: PASS;
- code-smell audit: zero new changed-file findings;
- `git diff --check`: PASS;
- local/remote semantic head exact.

Canonical latest adaptation source remains `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`. Prometheus is historical evidence only and not the current adaptation source.

## Fresh turn-in EGM

Fresh independent review against the exact candidate returned **PASS — 0
Blockers / 0 Majors / 0 Nits**, with disposition
**READY_FOR_HUMAN_REVIEW**. The durable review receipt is
`docs/evidence/bamf/C03/egm.md`.

Hosted CI subsequently exposed only opaque numeric guard debt in the new C03
digest-width checks. Repair `874eabc39ad2086b758e891ccf9b6f6a2f11ccec`
names those unchanged SHA-256/Git-commit widths, regenerates the repository-owned
error catalog/manual, and passes the exact 37-test C03/B13 ring plus the
error-control gate with zero new debt. A targeted fresh Goldfish re-audit of that
repair also returned **0 Blockers / 0 Majors / 0 Nits** and confirmed no semantic
contract changed.

## Remaining gate

Ready human-review PR #932 is open against
`codex/bamf-unified-base-20261028`. Only hosted integration checks, human PR
review and merge remain. No self-merge is authorized.
