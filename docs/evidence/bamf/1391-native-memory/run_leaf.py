"""Snapshot-local, fail-fast integration qualification for issue #1391."""
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path.cwd()
bootstrap = root / "docs/evidence/bamf/1391-native-memory/resource_bootstrap"
environment = dict(os.environ)
environment.update({
    "BILQIS_TEST_WORKERS": "1",
    "BILQIS_TEST_BASE_REF": "204a5f4769189b1dd9d334f1b7a85b4133a48110",
    "BILQIS_QUALITY_BASE_REF": "204a5f4769189b1dd9d334f1b7a85b4133a48110",
    "PYTHONPATH": str(bootstrap) + os.pathsep + str(root),
    "PATH": str(Path(sys.executable).parent) + os.pathsep + "/opt/homebrew/bin:" + os.environ["PATH"],
})
print("STAGE Node test dependencies", flush=True)
subprocess.run(["npm", "ci", "--ignore-scripts", "--omit=dev"],
               env=environment, timeout=180, check=True)
started = time.monotonic()
# Prior leaf: 18 minutes including static Git-history checks. Aggregate discovery
# contains 1,186 files / approximately 5,500 unittest methods. Expected complete
# pipeline: 45–90 minutes; terminal failure boundary below the two-hour ceiling.
deadline = started + 115 * 60
preflight = (
    "from pathlib import Path; import pytest; "
    "from scripts.run_tests import discover_test_files; "
    "raise SystemExit(pytest.main(['--collect-only', '-q', "
    "'--import-mode=importlib', *map(str, discover_test_files(Path.cwd()))]))"
)
stages = (
    ("static integration quality", ["npm", "run", "quality:check"]),
    ("aggregate import/collection preflight", [sys.executable, "-B", "-c", preflight]),
    ("affected owner tests", ["npm", "run", "test:changed"]),
    ("Node behavior", ["npm", "run", "bamf:test"]),
    ("security boundary", ["npm", "run", "bamf:security:test"]),
    ("premerge aggregate", ["npm", "run", "test:premerge"]),
)
for label, command in stages:
    print(f"STAGE {label} START", flush=True)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("integration qualification exceeded its wall-clock bound")
    result = subprocess.run(command, env=environment, timeout=remaining)
    print(f"STAGE {label} exit={result.returncode} "
          f"elapsed_seconds={time.monotonic() - started:.3f}", flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
print("INTEGRATION_QUALIFICATION_PASS", flush=True)
