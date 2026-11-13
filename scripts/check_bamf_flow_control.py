#!/usr/bin/env python3
"""Validate BAMF-0.2 lane flow control and optional live PR inventory."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__:
    from scripts.flow_control.core import (
        DEFAULT_DIR,
        FlowControlError,
        validate_flow_control,
    )
    from scripts.flow_control.live import (
        validate_live_from_environment,
        validate_live_pr_inventory,
    )
else:
    from flow_control.core import (
        DEFAULT_DIR,
        FlowControlError,
        validate_flow_control,
    )
    from flow_control.live import (
        validate_live_from_environment,
        validate_live_pr_inventory,
    )

__all__ = [
    "FlowControlError",
    "validate_flow_control",
    "validate_live_pr_inventory",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="reconcile the repository ledger against live GitHub open PR state",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", "Entif-AI/Bilqis-MLX"),
    )
    parser.add_argument(
        "--live-json",
        type=Path,
        help="test-only path containing a GitHub open-PR JSON array",
    )
    args = parser.parse_args()

    try:
        if args.live_json is not None:
            open_prs = json.loads(args.live_json.read_text(encoding="utf-8"))
            if not isinstance(open_prs, list):
                raise FlowControlError("--live-json must contain a JSON array")
            summaries = validate_live_pr_inventory(open_prs, DEFAULT_DIR)
        elif args.live:
            summaries = validate_live_from_environment(args.repository, DEFAULT_DIR)
        else:
            summaries = validate_flow_control(DEFAULT_DIR)
    except (FlowControlError, OSError, json.JSONDecodeError) as exc:
        print(f"BAMF_FLOW_CONTROL_FAIL: {exc}", file=sys.stderr)
        return 1

    print("BAMF_FLOW_CONTROL_OK")
    for summary in summaries:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
