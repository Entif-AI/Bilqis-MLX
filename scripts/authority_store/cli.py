#!/usr/bin/env python3
"""Operate the fixed BAMF ordinary-user authority store without selecting its path."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.authority_store.lifecycle import AuthorityStoreOperator


def _bytes(path: Path | None) -> bytes | None:
    return None if path is None else path.read_bytes()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    sub.add_parser("recover")

    install = sub.add_parser("install")
    install.add_argument("--registry", type=Path, required=True)
    install.add_argument("--signer", type=Path)

    sub.add_parser("backup")
    sub.add_parser("restore")

    for operation in ("rotate", "migrate"):
        change = sub.add_parser(operation)
        change.add_argument("--registry", type=Path, required=True)
        change.add_argument("--signer", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    operator = AuthorityStoreOperator()
    if args.command == "verify":
        status = operator.verify()
    elif args.command == "recover":
        status = operator.recover()
    elif args.command == "install":
        status = operator.install(
            args.registry.read_bytes(),
            signer_bytes=_bytes(args.signer),
        )
    elif args.command == "backup":
        status = operator.backup()
    elif args.command == "restore":
        status = operator.restore()
    elif args.command in ("rotate", "migrate"):
        operation = operator.rotate if args.command == "rotate" else operator.migrate
        status = operation(
            args.registry.read_bytes(), signer_bytes=args.signer.read_bytes(),
        )
    else:  # pragma: no cover - argparse owns the command domain.
        raise AssertionError(args.command)
    print(json.dumps(status.to_record(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
