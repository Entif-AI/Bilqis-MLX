"""Fail early on collection defects using the final gates' own loaders."""
from pathlib import Path
import subprocess
import unittest

from scripts import run_tests
from scripts.skos_test_policy import plan as skos_plan
from scripts.testing.differential_test_gate import plan_leaf, _pytest_command


root = Path.cwd()
leaf = plan_leaf(root)
print(f"COLLECTION_PREFLIGHT leaf_files={len(leaf.tests)}", flush=True)
status = subprocess.run(_pytest_command(leaf.mode, leaf.tests) + ["--collect-only"],
                        check=False).returncode
if status:
    raise SystemExit(status)
run_tests._install_source_only_legacy_geometry_shim()
paths = run_tests.discover_test_files(root)
if skos_plan(root).action == "SKIP":
    paths = run_tests.exclude_ithkuil_tests(paths, root)
suite = run_tests.load_test_files(paths, root)


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


failures = [case for case in cases(suite) if isinstance(case, run_tests._LoadFailure)]
print(f"COLLECTION_PREFLIGHT premerge_files={len(paths)} cases={suite.countTestCases()} "
      f"import_failures={len(failures)}", flush=True)
for failure in failures:
    print(f"{failure}: {failure._error}", flush=True)
raise SystemExit(bool(failures))
