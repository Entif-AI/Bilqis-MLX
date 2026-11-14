"""Run the GUI05 differential gate with a terminal two-hour resource boundary."""
import os
import signal
import subprocess


process = subprocess.Popen(["npm", "run", "verify:leaf"], start_new_session=True)
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
