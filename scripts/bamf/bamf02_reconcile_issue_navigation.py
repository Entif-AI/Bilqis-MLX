"""Regenerate navigation from the authoritative BAMF-0.2 issue mirrors.

Does not edit issue contract prose or neural/student state. Rerunnable; the
original 43 issue bodies remain byte-identical inside the generated issue book.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TASKS=ROOT/'docs/tasks/bamf-0.2'
WS=json.loads((TASKS/'workstack.json').read_text(encoding='utf-8'))
INDEX=json.loads((TASKS/'children/registry.json').read_text(encoding='utf-8'))
ISSUES=json.loads((TASKS/'issue-map.json').read_text(encoding='utf-8'))


def main():
    owners=WS['items']
    children=INDEX['entries']
    by_lane=Counter(item['lane'] for item in owners)
    child_lanes=Counter(e['key'][0] for e in children)
    if len(owners)!=43 or by_lane!=Counter({'A':13,'B':14,'C':16}):
        raise RuntimeError('original owner census changed')
    if any(not item.get('children') for item in owners):
        raise RuntimeError('some original owners have no native child tree')

    # Preserve every full current owner body without re-authoring its content.
    index_note=(
        '<!-- BAMF02:LIVE-DECOMPOSITION-DIRECTIVE -->\n'
        '> Active implementation starts at the deepest dependency-ready native GitHub child, '
        'not the original broad owner. All 43 original specifications, engineering '
        'constraints and acceptance contracts remain intact. The exact complete '
        'child tree is `children/registry.json`. No predecessor BAV crosswalk, '
        'live trainer experiment or new research gate is part of this issue-grooming pass.\n'
    )
    parent_texts=[(TASKS/'issues'/f"{item['key']}.md").read_text(encoding='utf-8').rstrip('\n') for item in owners]
    book='# BAMF-0.2 complete implementation issue book\n\n'+index_note+'\n'+'\n\n---\n\n'.join(parent_texts)+'\n'
    (TASKS/'ISSUE_BOOK.md').write_text(book,encoding='utf-8')

    summary=(f"43 original complete owner contracts across three lanes; "
             f"{len(children)} native recursively linked child nodes "
             f"(A {child_lanes['A']}, B {child_lanes['B']}, C {child_lanes['C']}).")
    ready={
        'A':('A01.1','A01'),
        'B':('B01.1a','B01'),
        'C':('C01.1','C01'),
    }
    readme=TASKS/'README.md'
    r=readme.read_text(encoding='utf-8')
    marker='<!-- BAMF02:ALL-LANES-GROOMED-20261027 -->'
    update=(f"{marker}\n## Current native issue-tree routing | 27 October 2026\n\n"
            f"{summary} Assign an agent **only to a deepest ready implementable child**, "
            f"never to an intermediate group or an original integration parent. If a child "
            f"remains too large, recursively subdivide it without dropping source clauses, "
            f"technical details or original acceptance. See [full native child registry](children/README.md), "
            f"[machine-readable tree](children/registry.json) and updated [complete parent book](ISSUE_BOOK.md).\n\n"
            f"First ready child candidates: A [{ready['A'][0]} #{ISSUES[ready['A'][0]]}](https://github.com/Entif-AI/Bilqis-MLX/issues/{ISSUES[ready['A'][0]]}), "
            f"B [{ready['B'][0]} #{ISSUES[ready['B'][0]]}](https://github.com/Entif-AI/Bilqis-MLX/issues/{ISSUES[ready['B'][0]]}), "
            f"C [{ready['C'][0]} #{ISSUES[ready['C'][0]]}](https://github.com/Entif-AI/Bilqis-MLX/issues/{ISSUES[ready['C'][0]]}). "
            f"Readiness still depends on actual upstream branch/receipt state and existing one-writer rules.\n\n")
    if marker in r:
        head,tail=r.split(marker,1)
        idx=tail.find('## Parallel start\n')
        if idx<0:raise RuntimeError('cannot locate exact parallel start anchor')
        r=head+update+tail[idx:]
    else:
        p='## Parallel start\n'
        if r.count(p)!=1:raise RuntimeError('missing README anchor')
        r=r.replace(p,update+p,1)
    readme.write_text(r,encoding='utf-8')

    for lane,(child,parent) in ready.items():
        f=TASKS/f'EXECUTION_LANE_{lane}.md'
        s=f.read_text(encoding='utf-8')
        marker=f'<!-- BAMF02:LANE-{lane}-DEEP-ENTRYPOINT -->'
        update=(f'{marker}\n**Current low-burn launch:** start with the deepest ready child '
                f'[{child} #{ISSUES[child]}](https://github.com/Entif-AI/Bilqis-MLX/issues/{ISSUES[child]}), '
                f'not the original broad [{parent} #{ISSUES[parent]}](https://github.com/Entif-AI/Bilqis-MLX/issues/{ISSUES[parent]}). '
                f'Follow `children/registry.json` for child prerequisites and native parents. '
                f'Original parent remains the complete integration/acceptance contract; '
                f'all technical requirements and existing EGM guardrails are unchanged. '
                f'No live training starts from issue planning.\n\n')
        if marker in s:
            before,after=s.split(marker,1)
            next_heading=after.find('## Bootstrap once\n')
            if next_heading<0:raise RuntimeError('missing lane bootstrap anchor')
            s=before+update+after[next_heading:]
        else:
            p='## Bootstrap once\n'
            if s.count(p)!=1:raise RuntimeError('missing lane anchor')
            s=s.replace(p,update+p,1)
        f.write_text(s,encoding='utf-8')
    print(summary)
    print('PASS: issue book regenerated from exact 43 mirrors; three current launch entries updated')


if __name__=='__main__':
    main()
