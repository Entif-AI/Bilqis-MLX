"""Idempotent, explicitly owned materialization of conformant canonical RDF (#74)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from falkordb import FalkorDB
from redis.backoff import NoBackoff
from redis.retry import Retry
from redis.exceptions import RedisError

from .conformance import GATES, validate_artifacts
from .errors import ProfileError
from .falkor_projection import SCHEMA, VERSION, project_graph, reconstruct_graph
from .no_omission import SourceRowIdentity
from .rdf_read import read_canonical_graph

LABELS = frozenset({'RdfTerm','Resource','Literal','BlankNode','Concept','ConceptScheme','Collection','OrderedCollection'})


def connect(host='127.0.0.1', port=16379):
    return FalkorDB(host=host, port=port, username=os.environ.get('BILQIS_FALKOR_USERNAME'),
                    password=os.environ.get('BILQIS_FALKOR_PASSWORD'), socket_timeout=15,
                    socket_connect_timeout=5, retry=Retry(NoBackoff(), 0))


def load_conformant_bundle(directory):
    root = Path(directory)
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    required = {'canonical.nt','comparison.nt','coverage.json','source-rows.json','conformance.json'}
    if not required <= set(manifest):
        raise ProfileError('FALKOR_CONFORMANCE_EVIDENCE_MISSING')
    payloads = {}
    for name, digest in manifest.items():
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]*',name) or (root/name).is_symlink():
            raise ProfileError('FALKOR_EVIDENCE_PATH_INVALID')
        payload = (root/name).read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ProfileError('FALKOR_EVIDENCE_DIGEST_MISMATCH', name)
        payloads[name] = payload
    graph = read_canonical_graph(payloads['canonical.nt'])
    claimed = json.loads(payloads['conformance.json'])
    if (claimed.get('status') != 'complete' or tuple(g.get('gate') for g in claimed.get('gates',[])) != GATES
            or any(g.get('status') != 'passed' for g in claimed['gates'])):
        raise ProfileError('FALKOR_CONFORMANCE_NOT_PASSED')
    rows = tuple(SourceRowIdentity(**row) for row in json.loads(payloads['source-rows.json']))
    actual = validate_artifacts(graph, json.loads(payloads['coverage.json']), rows,
                                read_canonical_graph(payloads['comparison.nt']),
                                admitted_mappings=read_canonical_graph(payloads['admitted-mappings.nt']) if 'admitted-mappings.nt' in payloads else ())
    if actual != claimed:
        raise ProfileError('FALKOR_CONFORMANCE_READBACK_MISMATCH')
    return project_graph(graph)


class Importer:
    def __init__(self, db, graph_name, owner, *, batch_size=500):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,127}',graph_name) or graph_name.lower() == 'default':
            raise ProfileError('FALKOR_EXPLICIT_GRAPH_REQUIRED')
        if not isinstance(owner,str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,128}',owner):
            raise ProfileError('FALKOR_EXPLICIT_OWNER_REQUIRED')
        if not isinstance(batch_size,int) or not 1 <= batch_size <= 1000:
            raise ProfileError('FALKOR_BATCH_SIZE_INVALID')
        self.db, self.name, self.owner, self.batch_size = db, graph_name, owner, batch_size
        self.graph = db.select_graph(graph_name)

    def _read(self, query, params=None):
        return self.graph.ro_query(query,params).result_set

    def status(self):
        if self.name not in self.db.list_graphs():
            raise ProfileError('FALKOR_GRAPH_NOT_FOUND',self.name)
        rows = self._read('MATCH (m:BilqisProjection) RETURN properties(m)')
        if len(rows) != 1 or rows[0][0].get('owner') != self.owner:
            raise ProfileError('FALKOR_OWNERSHIP_MISMATCH',self.name)
        return rows[0][0]

    def require_owned(self):
        state = self.status()
        nodes = self._read("MATCH (n) WHERE n.owner=$owner AND NOT ('RdfTerm' IN labels(n)) AND NOT ('BilqisProjection' IN labels(n)) RETURN count(n)",{'owner':self.owner})[0][0]
        edges = self._read("MATCH (a)-[e]->(b) WHERE (a.owner=$owner OR b.owner=$owner OR e.owner=$owner) AND (coalesce(e.owner,'') <> $owner OR coalesce(a.owner,'') <> $owner OR coalesce(b.owner,'') <> $owner OR type(e) <> 'RDF' OR NOT ('RdfTerm' IN labels(a)) OR NOT ('RdfTerm' IN labels(b))) RETURN count(e)",{'owner':self.owner})[0][0]
        if nodes or edges:
            raise ProfileError('FALKOR_FOREIGN_DATA_PRESENT', f'nodes={nodes}',f'edges={edges}')
        return state

    def _pages(self, query):
        offset = 0
        while True:
            rows = self._read(query+' SKIP $offset LIMIT $limit',{'owner':self.owner,'offset':offset,'limit':1000})
            yield from rows
            if len(rows) < 1000: break
            offset += len(rows)

    def read_projection(self):
        state = self.require_owned()
        nodes,edges = [],[]
        for props,labels in self._pages('MATCH (n:RdfTerm) WHERE n.owner=$owner RETURN properties(n), labels(n) ORDER BY n.key'):
            props.pop('owner',None)
            nodes.append({**props,'labels':sorted(labels)})
        for source,props,target in self._pages('MATCH (s)-[e:RDF]->(t) WHERE e.owner=$owner RETURN s.key,properties(e),t.key ORDER BY e.key'):
            props.pop('owner',None)
            edges.append({**props,'source':source,'target':target,'type':'RDF'})
        result={'schema':SCHEMA,'version':VERSION,'canonical_sha256':state['digest'],
                'triple_count':state['edges'],'nodes':nodes,'edges':edges}
        reconstruct_graph(result)
        if state['version'] != VERSION or state['nodes'] != len(nodes) or state['edges'] != len(edges):
            raise ProfileError('FALKOR_MARKER_CENSUS_MISMATCH')
        total = self._read('MATCH (n) WHERE n.owner=$owner RETURN count(n)',{'owner':self.owner})[0][0]
        if total != len(nodes)+1:
            raise ProfileError('FALKOR_UNACCOUNTED_NODES')
        return result

    def materialize(self, bundle, *, fail_after_batches=None):
        if not isinstance(bundle,(str,Path)):
            raise ProfileError('FALKOR_CONFORMANT_BUNDLE_REQUIRED')
        projection=load_conformant_bundle(bundle)
        reconstruct_graph(projection)
        params={'owner':self.owner,'digest':projection['canonical_sha256'],'version':VERSION,
                'nodes':len(projection['nodes']),'edges':len(projection['edges'])}
        if self.name not in self.db.list_graphs():
            rows=self.graph.query("MATCH (n) WITH count(n) AS count WHERE count=0 CREATE (m:BilqisProjection {owner:$owner,digest:$digest,version:$version,nodes:$nodes,edges:$edges,state:'incomplete'}) RETURN m.owner",params).result_set
            if rows != [[self.owner]]: raise ProfileError('FALKOR_GRAPH_CLAIM_REFUSED')
        state=self.require_owned()
        if state['state']=='empty':
            rows=self.graph.query("MATCH (m:BilqisProjection {owner:$owner,state:'empty',digest:''}) OPTIONAL MATCH (n:RdfTerm) WHERE n.owner=$owner WITH m,count(n) AS count WHERE count=0 SET m.digest=$digest,m.version=$version,m.nodes=$nodes,m.edges=$edges,m.state='incomplete' RETURN m.state",params).result_set
            if rows != [['incomplete']]:raise ProfileError('FALKOR_EMPTY_REBUILD_REFUSED')
            state=self.status()
        if state['digest'] != params['digest'] or state['version'] != VERSION:
            raise ProfileError('FALKOR_DIFFERENT_ARTIFACT_REQUIRES_RESET')
        if state['state'] == 'complete':
            if self.read_projection() != projection: raise ProfileError('FALKOR_READBACK_MISMATCH')
            return self._receipt(projection)
        if state['state'] != 'incomplete': raise ProfileError('FALKOR_PROJECTION_STATE_INVALID')
        indexes=self._read('CALL db.indexes() YIELD label, properties RETURN label,properties')
        if not any(label=='RdfTerm' and 'key' in fields for label,fields in indexes):
            self.graph.query('CREATE INDEX FOR (n:RdfTerm) ON (n.key)')
        batches=0
        try:
            groups={}
            for node in projection['nodes']:
                labels=tuple(sorted(node['labels']))
                if not set(labels) <= LABELS: raise ProfileError('FALKOR_LABEL_NOT_ADMITTED')
                groups.setdefault(labels,[]).append({'key':node['key'],'properties':{k:v for k,v in node.items() if k!='labels'}})
            for labels,items in sorted(groups.items()):
                for start in range(0,len(items),self.batch_size):
                    rows=items[start:start+self.batch_size]
                    query='UNWIND $rows AS row MERGE (n:RdfTerm {key:row.key}) ON CREATE SET n.owner=$owner WITH n,row WHERE n.owner=$owner SET n += row.properties SET n:'+':'.join(labels)+' RETURN count(n)'
                    count=self.graph.query(query,{'rows':rows,'owner':self.owner}).result_set[0][0]
                    if count != len(rows): raise ProfileError('FALKOR_FOREIGN_KEY_COLLISION')
                    batches+=1
                    if fail_after_batches == batches: raise ProfileError('FALKOR_INJECTED_PARTIAL_FAILURE')
            for start in range(0,len(projection['edges']),self.batch_size):
                rows=projection['edges'][start:start+self.batch_size]
                count=self.graph.query('UNWIND $rows AS row MATCH (s:RdfTerm {key:row.source}),(t:RdfTerm {key:row.target}) WHERE s.owner=$owner AND t.owner=$owner MERGE (s)-[e:RDF {key:row.key}]->(t) ON CREATE SET e.owner=$owner WITH e,row WHERE e.owner=$owner SET e.predicate_iri=row.predicate_iri RETURN count(e)',{'rows':rows,'owner':self.owner}).result_set[0][0]
                if count != len(rows): raise ProfileError('FALKOR_EDGE_WRITE_REFUSED')
                batches+=1
                if fail_after_batches == batches: raise ProfileError('FALKOR_INJECTED_PARTIAL_FAILURE')
            if self.read_projection() != projection: raise ProfileError('FALKOR_READBACK_MISMATCH')
            rows=self.graph.query("MATCH (m:BilqisProjection {owner:$owner,digest:$digest,state:'incomplete'}) SET m.state='complete' RETURN m.state",params).result_set
            if rows != [['complete']] or self.status()['state'] != 'complete':
                raise ProfileError('FALKOR_COMPLETION_READBACK_REQUIRED')
        except ProfileError:
            raise
        except Exception as error:
            raise ProfileError('FALKOR_IMPORT_RECONCILE_REQUIRED',type(error).__name__) from error
        return self._receipt(projection)

    def _receipt(self, projection):
        return {'status':'complete','graph':self.name,'owner':self.owner,'projection_version':VERSION,
                'canonical_sha256':projection['canonical_sha256'],'nodes':len(projection['nodes']),
                'edges':len(projection['edges'])}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--graph',required=True)
    parser.add_argument('--owner',required=True)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=16379)
    args=parser.parse_args(argv)
    try:
        result=Importer(connect(args.host,args.port),args.graph,args.owner).materialize(args.bundle)
    except (ProfileError,OSError,ValueError,RedisError) as error:
        print(json.dumps({'status':'incomplete','code':getattr(error,'code',type(error).__name__)}))
        return 2
    print(json.dumps(result,sort_keys=True)); return 0


if __name__=='__main__': raise SystemExit(main())
