"""Plan and atomically guard deletion of one explicitly owned projection (#75)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import ProfileError
from .falkor_import import Importer,connect
from .falkor_projection import VERSION


def plan_reset(importer):
    state=importer.status()
    if state.get('version')!=VERSION:raise ProfileError('FALKOR_RESET_VERSION_UNSUPPORTED')
    rows=importer._read('MATCH(n) WHERE n.owner=$owner RETURN properties(n),labels(n)',{'owner':importer.owner})
    nodes=[];blockers=[]
    for props,labels in rows:
        if 'BilqisProjection' in labels: continue
        if 'RdfTerm' not in labels or not props.get('key'):
            blockers.append({'code':'UNCLASSIFIED_OWNED_NODE','key':props.get('key','')})
        else:nodes.append(props['key'])
    node_set=set(nodes)
    edges=[]
    boundaries=importer._read('MATCH(a)-[e]->(b) WHERE a.owner=$owner OR b.owner=$owner OR e.owner=$owner RETURN a.key,a.owner,e.key,e.owner,type(e),b.key,b.owner',{'owner':importer.owner})
    for source,source_owner,key,owner,kind,target,target_owner in boundaries:
        if source_owner!=importer.owner or target_owner!=importer.owner or owner!=importer.owner or kind!='RDF' or source not in node_set or target not in node_set:
            blockers.append({'code':'FOREIGN_BOUNDARY','source':source or '', 'edge':key or '', 'target':target or '', 'relationship_type':kind})
        else:edges.append(key)
    return {'schema':'bilqis.skos.reset-plan/v1','graph':importer.name,'owner':importer.owner,
            'canonical_sha256':state['digest'],'state':state['state'],'projection_version':state['version'],
            'owned_nodes':len(nodes),'owned_edges':len(edges),'node_keys':sorted(nodes),'edge_keys':sorted(edges),
            'foreign_nodes_touching_owned_edges':[{'source':s or '', 'edge':k or '', 'target':t or ''} for s,so,k,eo,kind,t,to in boundaries if eo==importer.owner and (so!=importer.owner or to!=importer.owner)],
            'foreign_edges_touching_owned_nodes':[k or '' for s,so,k,eo,kind,t,to in boundaries if eo!=importer.owner and (so==importer.owner or to==importer.owner)],
            'blockers':sorted(blockers,key=lambda v:json.dumps(v,sort_keys=True))}


RESET_QUERY="""
MATCH (m:BilqisProjection {owner:$owner,digest:$digest,state:$state,version:$version})
OPTIONAL MATCH (n:RdfTerm) WHERE n.owner=$owner
WITH m,n ORDER BY n.key
WITH m,collect(n) AS owned
WHERE [n IN owned | n.key]=$node_keys
OPTIONAL MATCH (a)-[bad]->(b)
WHERE (a.owner=$owner OR b.owner=$owner OR bad.owner=$owner)
AND (coalesce(a.owner,'')<>$owner OR coalesce(b.owner,'')<>$owner
 OR coalesce(bad.owner,'')<>$owner OR type(bad)<>'RDF'
 OR NOT ('RdfTerm' IN labels(a)) OR NOT ('RdfTerm' IN labels(b)))
WITH m,owned,count(bad) AS bad_count WHERE bad_count=0
OPTIONAL MATCH ()-[e:RDF]->() WHERE e.owner=$owner
WITH m,owned,e ORDER BY e.key
WITH m,owned,collect(e) AS edges
WHERE [e IN edges | e.key]=$edge_keys
SET m.state='resetting'
FOREACH (e IN edges | DELETE e)
FOREACH (n IN owned | DELETE n)
SET m.state='empty',m.digest='',m.nodes=0,m.edges=0
RETURN size(owned),size(edges)
"""


def reset_owned(importer,plan):
    if not isinstance(plan,dict) or plan.get('schema')!='bilqis.skos.reset-plan/v1':
        raise ProfileError('FALKOR_RESET_PLAN_INVALID')
    if plan.get('graph')!=importer.name or plan.get('owner')!=importer.owner:
        raise ProfileError('FALKOR_RESET_TARGET_MISMATCH')
    if plan.get('blockers'):
        raise ProfileError('FALKOR_RESET_FOREIGN_BOUNDARY',*(json.dumps(b,sort_keys=True) for b in plan['blockers']))
    if plan_reset(importer)!=plan:
        raise ProfileError('FALKOR_RESET_PLAN_STALE')
    params={'owner':importer.owner,'digest':plan['canonical_sha256'],'state':plan['state'],
            'node_keys':plan['node_keys'],'edge_keys':plan['edge_keys'],'version':plan['projection_version']}
    try:
        result=importer.graph.query(RESET_QUERY,params).result_set
    except Exception as error:
        raise ProfileError('FALKOR_RESET_RECONCILE_REQUIRED',type(error).__name__) from error
    if result!=[[plan['owned_nodes'],plan['owned_edges']]]:
        raise ProfileError('FALKOR_RESET_PLAN_STALE')
    state=importer.status()
    if state['state']!='empty' or state['nodes'] or state['edges']:
        raise ProfileError('FALKOR_RESET_READBACK_REQUIRED')
    return {'status':'empty','graph':importer.name,'owner':importer.owner,
            'deleted_nodes':plan['owned_nodes'],'deleted_edges':plan['owned_edges']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph',required=True);parser.add_argument('--owner',required=True)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=16379)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--plan',type=Path)
    args=parser.parse_args(argv)
    importer=Importer(connect(args.host,args.port),args.graph,args.owner)
    try:
        if args.execute:
            if not args.plan:raise ProfileError('FALKOR_RESET_REVIEWED_PLAN_REQUIRED')
            result=reset_owned(importer,json.loads(args.plan.read_text()))
        else:result=plan_reset(importer)
    except (ProfileError,OSError,ValueError) as error:
        print(json.dumps({'status':'refused','code':getattr(error,'code',type(error).__name__)}));return 2
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
