# C10.2 atomic outbox batch repair

Status: PARTIAL; EGM_PENDING. Issue #520 and its upstream qualification remain open.
IPR-0220; incident PM-2026-10-29-009. The branch starts at Lane C
`57f8d9d878e57429fdb7f4335167f5c6e7dcbdaa`, which consumes unified
`d468b1af1c70a8dc0c0a7aa5ffa6d19b55cb2e18`.

The prior projection preflight checked the submitted wrappers but committed each
outbox event independently. A later existing event with a different durable rights
binding, or a conflicting source identity, rejected the call after an earlier new
event had already committed. A disposable SQLite reproduction read back the unwanted
event. No production graph, student, optimizer, or external service was touched.

The outbox owner validates entries, then performs the event and source-identity
checks and inserts under one SQLite `BEGIN IMMEDIATE` transaction. A conflict
rolls back all inserts. Single-event callers use the same transaction path.
The projection receipt and existing event, binding, and projection schemas remain
unchanged. This repair does not provide source-rights authority or complete C10.

Red: `red.txt` records two failing tests against the prior implementation.
Green: `green.txt` records 22 passing tests across the projection, outbox,
owner-fixture, and native-generation receiving suites. The additional regression
checks conflict between two new source identities in the same batch. The existing
duplicate, restart, immutable binding, graph outage, and staging tests also pass.
Independent fresh-context EGM review and upstream/service qualification are pending.
The earlier local changed-path structure check ran before the repair commit and
did not include its files. Hosted CI reports eight structure violations. The
repository-wide operator-contract check fails with 30 findings; its output is
byte-identical to unmodified Lane C at `57f8d9d`.

The original public projection import paths are preserved and tested. The
projection-owner tests now live under `bilqis_mlx/runtime/tests/projection/`;
the test-only move updates fixture imports and the Rosetta bridge's repository
root lookup. With the local Rosetta owner selected, all 26 tests pass. Runtime
and test directory restructuring remains incomplete; independent review and
exact-head hosted checks remain pending.

Projection owners are physically grouped under `runtime/_projection/` while
`runtime.__path__` includes that directory to retain the established public
module names and relative imports. The import regression verifies all six
original names, their module identities, and package discovery. The 26-test
projection suite passes with the local Rosetta owner; three other grouped suites
pass 63 tests with one optional skip. This is a partial directory interruption,
not evidence that all runtime packaging or downstream deployment is qualified.
The unchanged Lane C baseline and this worktree both fail the factory
architecture check at `model_topology_v2.py:280`; their operator-contract
check output is also byte-identical with 30 findings.

PM-2026-10-29-010 records the duplicate-module risk in physical search-path
grouping. A fresh-process negative test registered a plausible sibling module
and reproduced distinct `BamfProjectionEvent` classes through the physical
subpackage path. The physical subpackage now exposes an empty search path, so
ordinary import traversal cannot load the six owners under alternate names.
The regression asserts the exact missing alternate module name for each owner;
it does not treat arbitrary transitive import failures as success. All 27
projection tests pass with the local Rosetta owner. This is not a security
sandbox or proof of installation packaging; independent review remains pending.

The subsequent admission-owner grouping preserves the exact bytes of six moved
source files and their established runtime module names. Before the move, 39
affected admission and autonomy tests passed. Afterward, those tests plus two
new import-identity tests passed; the combined admission and projection run
passed 68 tests, including native Rosetta. The physical admission subpackage
also rejects ordinary alternate-name traversal. The saved student, optimizer,
teacher state and existing run directories were not opened for mutation. This
is not a training, installation-distribution or full integration proof.

Two capability owners were grouped with their source bytes and established
runtime module names unchanged. Their prior 41-test behavioral suite passed
before the move. After the move, the suite and two import-identity tests passed
43 tests; the combined projection, admission and capability run passed 111
tests, including the native Rosetta checks. Ordinary alternate-name imports
are rejected for both moved capability modules. This is not a full runtime
qualification or a proof of behavior under untested packaging layouts.

## Directory interruption,30 October2026

The dedicated issue branch codex/bamf02-c10-520-structure-20261030 was created from LaneC57f8d9d, consuming unifiedd468b1a, then fast-forwarded through the prior repair branch's local339c9cc without rewriting its history. Runtime and runtime/tests each now contain12 direct Python files. Exact move inventory and preservation requirements are in structure-plan-20261030.md. This directory phase is committed separately before the encountered file repairs.

41 moved source files retain their bytes except qualification's package-root lookup and teacher_observation_capture's package-root/source-hash lookup. directory-owner-hashes-20261030.json records exact before/after digests. Canonical teacher implementation keys remain unchanged. The runtime behavioral suite reports467 total,423 pass,1 failure,22 errors,21 skips. All23 failure/error identities match baseline exactly; directory-failure-parity-20261030.json preserves that comparison. These baseline failures remain failures. Five additional import/root tests are now present; the recorded full-suite run included the first four.

A baseline-built wheel contained no runtime modules. Package discovery now includes bilqis_mlx subpackages and their JSON resources. A clean disposable environment installed the rebuilt wheel; four grouped-owner tests passed from /tmp, outside the checkout. This proves package inclusion, discoverability, alternate-name rejection, canonical source-class identity and teacher source hashing for the tested installed layout. It does not qualify the full application, external corpus resources or MLX. A subsequently added qualification-root test still requires its final exact-wheel rerun.

Fresh EGM implementation-readiness review of the exact directory plan is READY for that phase only. Independent implementation review and the subsequent file interruptions remain pending. The staged structure check records14 remaining file findings and zero directory findings; the inherited akasha_staging offender also remains in the full feature diff. No structure threshold, baseline or exclusion was changed. C10.2 qualification is paused until these interruptions are repaired.

First subsequent file interruption:atlas_admission.py is now162lines, its contracts147 and storage133; original/shared-fixture and focused contract/storage tests remain below240. Admission41/41 plus five grouped import/root tests pass46/46. The public command/staging/renewal owner preserves existing functions and the renewal _durable_json patch seam. Immutable payloads, signature checks, lock scope and pointer ordering are unchanged. Independent scoped review is running; no final leaf acceptance is claimed.

Fresh-context codebase/comprehension review through64610f2 found zero Blockers/Majors in the directory phase plus lease extraction. One proof-name nit was repaired; see egm-directory-lease-20261030.md. Full issue520 remains PARTIAL and EGM_PENDING for unrepaired file interruptions and upstream owner acceptance.

Second file interruption:atlas_requalification393lines becomes100-line orchestration plus113-line authenticated branches and201-line immutable evidence contracts. The organically encountered784-line companion is now154lines of shared signed fixtures plus seven focused test files53–151lines. All original production function/class ASTs and all18 test method ASTs are identical.18/18baseline tests and91/91combined correction/admission/projection tests pass with no skips/errors. Focused structure checks pass. This repairs that interruption only; remaining file/test interruptions and complete C10 acceptance remain pending.

Final installed lease checkpoint:five tests passed outside the checkout; directory-installed-lease-final-20261030.txt records it. Unified advanced tob78a500 and was merged into both the issue branch3525d65 and long-lived LaneC03b2145. Post-sync combined admission/projection73/73passed. All12 tracker tabs were updated/read back and visually checked; only LaneC row7 height was auto-fitted to avoid clipping, with original column widths/formulas preserved.

Independent correction-extraction EGM returned scoped PASS with zero Blockers/Majors and independently confirmed13 production/18 test AST identities. Third file interruption splits temporal revalidation443lines into130-line pure projection,127-line temporal contracts and207-line stale-replay escalation. Original production definition ASTs remain identical, companion tests remain below240lines, and the same91 combined tests pass without skips/errors. Subsequent file repairs and full C10 acceptance remain open.

Fourth file interruption:the402-line training adapter now has207-line source compilation,98-line immutable contracts/release checks and120-line delivery/backend ownership. The492-line companion is172lines of preserved shared source fixtures plus17–146-line focused tests. Every production function/class AST and all25 distinct test method ASTs are unchanged. Adapter+salience now passes28/28 distinct executions; the original48 included20 identical base-method executions inherited by its execution-test subclass. Only those redundant executions disappeared; no distinct test scenario or assertion was removed. Independent temporal/adapter review and the remaining interruptions stay pending.

Fifth file interruption: candidate_evidence is 168 lines, retention_support 140 and fixed_frontier_evidence 153. The existing fixed-row monkeypatch seam remains in the original owner. Direct imports of each new owner succeed in fresh processes. All original production function ASTs match.

The directly encountered 2,574-line learning-experiment test and 568-line fragile-replay test are now compact shared fixtures plus focused retention/teacher/source/replay files. All 92 original test method ASTs and every original comment survive unchanged. New test folders have 3–12 direct files, with maximum test-file lengths 157–188 lines. The 96-line frontier companion's support tests now mirror the support owner.

Baseline: 92 tests, 91 passed, one existing MLX-unavailable optimizer-custody error. Combined post-extraction proof: 117 tests, 116 passed, the same optimizer test error. The extra 25 tests are the already-split adapter methods. No baseline failure is waived. Focused structure checks pass; the learning/tests directory is the next recorded interruption before feature qualification resumes.

Learning-test directory interruption: 33 direct code files become 12 after moving exactly 21 files into engram/championship/salience/teaching/custody groups. Stable fixture import paths remain available. Twenty moved files retain identical bytes; teacher_observations alone adjusts its fixture lookup by one parent level. Full learning tests before and after both report 313 total, 301 passed and the same 12 error identities. No source tests or failures were removed. The root oversized files encountered during directory inspection remain recorded subsequent file interruptions.

Next recorded learning-file interruption: the 584-line engram allocation test becomes 123 lines of unchanged shared fixtures plus complete key/preparation/transaction test classes in 113/206/162-line focused files. Every class AST matches; all 25 tests pass before and after. No production logic changes.

M3 Ultra engram-read proof: immutable source snapshots d200c62 and 9bbf7aa ran the original and split motif-read suites serially on MLX GPU. Both report nine tests: eight passed, one existing pinned-A01-artifact-dependent skip, zero failures/errors. Original nine method ASTs remain identical. Shared fixtures are143lines; boundary/inference/gradient files are156/97/61lines. A separate temporary dependency target supplied cryptography/rdflib; the existing M3 Python environment was not modified. Remote free disk exceeded100GiB reserve. All source and logs live under explicit /tmp/bamf-c520-* paths; no saved student, AdamW or human-run command was used.

Epoch-test interruption: the660-line original is now104lines of shared helpers, with five focused authority/competition/settled-ledger/fan-out/reset files73–156lines. All26 original test method ASTs match, and26/26tests pass before and after. Production championship policy is unchanged.
