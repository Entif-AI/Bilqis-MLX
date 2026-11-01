# C01 compiler structural interruption — 1 November 2026

The receipt-normalization investigation encountered the 1,029-line causal compiler
and its 1,093-line companion test. The mandatory development interruption was
preserved in Work Stack `59d77f15-1d25-4af5-9527-de2939b126de`, task
`struct-frame-compiler`, before feature work continued. Four other encountered
source files remain queued: partial_visible_forest, released_frame_schemas,
frame_schema and frame_codec. This checkpoint completes only the compiler repair.

The compiler facade is now 104 lines. Imported owners separate source/configuration,
positions, batch identity, approval, causal visibility, packing, source maps,
statistics, rows, lawful segments and reconstruction. The largest source owner is
147 lines. The original test module is a six-line fixture compatibility facade;
all companion files are below 240 lines, with shared fixtures largest at 189.
Production and tests follow the same ownership boundaries. The private source and
compiler-test directories contain 15 and 13 direct Python files respectively.
No directory reaches the 18-file interruption trigger.

All original production record bodies, constants, digest recipes and error fields
remain unchanged. The five intentionally changed original definitions contain only
phase extraction and deferred calculation/facade imports. All 26 original test
method names occur exactly once. The long lawful-segmentation witness retains its
assertions across a setup helper and two focused cases. Existing fixture imports,
public class identity, pickle identity, return type hints and the facade packing
patch seam remain available. Existing comments and literal wire-byte witnesses
are retained.

## Verification

- Original compiler baseline: 26/26.
- Three compatibility witnesses against the original source: 3/3.
- First record extraction and full procedure extraction: 29/29 at each checkpoint.
- A new return-type-hint witness failed with `NameError: PrefixMaps`; separate
  records and calculation owners fixed the import dependency. No mutable alias
  injection or weakened annotation contract was introduced.
- Final compiler, partial-forest and source-binding selection: 38/38, no skips.
  Use package-qualified targets for the existing source-binding tests because
  the file runner cannot resolve their relative helper imports.
- Native M3 encoder/member/execution callers: 6/6, no skips, in an isolated
  disposable checkout using the existing sovereign MLX lock. The portable
  environment lacks MLX and could not load these three modules locally.
- BAMF control-plane suite: 70/70, no skips.
- Staged structure and code hygiene: 34 files, no violations/new findings.
  Architecture, governance, documentation and error-control checks passed;
  changed-branch checks must be repeated after the integration merge.
- Fresh independent implementation-readiness review cleared both initial Major
  plan gaps. Fresh independent implementation review found zero Blockers, Majors
  or Nits; it compared source/test ASTs, statement order, comments and imports.
  Reviews were read-only and did not independently run tests.

Reproduce the portable selection:

```sh
/tmp/c524-venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/semantics/tests/frame_compiler \
  bilqis_mlx/semantics/tests/partial_visible_forest \
  bilqis_mlx.semantics.tests.source_atom_binding.test_binding \
  bilqis_mlx.semantics.tests.source_atom_binding.test_handoff \
  bilqis_mlx.semantics.tests.source_atom_binding.test_resolution
```

Native selection: the package-qualified modules
`bilqis_mlx.learning.tests.frames.test_compiled`, `test_members` and `test_execution`
under the same `bilqis_mlx.learning.tests.frames` package. These are finite tests,
not durable learner, optimizer, source-admission or training authority.

While this repair was being prepared, humans merged PR682 as `a6d8a000` and
advanced unified to `bd62f3cb`. The next step is to consume that reviewed unified
state and revalidate before publishing the structural follow-up PR. The integrated
171-child registry still has eight explicit holds and no executable order. Neither
this refactor nor its software proof establishes full C01 acceptance.

## Integration readback

Lane C fast-forwarded to `bd62f3cb6c296151aba7b9ed5fa90ee814492494` and
remote readback reported up to date. The active C01 branch consumed that same
unified commit without conflicts as merge `11b2b736723d791216c6f54964fae5e5967724b8`.
The post-merge combined compiler/source-binding/control-plane selection passed
108/108 with no skips. Changed-from-`bd62f3cb` structure, hygiene (34 Python files,
zero findings), architecture, governance, docs and error-control checks all passed.
No baseline or threshold changed. PR682 is already human-merged; this structural
continuation returns through a separate draft PR against unified.

Exact integrated compiler head `d22143d395d44e4d73300f5228d8dc7bc48a8536` also
passed the native M3 six-case selection. Its hosted portable, portable-core and
semantic-ABI checks all succeeded; semantic-profile jobs were intentionally skipped.
Draft PR694 is the structural follow-up. All12tracker tabs were updated/read back
with QA332,Turned-in267,IssueIndex224. The next coherent partial-forest repair has
its own proof record; no compiler acceptance claim extends to an untested new head.
