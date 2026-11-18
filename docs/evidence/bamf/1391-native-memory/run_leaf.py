"""Snapshot-local, fail-fast leaf qualification for issue #1391."""
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
    "BILQIS_TEST_BASE_REF": "71a00bb90bfc261746a5e613e68f791b8ba9ad70",
    "BILQIS_QUALITY_BASE_REF": "71a00bb90bfc261746a5e613e68f791b8ba9ad70",
    "PYTHONPATH": str(bootstrap) + os.pathsep + str(root),
    "PATH": str(Path(sys.executable).parent) + os.pathsep + "/opt/homebrew/bin:" + os.environ["PATH"],
})
started = time.monotonic()
# 36 selected files; expected 20–45 minutes including static Git-history checks.
# A single complete leaf claim; the timeout is a failure boundary, never PASS.
print("STAGE leaf: static quality, affected tests, Node and security", flush=True)
result = subprocess.run(
    ["npm", "run", "verify:leaf"], env=environment, timeout=80 * 60)
print(f"STAGE leaf exit={result.returncode} seconds={time.monotonic() - started:.3f}", flush=True)
raise SystemExit(result.returncode)
