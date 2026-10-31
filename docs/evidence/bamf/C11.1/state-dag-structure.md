# C11.1 state-DAG structure interruption

## Scope

Issue #522 encountered `bilqis_mlx/state_dag.py` at 823 lines and its direct companion test at 341 lines. The development structure contract therefore interrupted feature work before further C11.1 behavior changes.

The repair keeps `bilqis_mlx.state_dag` as the public module and moves cohesive internal owners under `bilqis_mlx/_state_dag/`. The companion test keeps its historical entry path and delegates to mirrored focused test owners. The public module now has 122 lines. Every extracted production owner and every focused companion test remains below 240 lines. The new production subpackage has nine direct Python files; the test subpackage has five.

No state schema, CID/hash rule, durable-write rule, migration rule, public function name, failure identity, or CLI action changes in this repair.

## Preservation proof

The original `500b6d2f` source contains 41 top-level production definitions. AST comparison against the extracted owners finds all 41 definitions and no changed definition bodies. The original companion contains 13 test methods. All 13 remain AST-identical in the focused test owners.

Focused state-DAG tests pass 13/13 before and after the split. A broader custody/recovery/admission/projection selection passes every state-DAG consumer that does not require MLX. Two `test_prepared_successor.py` cases fail because the local verification environment has no `mlx` module. The untouched `500b6d2f` baseline produces the same two failures and the same 10 passing tests.

Repository checks after the split:

```text
python3 -B scripts/check_module_size.py --changed-from 500b6d2f
DEVELOPMENT_STRUCTURE_CHECK OK violations=0

python3 -B scripts/quality/check_governance_integrity.py --base-ref 500b6d2f
GOVERNANCE_INTEGRITY_CHECK OK violations=0

python3 -B scripts/code_smell_audit.py --changed-from 500b6d2f --check-baseline docs/evidence/development/code_smell_baseline.json
New changed-file findings: 0

git diff --check 500b6d2f
PASS
```

`python -m bilqis_mlx.state_dag --help` still exposes `status`, `migrate`, and `migrate-history`.

## Remaining C11.1 state

This is a structural checkpoint only. It does not satisfy production BAMF create/resume or accepted B13/A12 run/source authority. The next queued structure interruptions remain `data_plane.py`, `curriculum_compiler.py`, and `registry_ast.py`, one owner at a time. Durable student start and PR merge remain human-owned.
