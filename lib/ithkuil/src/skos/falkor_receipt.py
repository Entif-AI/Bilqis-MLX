"""Generate and revalidate digest-bound owned materialization receipts (#78)."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator,FormatChecker

from .errors import ProfileError
from .falkor_import import IMPORTER_VERSION,Importer,connect,load_conformant_bundle
from .falkor_lookup import INDEXES,Reader,ensure_indexes
from .falkor_projection import VERSION
from .falkor_smoke import run_smoke

PACKAGE=Path(__file__).parent
SCHEMA_PATH=PACKAGE/'materialization_receipt.schema.json'


def validate_receipt(receipt):
    schema=json.loads(SCHEMA_PATH.read_text())
    errors=sorted(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(receipt),key=lambda e:str(e.path))
    if errors:raise ProfileError('FALKOR_RECEIPT_INVALID',*(str(e.path) for e in errors))
    return receipt


def _implementation():
    from .publication import json_bytes
    files=sorted([*PACKAGE.glob('falkor*.py'),SCHEMA_PATH,PACKAGE.parents[1]/'requirements-falkor.txt'])
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=PACKAGE,capture_output=True,text=True)
    dirty=subprocess.run(['git','status','--porcelain','--',str(PACKAGE)],cwd=PACKAGE,capture_output=True,text=True)
    return {'version':IMPORTER_VERSION,'implementation_sha256':hashlib.sha256(json_bytes(hashes)).hexdigest(),
            'git_commit':commit.stdout.strip() if commit.returncode==0 else None,'dirty_source':bool(dirty.stdout)}


def build_receipt(importer,bundle,suite_path):
    expected=load_conformant_bundle(bundle)
    state=importer.status()
    if state['state']!='complete':raise ProfileError('FALKOR_RECEIPT_IMPORT_INCOMPLETE')
    actual=importer.read_projection()
    if actual!=expected:raise ProfileError('FALKOR_RECEIPT_GRAPH_DRIFT')
    smoke=run_smoke(Reader(importer),suite_path)
    if not smoke['passed']:raise ProfileError('FALKOR_RECEIPT_SMOKE_FAILED',*(c['id'] for c in smoke['cases'] if not c['passed']))
    root=Path(bundle);coverage_bytes=(root/'coverage.json').read_bytes()
    indexes=importer._read('CALL db.indexes() YIELD label, properties RETURN label,properties')
    receipt={'schema':'bilqis.skos.materialization/v1','version':'1.0.0','status':'complete',
             'timestamp':datetime.now(timezone.utc).isoformat(),'graph':importer.name,'owner':importer.owner,
             'canonical_rdf_sha256':actual['canonical_sha256'],'projection_version':VERSION,
             'semantic_coverage':{'ref':'coverage.json','sha256':hashlib.sha256(coverage_bytes).hexdigest()},
             'coverage_status':json.loads(coverage_bytes)['build_status'],'importer':_implementation(),
             'nodes_by_label':dict(sorted(Counter(label for n in actual['nodes'] for label in n['labels']).items())),
             'edges_by_type':{'RDF':len(actual['edges'])},
             'indexes':[{'label':label,'property':field,'present':any(l==label and field in fs for l,fs in indexes)} for label,field in INDEXES],
             'smoke_suite':smoke}
    validate_receipt(receipt)
    return receipt


def verify_receipt(receipt,importer,bundle,suite_path):
    validate_receipt(receipt)
    if receipt['status']!='complete':raise ProfileError('FALKOR_RECEIPT_NOT_COMPLETE')
    current=build_receipt(importer,bundle,suite_path)
    # Commit/dirty metadata records historical execution; exact implementation
    # bytes, the graph and every semantic proof must still match now.
    def comparable(value):
        return {k:({'version':v['version'],'implementation_sha256':v['implementation_sha256']} if k=='importer' else v)
                for k,v in value.items() if k!='timestamp'}
    if comparable(receipt)!=comparable(current):raise ProfileError('FALKOR_RECEIPT_STALE')
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--graph',required=True);parser.add_argument('--owner',required=True)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=16379)
    args=parser.parse_args(argv)
    try:
        importer=Importer(connect(args.host,args.port),args.graph,args.owner)
        importer.materialize(args.bundle);ensure_indexes(importer)
        receipt=build_receipt(importer,args.bundle,args.suite)
    except Exception as error:
        receipt={'schema':'bilqis.skos.materialization/v1','version':'1.0.0','status':'incomplete',
                 'timestamp':datetime.now(timezone.utc).isoformat(),'graph':args.graph,'owner':args.owner,
                 'reason':getattr(error,'code',type(error).__name__)}
        print(json.dumps(receipt,sort_keys=True));return 2
    print(json.dumps(receipt,ensure_ascii=False,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
