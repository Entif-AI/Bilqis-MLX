"""v15 read-only watcher, reusing the unchanged v11-derived renderer."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import time_first_dashboard_watch as original
from . import time_first_runner_v15 as runner


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--follow',action='store_true')
    p.add_argument('--log-file',type=Path)
    a=p.parse_args()
    original.watch(run_dir=runner.RUN,log_file=a.log_file,follow=a.follow)


if __name__=='__main__':
    main()
