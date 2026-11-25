"""Execute one explicitly selected, source-bound witness setup and callback.

Witness files define prepare(argv, probes) -> callable. Module initialization
and prepare must be neural-inert; the returned callback owns expensive work.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType

from .checked_launch import CONTRACT_ENV
from .imports import import_failure_hint, resolve_module, validate_loaded
from .probes import ProbeBook


def execute(mode: str, path: Path, digest: str, argv: list[str]) -> int:
    root = Path.cwd().resolve()
    if not Path(__file__).resolve().is_relative_to(root):
        raise ImportError("checked-witness runner imported outside snapshot")
    resolve_module("bilqis_mlx", root)
    path = path.resolve()
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != digest:
        raise RuntimeError(f"checked witness source changed: {path}")
    module = ModuleType("_bilqis_checked_witness")
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    probes = ProbeBook(root)
    try:
        exec(compile(source, str(path), "exec"), vars(module))
        prepare = getattr(module, "prepare", None)
        if not callable(prepare):
            raise TypeError("checked witness must define prepare(argv, probes)")
        run = prepare(argv, probes)
        if not callable(run):
            raise TypeError("witness prepare must return an expensive-phase callback")
        probes.verify()
        contract = probes.contract_sha256()
        if mode == "preflight":
            print("CHECKED_WITNESS_PREFLIGHT_PASS " + contract, flush=True)
            return 0
        if mode != "run":
            raise ValueError(f"invalid checked witness mode: {mode}")
        expected = os.environ.get(CONTRACT_ENV)
        if expected is not None and contract != expected:
            raise RuntimeError("checked witness probe contract changed after preflight")
        probes.reset()
        result = run()
        if result is not None and type(result) is not int:
            raise TypeError("witness callback must return None or an integer exit code")
        if result:
            return result
        probes.require_calls()
        validate_loaded(root)
        print("CHECKED_WITNESS_COMPLETE " + json.dumps({
            "probe_contract_sha256": contract, "probe_results": probes.results(),
        }, sort_keys=True), flush=True)
        return 0
    except ModuleNotFoundError as error:
        hint = import_failure_hint(source, error, root)
        if hint:
            raise ImportError(f"{error}{hint}") from error
        raise
    except SystemExit as error:
        raise RuntimeError("checked witness exited before completing its contract") from error
    finally:
        probes.restore()
        sys.modules.pop(module.__name__, None)


def main():
    mode, path, digest, *argv = sys.argv[1:]
    return execute(mode, Path(path), digest, argv)


if __name__ == "__main__":
    raise SystemExit(main())
