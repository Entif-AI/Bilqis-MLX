# C11.1 scoped independent review

EGM pin: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
The actual pinned Codex instructions, implementation-readiness, codebase-details
and comprehension personas and referenced document standards were read.

Fresh-context readiness review identified production v2 and Atlas admission
blockers: B13 checkpoint/run custody and A12/source authority remain unavailable.
It also distinguished a release manifest from the existing disposable lease and
required saved-versus-explicit override resolution. These are open #522 acceptance
requirements, not waived by this structural checkpoint.

A separate fresh-context Goldfish reviewed the original CLI extraction and found
zero Blockers/Majors. AST comparison preserved all original functions, tests,
comments and payloads after import relocation.

A further fresh-context Goldfish reviewed the expanded directory/CLI source and
packaging changes. It found one Major: the read-only issue349 transfer probe still
hashed old physical module paths. The patch uses canonical `source_path(name)`
while preserving receipt keys. The source-only review-evidence fingerprint reader
received the same necessary correction. One bounded re-audit found the Major
resolved and no remaining Blocker/Major within that scope.

Reviewers performed source inspection, not independent test execution. The main
writer separately ran the verification recorded in `structure.md`. Installed-wheel
proof subsequently passed 9/9 after the required Ithkuil compiler namespace was
included. This disposition covers structural behavior and provenance only, not
production #522 completion, live learning, semantic admission or merge authority.

A subsequent fresh-context Goldfish reviewed the numeric companion split against
`43eaeb3`: all 21 methods remain once, the 13 tests are AST-identical, inherited
fixtures add no duplicate tests, and the sole setup change preserves canonical
root resolution. Zero structural Blockers/Majors. The writer's isolated M3
comparison retains the inherited failing lifecycle cases and introduces no new
nonpassing identity; full numeric lifecycle acceptance remains red.
