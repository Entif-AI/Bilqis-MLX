"""Versioned, parameterized, read-only semantic query runner (#77)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from .errors import ProfileError
from .falkor_import import Importer,connect
from .falkor_lookup import Reader

SUITE_PATH=Path(__file__).with_name('smoke_queries.json')
MUTATION=re.compile(r'\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|LOAD|CALL|FOREACH)\b',re.I)


def run_smoke(reader,suite_path=SUITE_PATH):
    payload=Path(suite_path).read_bytes();suite=json.loads(payload)
    if suite.get('schema')!='bilqis.skos.smoke-suite/v1' or suite.get('version')!='1.0.0':
        raise ProfileError('FALKOR_SMOKE_SUITE_UNSUPPORTED')
    ids=[case.get('id') for case in suite['queries']]
    if not ids or any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):
        raise ProfileError('FALKOR_SMOKE_QUERY_ID_INVALID')
    cases=[]
    for case in suite['queries']:
        if MUTATION.search(case['cypher']):raise ProfileError('FALKOR_SMOKE_MUTATION_FORBIDDEN',case['id'])
        rows=reader.query(case['cypher'],case['params'])
        cases.append({'id':case['id'],'passed':rows==case['expected'],'expected':case['expected'],'actual':rows})
    return {'schema':'bilqis.skos.smoke-report/v1','suite_version':suite['version'],
            'suite_sha256':hashlib.sha256(payload).hexdigest(),'canonical_sha256':reader.canonical_sha256,
            'passed':all(c['passed'] for c in cases),'cases':cases}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph',required=True);parser.add_argument('--owner',required=True)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=16379)
    parser.add_argument('--suite',type=Path,default=SUITE_PATH);args=parser.parse_args(argv)
    report=run_smoke(Reader(Importer(connect(args.host,args.port),args.graph,args.owner)),args.suite)
    print(json.dumps(report,ensure_ascii=False,sort_keys=True));return 0 if report['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
