"""Live Falkor qualification phases shared by the CT-056 runner."""
from __future__ import annotations

import hashlib
import json
import time


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def elapsed(call):
    started = time.perf_counter()
    result = call()
    return result, max(time.perf_counter() - started, 1e-9)


def restore_snapshot(db, name, owner, snapshot):
    from lib.ithkuil.src.skos.falkor_import import Importer, LABELS
    from lib.ithkuil.src.skos.falkor_projection import VERSION, reconstruct_graph
    reconstruct_graph(snapshot)
    importer = Importer(db, name, owner)
    if name in db.list_graphs():
        raise AssertionError("QUALIFICATION_RESTORE_REQUIRES_ABSENT_GRAPH")
    params = {"owner": owner, "digest": snapshot["canonical_sha256"],
              "version": VERSION, "nodes": len(snapshot["nodes"]),
              "edges": len(snapshot["edges"])}
    rows = importer.graph.query(
        "MATCH(n) WITH count(n) AS count WHERE count=0 "
        "CREATE(m:BilqisProjection {owner:$owner,digest:$digest,version:$version,"
        "nodes:$nodes,edges:$edges,state:'incomplete'}) RETURN m.owner", params).result_set
    if rows != [[owner]]:
        raise AssertionError("QUALIFICATION_RESTORE_CLAIM_REFUSED")
    importer.graph.query("CREATE INDEX FOR (n:RdfTerm) ON (n.key)")
    groups = {}
    for node in snapshot["nodes"]:
        labels = tuple(sorted(node["labels"]))
        if not set(labels) <= LABELS:
            raise AssertionError("QUALIFICATION_RESTORE_LABEL_INVALID")
        groups.setdefault(labels, []).append(
            {"key": node["key"], "properties": {k: v for k, v in node.items() if k != "labels"}})
    for labels, items in sorted(groups.items()):
        for start in range(0, len(items), importer.batch_size):
            rows = items[start:start + importer.batch_size]
            query = ("UNWIND $rows AS row MERGE(n:RdfTerm {key:row.key}) "
                     "ON CREATE SET n.owner=$owner WITH n,row WHERE n.owner=$owner "
                     "SET n += row.properties SET n:" + ":".join(labels) + " RETURN count(n)")
            if importer.graph.query(query, {"rows": rows, "owner": owner}).result_set != [[len(rows)]]:
                raise AssertionError("QUALIFICATION_RESTORE_NODE_REFUSED")
    for start in range(0, len(snapshot["edges"]), importer.batch_size):
        rows = snapshot["edges"][start:start + importer.batch_size]
        query = ("UNWIND $rows AS row MATCH(s:RdfTerm {key:row.source}),(t:RdfTerm {key:row.target}) "
                 "WHERE s.owner=$owner AND t.owner=$owner MERGE(s)-[e:RDF {key:row.key}]->(t) "
                 "ON CREATE SET e.owner=$owner WITH e,row WHERE e.owner=$owner "
                 "SET e.predicate_iri=row.predicate_iri RETURN count(e)")
        if importer.graph.query(query, {"rows": rows, "owner": owner}).result_set != [[len(rows)]]:
            raise AssertionError("QUALIFICATION_RESTORE_EDGE_REFUSED")
    if importer.read_projection() != snapshot:
        raise AssertionError("QUALIFICATION_RESTORE_READBACK_MISMATCH")
    if importer.graph.query(
            "MATCH(m:BilqisProjection {owner:$owner,digest:$digest,state:'incomplete'}) "
            "SET m.state='complete' RETURN m.state", params).result_set != [["complete"]]:
        raise AssertionError("QUALIFICATION_RESTORE_COMPLETION_REFUSED")
    return importer


def latencies(importer, suite, count=7):
    from lib.ithkuil.src.skos.falkor_lookup import Reader
    case = next(item for item in suite["queries"] if item.get("expected"))
    reader, samples = Reader(importer), []
    for _ in range(count):
        started = time.perf_counter()
        actual = reader.query(case["cypher"], case["params"])
        samples.append(max((time.perf_counter() - started) * 1000, 1e-9))
        if actual != case["expected"]:
            raise AssertionError("QUALIFICATION_QUERY_MISMATCH")
    return tuple(samples), case


def materialization_phase(db, bundle, suite_path, suite, names, owner, host, port, output):
    from lib.ithkuil.src.skos.falkor_import import Importer
    from lib.ithkuil.src.skos.falkor_lookup import ensure_indexes
    from lib.ithkuil.src.skos.falkor_receipt import build_receipt
    from lib.ithkuil.tests.release_graph_proof import journey
    first = Importer(db, names["source"], owner)
    first_import, rebuild_seconds = elapsed(lambda: first.materialize(bundle))
    ensure_indexes(first); first_receipt = build_receipt(first, bundle, suite_path)
    snapshot = first.read_projection(); backup = canonical_bytes(snapshot)
    (output / "projection-backup.json").write_bytes(backup)
    second_import, idempotent_seconds = elapsed(lambda: first.materialize(bundle))
    latency_ms, query_case = latencies(first, suite)
    access = journey(first, first_receipt, bundle, suite_path, {"host": host, "port": port})
    restored, restore_seconds = elapsed(
        lambda: restore_snapshot(db, names["restore"], owner + "r", snapshot))
    ensure_indexes(restored); restored_receipt = build_receipt(restored, bundle, suite_path)
    restored_query, _ = latencies(restored, suite, 5)
    restored_matches = restored.read_projection() == snapshot
    rebuilt = Importer(db, names["rebuild"], owner + "b")
    rebuilt_import, _ = elapsed(lambda: rebuilt.materialize(bundle))
    ensure_indexes(rebuilt); rebuilt_receipt = build_receipt(rebuilt, bundle, suite_path)
    return {"first": first, "first_import": first_import, "first_receipt": first_receipt,
            "snapshot": snapshot, "backup": backup, "second_import": second_import,
            "rebuild_seconds": rebuild_seconds, "idempotent_seconds": idempotent_seconds,
            "latency_ms": latency_ms, "query_case": query_case, "access": access,
            "restored": restored, "restored_receipt": restored_receipt,
            "restored_query": restored_query, "restored_matches": restored_matches,
            "restore_seconds": restore_seconds, "rebuilt_import": rebuilt_import,
            "rebuilt_receipt": rebuilt_receipt}


def fault_phase(db, bundle, suite_path, names, owner, host, port, material):
    from lib.ithkuil.src.skos.errors import ProfileError
    from lib.ithkuil.src.skos.falkor_import import Importer, connect
    from lib.ithkuil.src.skos.falkor_lookup import ensure_indexes
    from lib.ithkuil.src.skos.falkor_receipt import build_receipt, verify_receipt
    from lib.ithkuil.src.skos.falkor_reset import plan_reset, reset_owned
    stale = dict(material["first_receipt"]); stale["canonical_rdf_sha256"] = "0" * 64
    try: verify_receipt(stale, material["first"], bundle, suite_path)
    except ProfileError: stale_detected = True
    else: stale_detected = False
    restored = material["restored"]
    restored.graph.query(
        "MATCH(n:RdfTerm) WHERE n.owner=$owner AND n.lexical IS NOT NULL "
        "WITH n LIMIT 1 SET n.lexical=n.lexical+'__qualification_corrupt__'", {"owner": restored.owner})
    try: verify_receipt(material["restored_receipt"], restored, bundle, suite_path)
    except ProfileError: corruption_detected = True
    else: corruption_detected = False
    partial = Importer(db, names["partial"], owner + "p")
    try: partial.materialize(bundle, fail_after_batches=1)
    except ProfileError as error: partial_failed = error.code == "FALKOR_INJECTED_PARTIAL_FAILURE"
    else: partial_failed = False
    resumed = Importer(connect(host, port), names["partial"], owner + "p")
    resumed_import = resumed.materialize(bundle); ensure_indexes(resumed)
    resumed_receipt = build_receipt(resumed, bundle, suite_path)
    first = material["first"]
    first.graph.query("CREATE(a:QualificationForeign {key:'a'}),(b:QualificationForeign {key:'b'}),"
                      "(a)-[:QualificationForeign {key:'edge'}]->(b)")
    foreign_before = first._read("MATCH(n:QualificationForeign) RETURN n.key ORDER BY n.key")
    plan = plan_reset(first); reset_owned(first, plan)
    foreign_after = first._read("MATCH(n:QualificationForeign) RETURN n.key ORDER BY n.key")
    return {"stale_detected": stale_detected, "corruption_detected": corruption_detected,
            "partial_recovery": partial_failed and resumed_import == material["first_import"]
                and resumed_receipt["status"] == "complete",
            "restart_reconnect": resumed.status()["state"] == "complete",
            "foreign_isolation": foreign_before == foreign_after == [["a"], ["b"]],
            "resumed_receipt": resumed_receipt, "reset_plan": plan}
