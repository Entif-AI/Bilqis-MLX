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

Requested main intake exposed a 391-line rejection projection test. The
mandatory structure interruption split unchanged test assertions into projection
(232 lines), genesis (57 lines), and shared fixtures (115 lines). Twelve focused
cases passed before import-only cleanup. Local Work Stack interruption completed;
full leaf qualification includes the changed test files. This is inherited
structure compliance for the requested main merge, not a trainer semantic change.

Leaf v1 receipt: FAIL, 143 passed / 61 failed / 1 collection error; source
snapshot unmutated. Static structure, governance, smell, trainer-authority,
invariant-transfer and flow-control stages passed. Failure census: 52 stale
`run_authority.binding.storage_root` patches, moved session helper imports/patches,
and a cold-resume double missing `run_authority`. These boundaries were removed or
moved in the consumed baseline, independently of the memory-context change.
Repair scope: migrate affected test doubles to current owners and remove obsolete
storage-root substitutions. Preserve all runtime behavior and assertions. This
implements inherited #1391 acceptance requiring existing resume/publication tests
green; no new acceptance obligation. First focused repair checks: 18 + 7 passed.

Additional focused verification after fixture migration: 16/16 operator observed,
mentor, championship, publication, metrics and throughput cases passed in 5.04s.
Combined repair checks total 41 passing cases. Production memory implementation
has not changed. Differential selection now includes 72 files because shared
fixture repair invalidates its direct test consumers. Leaf v2 is a fresh snapshot;
v1 evidence remains preserved and its 143 passing cases are historical evidence.

Leaf v2: 388 passed, 1 failed, 58 subtests passed; snapshot unmutated.
Remaining failure was the cold-resume double call expectation omitting the
existing `run_authority=None` argument. Corrected the literal expected call;
production behavior remains unchanged. Static gates passed again. No third
unchanged broad diagnostic run: first prove this exact assertion locally on
m3-ultra, then consume current unified before the integration boundary.

Resume assertion repair: 2 passed in 26.26s on m3-ultra. Current unified
`204a5f4769189b1dd9d334f1b7a85b4133a48110` consumed at merge head
`249d541d066aa708917cd22da98e4dffa0194e0e`; only ledger conflict, preserving
both issue entries. Native memory coordinator files unchanged by intake. Intake
changes readout, retention, priority and model validation assumptions, so affected
integration proof must run again. Production design review/NO_DRIFT remains valid.

Integration qualification chains static quality, aggregate collection preflight,
affected tests, Node/security and the existing premerge aggregate. Existing runner
excludes DETACHED_ONLY witnesses. Discovery: 1,186 files / ~5,500 unittest methods.
Expected 45–90 minutes using the measured 18-minute leaf and repository qualification
estimates as inputs; entire composed run fails after 115 minutes. Test-only 8 GiB
allocator bound remains applied to every Python child. No whole-system PASS is
claimed until terminal receipts are reconciled.

Integration v1 stopped at the error field manual check before test collection.
The native test's inline synthetic exception was counted as a raw error site.
The test now creates the exception once and verifies that the operator
propagates the same instance. Regenerating the catalog produces no diff.
The v1 snapshot mutation guard passed.

Integration v2 passed static quality. Its collection preflight incorrectly used
pytest discovery for the unittest aggregate, which bypassed verified SKOS bundle
reuse and attempted to import the optional PDF extractor. The source snapshot
passed its mutation check. Preflight now uses the aggregate's own selection and
loader. The real loader also exposed four PyTorch import errors in the shared
test interpreter. Installing PyTorch 2.15.0 in a separate test dependency directory
resolved them. On the v2 source snapshot the corrected preflight loaded 5,076
unittest cases with zero import errors and verified the unchanged SKOS bundle.

Integration v3 passed the governance, architecture, documentation and error
catalog checks but stopped at the code smell check. The harness used a mutable
module-level list for its import paths. Replacing it with a tuple passed the
staged smell and structure checks. No test ran and the snapshot stayed intact.

Integration v4 passed static quality and aggregate import preflight (5,076
cases, zero import errors). Affected tests reported 368 passed and 21 failed.
Twenty failures hit the default 100 GiB reserve during disposable custody
writes on a host with 97 GiB available. The profile ordering test stopped
before visiting for the same reason. Three test files now pass an explicit
fixture reserve. The production default and reserve enforcement are unchanged.
The exact 21 failed case IDs passed on the same host in 17.23 seconds,
including eight subtests. The v4 snapshot mutation guard passed.
