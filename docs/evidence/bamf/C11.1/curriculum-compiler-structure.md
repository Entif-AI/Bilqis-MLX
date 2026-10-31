# C11.1 curriculum-compiler structure interruption

## Scope

Issue #522 next encountered `bilqis_mlx/curriculum_compiler.py` at 486 lines and its direct companion test at 262 lines. Both exceeded the active development-structure threshold.

The repair keeps the seven public typed records in `bilqis_mlx.curriculum_compiler`, preserving their historical module identity. Helper operations, dependency-graph logic, typed candidate-package compilation, and probe planning/materialization move under `bilqis_mlx/_curriculum_compiler/`. The public facade is 170 lines; every extracted production owner is below 240 lines. The internal package has seven direct Python files.

The companion test keeps its path-sensitive `setUpClass` and source-materialization test at the original file depth. The remaining tests move into graph/probe and typed-package mixins under `factory/tests/curriculum_compiler/`. This avoids changing the original `Path(__file__)` source-root contract or creating duplicate default discovery. Every companion test owner is below 240 lines.

No curriculum source, dependency, finite-coverage, oracle, admission, probe, or training-authority policy changes.

## Preservation proof

Against pre-interruption head `8400690`, all 19 original top-level production definitions are present and AST-identical after extraction. All 10 original test methods are present and AST-identical.

Focused compiler tests pass 10/10. A broader Factory construction, grade-admission, autonomy, runtime-autonomy, and construction-witness selection passes 136/136. The operator-contract/error census remains 30 findings, unchanged from the branch baseline.

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

The wheel builds with the new private owners. An empty isolated venv cannot import the package because it intentionally lacks `rdflib`; this is not introduced by the split. Installing the built wheel into a clean target directory and executing it with the existing dependency-bearing verifier imports the installed package outside the checkout, imports the private package owner, and preserves `CapabilityNode`, `CurriculumAST`, and `TypedExpressionTemplate` public module identity as `bilqis_mlx.curriculum_compiler`.

## Remaining C11.1 state

This is structural only. It does not satisfy production B13/A12 source/run authority or complete #522. The next queued root interruption is `registry_ast.py`.
