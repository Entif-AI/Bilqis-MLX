# Design review — #1391

Pinned EGM: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
Reviewer: fresh GPT-6.1 Terra, High reasoning, Codebase Details persona,
Implementation Readiness standard. Review performed before production changes.

Initial finding: Major, preserve portable entry-point tests when introducing lazy
MLX import. Design step 4 now specifies class-local no-op memory contexts for
existing mocked visits, real policy with fake MLX in focused tests, and real MLX
in hardware tests. Affected-scope re-review: PASS, zero unresolved Blockers/Majors.

Implementation scope audit: two production files; additional existing test edits
only isolate their mocked visits from MLX. All edits trace to #1391 acceptance;
no new acceptance obligations. Existing policy implementation remains unchanged.

Red: 2 failed / 3 passed on baseline 71a00bb90, both failures observed cache
987654 instead of zero during native operator ownership.
Green: 5 focused tests passed; 2 native MLX normal/exception tests passed on m3-ultra.
Hardware witness uses a disposable Linear model and native MLX AdamW inside the
real operator coordinator with visit/source/storage boundaries doubled. It proves
cache policy and live-array preservation, not full BAMF learning or publication.

Post-implementation fresh GPT-6.1 Terra High scoped review: NO_DRIFT;
no substantive implementation defect. Native hardware cases ran (2 passed,
zero skipped). Live legacy authority on m3-ultra: PASS, Factory branch
`codex/337-replay-349-20261026`, head
`d84d2ab9e2d79817c131ef7e0d4ec0d574e57b32`, generation 24254.
Local check could not resolve the remote-only authority path; remote live check
is the applicable receipt.

Next qualification: 36 differential test files, static gates first, single MLX
worker, test-only 8 GiB allocator bound and existing no-free-cache policy in every
Python child. Expected 20–45 minutes; hard failure after 80 minutes. This does
not claim the production trainer has an 8 GiB allocator cap.
