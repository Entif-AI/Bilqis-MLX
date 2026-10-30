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
The changed-path module-size check passes. The repository-wide operator-contract
check fails with 30 findings; its output is byte-identical to unmodified Lane C
at `57f8d9d`, so this repair adds no observed findings to that existing failure.
