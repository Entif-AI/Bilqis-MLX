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
