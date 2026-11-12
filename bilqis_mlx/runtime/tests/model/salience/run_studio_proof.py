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


GIB = 1024 ** 3
MAX_AUTHORIZED_CONCURRENT_GIB = 24


STAGES = (
    ('ordinal-loss', ('bilqis_mlx/runtime/tests/model/salience/test_salience_loss.py',)),
    ('factory-integration', ('bilqis_mlx/runtime/tests/model/salience/test_factory_salience_execution.py',)),
    ('affected-owners', (
        'bilqis_mlx/runtime/tests/model/execution/test_atlas_model_forward.py',
        'bilqis_mlx/runtime/tests/model/execution/test_atlas_model_forward_training.py',
        'bilqis_mlx/learning/atlas_readout/decoder/tests/test_losses.py',
    )),
)
DEFAULT_STAGE_LABELS = ('ordinal-loss',)


def _selected_stage_labels(*, include_native_integration=False,
                           include_affected_owners=False):
    selected = list(DEFAULT_STAGE_LABELS)
    if include_native_integration:
        selected.append('factory-integration')
    if include_affected_owners:
        selected.append('affected-owners')
    return tuple(selected)


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
    markers = ('run_studio_proof.py --_stage ', 'run_tests.py', ' -m pytest ', 'bilqis_mlx.cli train', 'bilqis_mlx.cli bamf')
    return tuple(sorted(pid for pid, (_, command) in rows.items()
                        if pid not in own and 'python' in command.lower()
                        and any(marker in command for marker in markers)))


def _resources_ready(*, allow_concurrent_mlx=False, max_memory_gib=None):
    swap = subprocess.run(['sysctl', 'vm.swapusage'], check=True,
                          capture_output=True, text=True).stdout
    pressure = subprocess.run(['memory_pressure', '-Q'], check=True,
                              capture_output=True, text=True).stdout
    print(swap + pressure, flush=True)
    values = re.search(r'total = ([0-9.]+)M.*used = ([0-9.]+)M', swap)
    free = re.search(r'memory free percentage: ([0-9]+)%', pressure)
    if values is None or free is None:
        print('C06_STUDIO_RESOURCE_STATUS_UNVERIFIED', flush=True)
        return False
    total, used = map(float, values.groups())
    if allow_concurrent_mlx:
        if (max_memory_gib is None or max_memory_gib <= 0
                or max_memory_gib > MAX_AUTHORIZED_CONCURRENT_GIB):
            print('C06_STUDIO_CONCURRENT_MEMORY_BUDGET_INVALID', flush=True)
            return False
        if int(free.group(1)) < 10:
            print('C06_STUDIO_RESOURCE_HOLD memory_pressure', flush=True)
            return False
        print(f'C06_STUDIO_CONCURRENT_RESOURCE_OVERRIDE max_memory_gib={max_memory_gib}',
              flush=True)
        return True
    if (total > 0 and used / total >= .9) or int(free.group(1)) < 10:
        print('C06_STUDIO_RESOURCE_HOLD swap_or_pressure', flush=True)
        return False
    return True


def _process_tree_rss_bytes(root_pid):
    result = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], check=True,
                            capture_output=True, text=True)
    rows = {}
    for line in result.stdout.splitlines():
        fields = line.strip().split()
        if len(fields) == 3:
            rows[int(fields[0])] = (int(fields[1]), int(fields[2]))
    descendants = {root_pid}
    while True:
        more = {pid for pid, (parent, _) in rows.items() if parent in descendants}
        if more <= descendants:
            break
        descendants.update(more)
    return sum(rows.get(pid, (0, 0))[1] for pid in descendants) * 1024


def _native_stage(label, max_memory_gib=None):
    root = Path(__file__).resolve().parents[5]
    sys.path.insert(0, str(root))
    import mlx.core as mx
    from bilqis_mlx.runtime.mlx_memory import training_memory_policy
    from scripts.run_tests import main as run_tests
    with training_memory_policy(mx) as policy:
        limit_bytes = None if max_memory_gib is None else int(max_memory_gib * GIB)
        previous_limit = None
        if limit_bytes is not None:
            previous_limit = mx.set_memory_limit(limit_bytes)
            mx.reset_peak_memory()
        print(f'C06_MEMORY_POLICY {policy} memory_limit_bytes={limit_bytes}', flush=True)
        try:
            return run_tests(dict(STAGES)[label], root=root)
        finally:
            if limit_bytes is not None:
                peak = mx.get_peak_memory()
                print(f'C06_MEMORY_PEAK bytes={peak} limit_bytes={limit_bytes}', flush=True)
                if previous_limit is not None:
                    mx.set_memory_limit(previous_limit)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', type=Path)
    parser.add_argument('--_stage', choices=tuple(dict(STAGES)))
    parser.add_argument('--allow-concurrent-mlx', action='store_true')
    parser.add_argument('--max-memory-gib', type=float)
    parser.add_argument('--include-native-integration', action='store_true')
    parser.add_argument('--include-affected-owners', action='store_true')
    args = parser.parse_args()
    if args._stage:
        return _native_stage(args._stage, args.max_memory_gib)
    if args.lock is None:
        parser.error('--lock is required for the coordinator')
    if args.allow_concurrent_mlx and (args.max_memory_gib is None
            or args.max_memory_gib <= 0
            or args.max_memory_gib > MAX_AUTHORIZED_CONCURRENT_GIB):
        parser.error('--allow-concurrent-mlx requires --max-memory-gib in (0, 24]')
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    selected = _selected_stage_labels(
        include_native_integration=args.include_native_integration,
        include_affected_owners=args.include_affected_owners,
    )
    with args.lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not args.allow_concurrent_mlx:
            previous = None
            while other := _other_workers():
                if other != previous:
                    print('C06_STUDIO_WAIT active_worker_pids=' + ','.join(map(str, other)), flush=True)
                    previous = other
                time.sleep(10)
        print('C06_STUDIO_SERIAL_LANE_ACQUIRED', flush=True)
        for label in selected:
            if not _resources_ready(
                    allow_concurrent_mlx=args.allow_concurrent_mlx,
                    max_memory_gib=args.max_memory_gib):
                return 75
            start = time.monotonic()
            print('C06_STAGE_START ' + label, flush=True)
            with TemporaryFile(mode='w+', encoding='utf-8') as output:
                command = [sys.executable, '-B', __file__, '--_stage', label]
                if args.max_memory_gib is not None:
                    command += ['--max-memory-gib', str(args.max_memory_gib)]
                child = subprocess.Popen(command,
                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'BILQIS_TEST_WORKERS': '1'},
                    stdout=output, stderr=subprocess.STDOUT)
                while child.poll() is None:
                    if args.max_memory_gib is not None:
                        rss = _process_tree_rss_bytes(child.pid)
                        if rss > int(args.max_memory_gib * GIB):
                            child.terminate()
                            child.wait()
                            output.seek(0)
                            print(output.read(), flush=True)
                            print('C06_STUDIO_MEMORY_LIMIT_EXCEEDED '
                                  f'rss_bytes={rss} limit_bytes={int(args.max_memory_gib * GIB)}',
                                  flush=True)
                            return 137
                    if not args.allow_concurrent_mlx and (other := _other_workers()):
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
