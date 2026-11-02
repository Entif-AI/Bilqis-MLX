# C11.1 curriculum-compiler structure interruption

## Scope

Issue #522 next encountered `bilqis_mlx/curriculum_compiler.py` at 486 lines and its direct companion test at 262 lines. Both exceeded the active development-structure threshold.

The repair keeps `bilqis_mlx.curriculum_compiler` as the public facade and moves the seven typed records plus cohesive helper/graph/probe owners under `bilqis_mlx/_curriculum_compiler/`. The facade explicitly restores every public record/function `__module__` to the historical public module. `compile_typed_candidate_package` remains physically in the public facade because it was already a known long-function/branch-density baseline finding at that exact path; moving it would create false-new path-qualified debt. The public facade is 160 lines; every extracted production owner is below 240 lines. The internal package has eight direct Python files.

The companion test keeps its path-sensitive `setUpClass` and source-materialization test at the original file depth. The remaining tests move into graph/probe and typed-package mixins under `factory/tests/curriculum_compiler/`. This avoids changing the original `Path(__file__)` source-root contract or creating duplicate default discovery. Every companion test owner is below 240 lines.

No curriculum source, dependency, finite-coverage, oracle, admission, probe, or training-authority policy changes.

## Preservation proof

Against pre-interruption head `8400690`, all 19 original top-level production definitions are present and AST-identical after extraction. All 10 original test methods are present and AST-identical.

Focused compiler tests pass 12/12, including public-module-identity and owner-first import-order regressions. A broader Factory construction, grade-admission, autonomy, runtime-autonomy, and construction-witness selection passes 138/138. The operator-contract/error census remains 30 findings, unchanged from the branch baseline.

Repository checks:

```text
python3 -B scripts/check_module_size.py --changed-from 8400690
DEVELOPMENT_STRUCTURE_CHECK OK violations=0

python3 -B scripts/quality/check_governance_integrity.py --base-ref 8400690
GOVERNANCE_INTEGRITY_CHECK OK violations=0

python3 -B scripts/code_smell_audit.py --changed-from 8400690 --check-baseline docs/evidence/development/code_smell_baseline.json
New changed-file findings: 0

git diff --check
PASS
```

The wheel builds with the new private owners. An empty isolated venv cannot import the package because it intentionally lacks `rdflib`; this is not introduced by the split. Installing the built wheel into a clean target directory and executing it with the existing dependency-bearing verifier imports the installed package outside the checkout. Direct owner-first imports of helpers, graph, packages, and probes now succeed without importing the public facade first. The public facade preserves `CapabilityNode`, `CurriculumAST`, `TypedExpressionTemplate`, and moved public functions as `bilqis_mlx.curriculum_compiler`.

## Remaining C11.1 state

This is structural only. It does not satisfy production B13/A12 source/run authority or complete #522. The next queued root interruption is `registry_ast.py`.

## Public function identity repair

A cross-facade ABI audit found that re-exported compiler functions retained private owner modules in `__module__`. A new regression failed first for all eight moved public compiler functions. The public facade now restores their historical `bilqis_mlx.curriculum_compiler` module identity after import. The typed record definitions now live in the private `types` owner to remove private-to-public import cycles; the public facade restores their historical module identity. A separate owner-first subprocess regression prevents that cycle from returning. The regression passes without changing any original definition body.


## Fresh review repair

Fresh independent review of `aa083208` found one Major: internal owner modules imported types back from the public facade, so direct owner-first imports were circular/order-dependent. The same failure reproduced through installed-wheel private-owner import. The repair introduces `_curriculum_compiler/types.py`, rewires every private owner to private types/helpers only, and keeps the public facade as a one-way re-export boundary. A new subprocess regression imports all private owners before the public facade and passes. Fresh quality checks report zero new changed-file smell findings.

## Public annotation introspection repair

Final aggregate review found one additional public-ABI Major after the ownership split: moved record classes correctly reported `bilqis_mlx.curriculum_compiler` as `__module__`, but the facade no longer bound the historical annotation globals `Expression` and `Proof`. As a result, `typing.get_type_hints(TypedCandidateSpecimen)` failed with `NameError` even though pickle/module identity passed.

A new failing-before regression resolves type hints for all seven public record classes and asserts the `TypedCandidateSpecimen.expression` and `.proof` annotations resolve to the public facade's `Expression` and `Proof`. The facade now re-binds those two historical annotation names from their canonical owners. Focused compiler proof is 13/13 and the four-owner structural aggregate is 50/50 after the repair. No implementation body, source rule, or admission policy changed.
