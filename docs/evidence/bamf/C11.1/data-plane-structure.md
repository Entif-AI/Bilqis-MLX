# C11.1 data-plane structure interruption

## Scope

Issue #522 next encountered `bilqis_mlx/data_plane.py` at 586 lines. Its direct companion test was already 155 lines, but the production owner violated the active structure contract. The repair keeps `bilqis_mlx.data_plane` as the public module and moves cohesive internal owners under `bilqis_mlx/_data_plane/`. Focused companion tests mirror those owners under `runtime/tests/custody/data_plane/` while the historical test entry path remains available.

The public facade is 68 lines. Every extracted production and focused test file is below 240 lines. The internal production package has eight direct Python files and the test package has five. The root `bilqis_mlx/` direct-file count does not increase.

No schema version, SQLite durability setting, object/node hash behavior, event-ledger indexing rule, custody scope, hardlink dedupe rule, public error identity, or CLI action changes.

## Preservation proof

Against pre-interruption head `63b1acd1`, all 15 original non-`DataPlane` top-level definitions are AST-identical and all 13 original `DataPlane` methods are AST-identical after extraction. All seven original companion test methods remain AST-identical in the focused owners.

The extraction initially omitted the original `@contextmanager` and `@staticmethod` decorators. Focused tests exposed both defects immediately. Restoring the exact decorators returns the original AST identities and all baseline behavior.

Focused data-plane tests pass 7/7. A broader custody/outbox/teacher-observation/state-DAG selection passes 39/39. The existing facade monkeypatch seam for `bilqis_mlx.data_plane._digest_file` remains exercised by the unchanged hardlink-cache test.

Repository checks:

```text
python3 -B scripts/check_module_size.py --changed-from 63b1acd1
DEVELOPMENT_STRUCTURE_CHECK OK violations=0

python3 -B scripts/quality/check_governance_integrity.py --base-ref 63b1acd1
GOVERNANCE_INTEGRITY_CHECK OK violations=0

python3 -B scripts/code_smell_audit.py --changed-from 63b1acd1 --check-baseline docs/evidence/development/code_smell_baseline.json
New changed-file findings: 0

git diff --check
PASS
```

`python -m bilqis_mlx.data_plane --help` still exposes `status`, `warm-custody`, `warm-events`, and `dedupe-bundles`.

## Remaining C11.1 state

This is structural only. It does not supply production B13/A12 source/run authority or complete #522. The next queued interruptions are `curriculum_compiler.py` and `registry_ast.py`, one owner at a time.
