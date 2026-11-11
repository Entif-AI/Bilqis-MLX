"""Run C06 proof stages after other Studio tests yield the shared device."""
from __future__ import annotations

import argparse
import fcntl
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from tempfile import TemporaryFile


STAGES = (
    ('ordinal-loss', ('bilqis_mlx/runtime/tests/model/salience/test_salience_loss.py',)),
    ('factory-integration', ('bilqis_mlx/runtime/tests/model/salience/test_factory_salience_execution.py',)),
    ('affected-owners', (
        'bilqis_mlx/runtime/tests/model/execution/test_atlas_model_forward.py',
        'bilqis_mlx/runtime/tests/model/execution/test_atlas_model_forward_training.py',
        'bilqis_mlx/learning/atlas_readout/decoder/tests/test_losses.py',
    )),
)


def _processes():
    result = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], check=True,
                            capture_output=True, text=True)
    rows = {}
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) == 3:
            rows[int(fields[0])] = (int(fields[1]), fields[2])
    return rows


def _other_workers():
    rows = _processes()
    own = {os.getpid()}
    parent = os.getppid()
    while parent in rows and parent not in own:
        own.add(parent)
        parent = rows[parent][0]
    descendants = {os.getpid()}
    while True:
        more = {pid for pid, (parent, _) in rows.items() if parent in descendants}
        if more <= descendants:
            break
        descendants.update(more)
    own.update(descendants)
    markers = ('run_tests.py', ' -m pytest ', 'bilqis_mlx.cli train', 'bilqis_mlx.cli bamf')
    return tuple(sorted(pid for pid, (_, command) in rows.items()
                        if pid not in own and 'python' in command.lower()
                        and any(marker in command for marker in markers)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', type=Path, required=True)
    args = parser.parse_args()
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    with args.lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = None
        while other := _other_workers():
            if other != previous:
                print('C06_STUDIO_WAIT active_worker_pids=' + ','.join(map(str, other)), flush=True)
                previous = other
            time.sleep(10)
        print('C06_STUDIO_SERIAL_LANE_ACQUIRED', flush=True)
        for label, paths in STAGES:
            start = time.monotonic()
            print('C06_STAGE_START ' + label, flush=True)
            with TemporaryFile(mode='w+', encoding='utf-8') as output:
                child = subprocess.Popen([sys.executable, '-B', 'scripts/run_tests.py', *paths],
                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                    stdout=output, stderr=subprocess.STDOUT)
                while child.poll() is None:
                    if other := _other_workers():
                        child.terminate()
                        child.wait()
                        output.seek(0)
                        print(output.read(), flush=True)
                        print('C06_STUDIO_COLLISION active_worker_pids=' + ','.join(map(str, other)), flush=True)
                        return 75
                    time.sleep(1)
                output.seek(0)
                transcript = output.read()
            print(transcript, end='', flush=True)
            print(f'C06_STAGE_DONE {label} exit={child.returncode} seconds={time.monotonic()-start:.3f}',
                  flush=True)
            if child.returncode:
                return child.returncode
            totals = re.findall(r'TEST_TOTALS total=(\d+) passed=(\d+) failed=(\d+) skipped=(\d+) errors=(\d+)',
                                transcript)
            if not totals or int(totals[-1][0]) == 0 or any(int(value) for value in totals[-1][2:]):
                print('C06_STAGE_INCOMPLETE missing, skipped or unsuccessful required evidence', flush=True)
                return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
