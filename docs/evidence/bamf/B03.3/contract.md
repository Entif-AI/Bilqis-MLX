# B03.3: nested handles and observable frame counts

Issue #444 owns source/parent/scope nesting and frame-fill/fallback observability.
Consumed unified and Lane B: `9104ce733e04fb9c82420428b18dfdbf5db49535`.
Direct source prerequisites #575 (A05.4 partial visible forests) and #576 (B02.4
child constituents) are merged in that lineage. IPR-0220 remains OPEN.

## Behavior and ownership

`encode_frames(CompiledEncoderInput, CompiledEmbeddingVectors, parameters)`
returns `FrameEncoding` with schema `bilqis.mlx.frame-encoding/v4`. The compiled
input is `bilqis.mlx.compiled-encoder-input/v1`; supplied vectors are
`bilqis.mlx.compiled-embedding-vectors/v2`. Existing B01 tensor names and
initializers remain authoritative. No new tensor, semantic ID or child ABI row
is introduced. The inherited implementation already supplies this behavior;
this change separates its owners and closes the explicit acceptance proof.

Each compiled row is independently revalidated against the source compiler.
Nested rows require their source AST and exact A05.4 partial-visible-forest
receipt. A13 validates current source grants and causal visibility before neural
encoding. Invalid geometry, stale receipts, orphan/relabelled children and
revoked source evidence fail through the existing `SCHOOL.MODEL_TOPOLOGY.INVALID`
boundary. The extraction preserves those validations and error identity.

Closures execute in source order. A parent member consumes the earlier child's
768-vector plus its B02 source-bound parent context; no child ConceptRef or
identity row is fabricated. The parent loss differentiates through the child,
its member vector, frame interactions and type/local-slot factors. Child-only
prefix encoding excludes the future parent and its members. A later parent
binding change cannot affect the p4 child's representation.

`FrameEncoding.compiled` is the original validated `CompiledFrameRows` object;
`handles` is its exact padded-position tuple. Each packed closure retains its
source instance, span, structural path, occurrence/content identity, parent,
causal end, schema scope and constituent metadata. Compiler expansion/scope maps
remain attached. Atomic closures have no schema scope in their sidecar and use
the source task scope in the compiler map. The encoder adds no alternate scope
or telemetry registry.

`row.stats` is the A05 authority for actual atom/frame/position counts,
COMPACT/EXTENDED/ATOMIC disposition shares and sidecar bytes. These are structural
counts, not occupancy estimates or learned performance. No separate frame-fill
formula is invented. In the named synthetic nested fixture:

| Prefix | Atoms | Frames | Neural positions | Compact | Extended | Atomic |
| --- | --- | --- | --- | --- | --- | --- |
| p4 | 4 | 1 | 5 | 0/1 | 1/1 | 0/1 |
| p8 | 8 | 3 | 11 | 0/3 | 2/3 | 1/3 |

Both batch rows have 11 tensor positions. The p4 tail has six `None` handles and
zero vectors; padding never contributes to compiler counts. Child and parent use
the existing `SCHEMA_NOT_FOUR_SINGULAR_ROLES` extended fallback; the middle atomic
closure uses `ATOMIC_FRAME`. The p4 child sidecar equals the p8 child sidecar.

## Focused validation

Run from the repository root with installed MLX and NumPy. Select CPU before
importing test modules to leave the shared GPU lane free:

```sh
node ~/.codex/hooks/validation-output-runner.mjs -- python3 -B -c '
import mlx.core as mx
mx.set_default_device(mx.cpu)
import unittest
loader = unittest.defaultTestLoader
suite = loader.discover("bilqis_mlx/learning/tests/frames", top_level_dir=".")
suite.addTests(loader.loadTestsFromNames([
    "bilqis_mlx.learning.tests.test_frame_encoder",
    "bilqis_mlx.learning.source_atoms.tests.encoder_regression.test_actual_a05_atoms_and",
    "bilqis_mlx.learning.source_atoms.tests.encoder_regression.test_exact_equations_original_members",
]))
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("TEST_TOTAL", result.testsRun, "SKIPPED", len(result.skipped))
raise SystemExit(not result.wasSuccessful())'
```

`test_compiled` proves future-parent isolation and source revalidation;
`test_members` proves child/member/type/local-slot gradients and invalid binding
rejection; `test_execution` checks exact sidecars, scope maps, dispositions and
padding-free counts; `test_contracts` checks public record pickle identities.
The unchanged source-atom regressions prove prior B03 equations and fallbacks.

The fixture is explicitly synthetic source-valid interface data. Real A01/B02
source admission, assembled B11 network, B05 depth provenance, retained learning,
B13 checkpoint publication and parent B03 integration remain their existing
owners' acceptance work. Tests perform only disposable CPU computation. No
durable student, own AdamW, teacher, champion, policy epoch or original artifact
is changed. Only the human starts/resumes persistent neural training or merges
the PR. Existing PM-2026-10-30-002 / RC-112 / PAT-035 controls apply.
