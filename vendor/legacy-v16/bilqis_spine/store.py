"""Materialized, queryable SQLite index of the immutable semantic graph.

The source manifest is authoritative. SQLite is an indexed derivative, not a
second editable ontology, avoiding the spreadsheet-as-source-of-truth trap.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import uuid

from .model import SemanticGraph

DDL = '''
PRAGMA foreign_keys = ON;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sources (
    id TEXT PRIMARY KEY, edition TEXT NOT NULL, url TEXT NOT NULL,
    section TEXT NOT NULL, basis TEXT NOT NULL);
CREATE TABLE concepts (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(id),
    admission TEXT NOT NULL, ordinal INTEGER, tier INTEGER NOT NULL,
    note TEXT NOT NULL);
CREATE INDEX ix_concept_kind ON concepts(kind);
CREATE TABLE edges (
    source_id TEXT NOT NULL REFERENCES concepts(id),
    relation TEXT NOT NULL, target_id TEXT NOT NULL REFERENCES concepts(id),
    authority TEXT NOT NULL REFERENCES sources(id),
    PRIMARY KEY(source_id,relation,target_id));
CREATE INDEX ix_edge_reverse ON edges(target_id,relation);
CREATE TABLE signatures (
    id TEXT PRIMARY KEY, inputs_json TEXT NOT NULL, output_kind TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(id));
'''


def materialize(graph:SemanticGraph,destination:Path):
    """Create a new index atomically; refuse overwrite or symlink targets."""
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('SPINE_INDEX_TARGET_EXISTS')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        connection=sqlite3.connect(temp)
        try:
            connection.executescript(DDL)
            with connection:
                connection.execute('INSERT INTO meta VALUES (?,?)',
                                   ('spine_sha256',graph.sha256))
                connection.executemany('INSERT INTO sources VALUES (?,?,?,?,?)',
                    [(s.id,s.edition,s.url,s.section,s.basis) for s in graph.sources.values()])
                connection.executemany('INSERT INTO concepts VALUES (?,?,?,?,?,?,?,?)',
                    [(c.id,c.kind,c.name,c.source,c.admission,c.ordinal,c.tier,c.note)
                     for c in graph.concepts.values()])
                connection.executemany('INSERT INTO edges VALUES (?,?,?,?)',
                    [(e.source,e.relation,e.target,e.authority) for e in graph.edges])
                import json
                connection.executemany('INSERT INTO signatures VALUES (?,?,?,?)',
                    [(s.id,json.dumps(s.inputs),s.output,s.source)
                     for s in graph.signatures.values()])
            result=connection.execute('PRAGMA foreign_key_check').fetchall()
            if result:
                raise ValueError('SPINE_INDEX_FOREIGN_KEYS')
        finally:
            connection.close()
        os.link(temp,destination)
    finally:
        temp.unlink(missing_ok=True)
    return destination


def query_neighbors(index:Path,concept_id:str,relation:str):
    uri='file:'+str(Path(index).resolve())+'?mode=ro'
    with sqlite3.connect(uri,uri=True) as db:
        return tuple(row[0] for row in db.execute(
            'SELECT target_id FROM edges WHERE source_id=? AND relation=? ORDER BY target_id',
            (concept_id,relation)))
