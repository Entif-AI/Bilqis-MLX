# C01 current-unified structural turn-in — 2 November 2026

Consumed reviewed unified `67c964a1548cb0075a28a90aa2565d8bdab0fd71`
through synchronized/pushed Lane C `46bfa98d564e1262be43463ec96d3ce1a95aa8c4`.
PR #699 merged, satisfying the recorded primary-drain trigger. C01 was activated
before refreshing its parked branch. C12/#680 remains frozen.

The merge retains unified's accepted `frame_codec_parts` implementation and both
codec test sets. The superseded `_frame_codec` extraction is removed. An independent
AST comparison found identical top-level named assignments and 31 of 32 definitions;
the accepted readout's additional source-type authority checks are preserved.
Old focused readout fixtures now provide the accepted authoritative concepts.
No assertion or production source-type gate is weakened.

## Defect and exact source proof

The first combined merge run had 183 passes, one failure and two errors among
186 tests. Two readout failures came from the stale fixture. The other error,
`NameError: name 'FrameSchema' is not defined`, exposed missing runtime annotation
binding in the accepted schema-map owner. Issue #731 / PR #732 records its isolated
branch from synchronized Lane C and explicit consumption of the already-completed
parent structure repair. The new annotation test failed before the canonical import
and passed afterward. Parent #694 consumed repair `7c8b75a418e726060945f2b9cbe296063b7d9ee4`.

At that source commit:

- Combined source selection: **187/187**, zero failures/errors/skips.
- Fresh git-archive installed wheel: **116/116**, zero skips, installed origins
  verified. See [the complete probe](installed-wheel-probe.md).
- Native frame callers: **6/6**, zero skips, Python environment with native MLX.
- Complete committed Python scope: **99 files**, zero hygiene findings/new debt.
  Structure, governance, architecture, docs, error-control and whitespace checks pass.
- Registry: 171 children, valid integrity, eight held keys and empty execution order.
  CLI exits 1 because the semantic dependency normalization remains held.

First follow the [complete setup and fixture rebuild recipe](installed-wheel-probe.md#rebuild-inputs-and-the-installed-target). It creates both inputs from tracked public CSV records, installs the tested dependencies in fresh environments, and builds the isolated wheel. Run the source command below from `$C01_WORK/source` with `$C01_PY` after that setup.

Supply `BILQIS_ATLAS_REAL_ARTIFACT` pointing to digest-named bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
and `BILQIS_ATLAS_REAL_CORPUS` pointing to conformance bundle
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`.
Use Python with the project's portable runtime dependencies. Omitting fixtures
does not reproduce this no-skip source proof.

```sh
python -B scripts/run_tests.py \
  bilqis_mlx/semantics/tests/frame_compiler \
  bilqis_mlx/semantics/tests/partial_visible_forest \
  bilqis_mlx/semantics/tests/released_schemas \
  bilqis_mlx/semantics/tests/frame_schema \
  bilqis_mlx/semantics/tests/frame_codec \
  bilqis_mlx/semantics/tests/test_frame_codec.py \
  bilqis_mlx/semantics/frame_codec_parts/tests \
  bilqis_mlx.semantics.tests.source_atom_binding.test_binding \
  bilqis_mlx.semantics.tests.source_atom_binding.test_handoff \
  bilqis_mlx.semantics.tests.source_atom_binding.test_resolution \
  scripts/tests/bamf
```

On a native MLX host, with no competing neural test writer:

```sh
python -B scripts/run_tests.py \
  bilqis_mlx.learning.tests.frames.test_compiled \
  bilqis_mlx.learning.tests.frames.test_members \
  bilqis_mlx.learning.tests.frames.test_execution
```

Historical 164/93/6 receipts elsewhere remain attributed to their original commits.
The current proof includes 22 accepted unified codec tests and the new annotation
regression beyond that source/installed selection. No threshold/baseline change,
source admission, persistent learner/own AdamW/teacher/graph mutation or self-merge.
Full #347 remains open; typed interface-receipt normalization is the preserved next
implementation task, not an outcome of this structural PR.

#733 repeats the full source and installed selection after rebuilding both exact
inputs from tracked public CSVs in fresh environments: 187/187 source and 116/116
installed, zero skips. All four conformance gates pass with partial source coverage
preserved. This independently reproduces fixture acquisition as well as test
execution; it does not promote source or claim full C01 acceptance.
