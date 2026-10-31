# C11.1 registry-AST structure interruption

## Scope

Issue #522 next encountered `bilqis_mlx/registry_ast.py` at 456 lines. The direct companion test is 148 lines and did not require a structural split.

The repair keeps `bilqis_mlx.registry_ast` as the public module and preserves all path-sensitive and path-qualified baseline behavior there. `REQUIRED_HEADERS`, `_table`, `parse_registry`, `load_registry`, `compiler_report`, and `main` stay at the historical public path. Immutable record types move to `_registry_ast/types.py`; digest/reference helpers move to `_registry_ast/helpers.py`; token binding and deterministic construction planning move to `_registry_ast/planning.py`. The public facade is 213 lines and every private owner is below 240 lines.

`parse_registry` remains physically at the public path because the development baseline already records its branch-density and long-function findings there. `REQUIRED_HEADERS` likewise remains at the public path because its module-mutable-literal finding is path-qualified. No baseline is moved or waived.

No registry schema, source identity, token/lesson/grade/bridge validation, dependency ordering, admission boundary, construction-frontier rule, report payload, or CLI behavior changes.

## Preservation proof

Against pre-interruption head `413ba0a`, all 21 original production definitions are present and AST-identical after extraction. The original 12 companion tests remain unchanged. Two new regressions prove historical public `__module__` identity and owner-first private imports.

Focused registry tests pass 14/14. A broader registry/source-adapter/semantic/verification/coverage selection produces 29 passes and two missing-`sympy` setup errors. The same two missing-`sympy` errors reproduce on untouched `413ba0a`; they are verification-environment limits, not candidate regressions.

Repository checks:

```text
python3 -B scripts/check_module_size.py --changed-from 413ba0a
DEVELOPMENT_STRUCTURE_CHECK OK violations=0

python3 -B scripts/quality/check_governance_integrity.py --base-ref 413ba0a
GOVERNANCE_INTEGRITY_CHECK OK violations=0

python3 -B scripts/code_smell_audit.py --changed-from 413ba0a --check-baseline docs/evidence/development/code_smell_baseline.json
New changed-file findings: 0

git diff --check
PASS
```

`python -m bilqis_mlx.registry_ast --help` is byte-identical to `413ba0a`.

A wheel built from the candidate installs into a clean target outside the checkout. Owner-first imports of `_registry_ast.helpers`, `_registry_ast.types`, and `_registry_ast.planning` succeed before the public facade. Public `Origin` and `RegistryAST` are the identical private type objects, report historical `bilqis_mlx.registry_ast` module identity, and `Origin` round-trips through pickle to the same public type.

## Remaining C11.1 state

This completes the last queued root structure interruption for #522. Production C11.1 acceptance still requires the issue's accepted B13/A12 run/source authority and complete production launch/resume proof. No durable learner, optimizer, graph service, or live-training state is changed by this repair.
