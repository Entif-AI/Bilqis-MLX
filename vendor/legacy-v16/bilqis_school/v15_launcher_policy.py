"""Resolve v15's immutable champion epoch before its human-operated launcher.

Read only. The checkpoint/state remains authoritative; no policy migration,
new run creation, lock acquisition or model/AdamW mutation occurs here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

VERSION='bilqis.primitive-consolidation.run-local/v15'
BOUNDARIES={
    'session':'AFTER_OPERATOR_SESSION_ONLY',
    'complete-program':'ON_FULL_29_GRADE_COLLECTION',
}


def resolve_boundary(run_dir:Path, requested:str|None)->str:
    if requested is not None and requested not in BOUNDARIES:
        raise ValueError('V15_UNSUPPORTED_CHAMPION_BOUNDARY:'+requested)
    saved=Path(run_dir)/'state.json'
    if saved.is_symlink():
        raise ValueError('V15_UNSAFE_FROZEN_RUN_STATE_PATH')
    if not saved.exists():
        # Preparation of a new run still defaults to session unless its
        # operator explicitly selects complete-program.
        return requested or 'session'
    if not saved.is_file() or saved.is_symlink():
        raise ValueError('V15_UNSAFE_FROZEN_RUN_STATE_PATH')
    state=json.loads(saved.read_text())
    if not isinstance(state,dict):
        raise ValueError('V15_INVALID_FROZEN_RUN_STATE')
    if state.get('version')!=VERSION:
        raise ValueError('V15_RUN_VERSION_MISMATCH')
    config=state.get('config')
    if not isinstance(config,dict):
        raise ValueError('V15_MISSING_FROZEN_CONFIGURATION')
    frozen=config.get('champion_boundary')
    if not isinstance(frozen,str) or frozen not in BOUNDARIES:
        raise ValueError('V15_UNSUPPORTED_CHAMPION_BOUNDARY:'+str(frozen))
    if config.get('session_soup_refresh')!=BOUNDARIES[frozen]:
        raise ValueError('V15_FROZEN_SOUP_REFRESH_POLICY_MISMATCH')
    if requested is not None and requested!=frozen:
        raise ValueError('V15_CHAMPION_BOUNDARY_CONFLICT: frozen='+frozen+
                         ' requested='+requested+'; unset CHAMPION_BOUNDARY '
                         'or specify its frozen value')
    return frozen


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--requested',choices=tuple(BOUNDARIES))
    args=p.parse_args()
    try:
        print(resolve_boundary(args.run_dir,args.requested))
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        p.exit(4,str(exc)+'\n')


if __name__=='__main__':main()
