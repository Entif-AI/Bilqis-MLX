"""Run the GUI05 differential gate with a terminal two-hour resource boundary."""
import os
import signal
import subprocess
from pathlib import Path


root = Path.cwd()
os.environ["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "apps/mission-control/tests/qualification")))
command = ("/bin/zsh", "-c",
           "npm run quality:check && python3 -B apps/mission-control/tests/qualification/preflight.py "
           "&& npm run verify:leaf && npm run verify:premerge")
print("GUI05_QUALIFICATION_PHASES static, collection, leaf, premerge", flush=True)
process = subprocess.Popen(command, start_new_session=True)
try:
    status = process.wait(timeout=2 * 60 * 60)
except subprocess.TimeoutExpired:
    print("Verification incomplete: two-hour ceiling reached.", flush=True)
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    status = 124
raise SystemExit(status)
