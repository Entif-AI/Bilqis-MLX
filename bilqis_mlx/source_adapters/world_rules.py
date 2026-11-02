"""Source-qualified actor, time, state and direct-causation world rules."""
from __future__ import annotations

import copy
import csv
import hashlib
from pathlib import Path
import random

from ..factory.adapters import RegisteredSourceAdapter
from ..factory.model import SourceAdapter
from ._world.oracle import answer
from ..vocabulary_growth import digest
CAPABILITIES = (
    "WORLD.ACTOR_OF", "WORLD.BEFORE", "WORLD.IS_OCCURRED",
    "WORLD.DIRECT_CAUSE",
)
GENERATOR = "bilqis.bamf.a08.qualified-world/v1"
ORACLE = "bilqis.bamf.a08.qualified-world-oracle/v1"
DIALECT = "bilqis.bamf.qualified-world/v1"
ROOT = Path(__file__).resolve().parents[2]

_CAUSE = "LEXSENSE-59819df75e3137"
_OCCURRENCE = "LEXSENSE-294d00be074a56"
_ACTOR = "ATOM-5d7116db8e1508"
_TIME = "ATOM-ef7cf17b427af9"
_TOKENS = (
    "bamf.world.syntax.actors", "bamf.world.syntax.causes",
    "bamf.world.actor.A0", "bamf.world.actor.A1", "bamf.world.actor.A2",
    "bamf.world.query.ACTOR_OF", "bamf.world.query.BEFORE",
    "bamf.world.query.IS_OCCURRED", "bamf.world.query.DIRECT_CAUSE",
)
def _row(path: Path, key: str, value: str) -> dict:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row.get(key) == value]
    if len(rows) != 1:
        raise ValueError("WORLD_RULE_SOURCE_ROW_MISSING_OR_AMBIGUOUS")
    return rows[0]
def verify_source() -> dict:
    """Replay exact pinned source anchors; do not infer laws from gloss text."""
    data = ROOT / "lib/ithkuil/_data"
    senses = data / "csv/lexicon_root_senses.csv"
    atoms = data / "csv/morphemes_atomic.csv"
    cause = _row(senses, "lexicon_sense_id", _CAUSE)
    occurrence = _row(senses, "lexicon_sense_id", _OCCURRENCE)
    actor = _row(atoms, "atomic_id", _ACTOR)
    time = _row(atoms, "atomic_id", _TIME)
    expected = (
        (cause, "source_text_sha256",
         "ea8605d91af2676e7695a73ffefd0617484aa6b01bd290cac36785993d11409a"),
        (occurrence, "source_text_sha256",
         "4ad21b82d3b0ff9f8bedbfb12efb7184cead6cb5ad549cc88c6626e0ec1b0dd7"),
        (actor, "semantic_summary", "ergative case; semantic role AGENT"),
        (actor, "primary_section_id", "NI-WEB-CH04:4.2.7"),
        (time, "value_code", "TPP"),
        (time, "semantic_summary", "Temporal Position Relative to Present"),
    )
    if any(row.get(key) != value for row, key, value in expected):
        raise ValueError("WORLD_RULE_SOURCE_DRIFT")
    for row in (cause, occurrence):
        pdf = data / "pdf" / row["tracked_pdf_name"]
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != row["tracked_pdf_sha256"]:
            raise ValueError("WORLD_RULE_SOURCE_PDF_DRIFT")
    return {
        "sense_id": _CAUSE,
        "occurrence_sense_id": _OCCURRENCE,
        "actor_atom_id": _ACTOR,
        "time_atom_id": _TIME,
        "grammar_section": actor["primary_section_id"],
        "time_section": time["primary_section_id"],
        "morphology": "NOT_REALIZED",
        "source_digests": (
            cause["source_text_sha256"], occurrence["source_text_sha256"],
        ),
        "source_rows_sha256": digest({
            "cause": cause, "occurrence": occurrence,
            "actor": actor, "time": time,
        }),
    }
_VERIFY_SOURCE = verify_source
def projected_graph(parent: dict) -> dict:
    """Append fixture-only symbols without changing any inherited row."""
    if (not isinstance(parent, dict)
            or not isinstance(parent.get("tokens"), list)
            or not isinstance(parent.get("nodes"), list)
            or len(parent["tokens"]) != len(parent["nodes"])):
        raise ValueError("WORLD_RULE_GRAPH_INVALID")
    graph = copy.deepcopy(parent)
    contracts = graph.setdefault("row_contract_sha256", {})
    for token in _TOKENS:
        if token in graph["tokens"]:
            continue
        node = {
            "id": token, "family": "qualified_world", "subtype": "source_fixture",
            "signature": "WorldFact", "arity": 0, "stage": 0, "edges": [],
        }
        graph["tokens"].append(token)
        graph["nodes"].append(node)
        contracts[token] = digest(node)
    return graph
def _record(rng: random.Random) -> dict:
    actors = ["A0", "A1", "A2"]
    event_ids = ["E0", "E1", "E2", "E3"]
    rng.shuffle(event_ids)
    events = [
        {"id": event_id, "actor": rng.choice(actors), "time": index,
         "state": "OCCURRED" if rng.getrandbits(1) else "PENDING"}
        for index, event_id in enumerate(event_ids)
    ]
    causes = [[event_ids[0], event_ids[1]], [event_ids[1], event_ids[2]]]
    if rng.getrandbits(1):
        causes.append([event_ids[0], event_ids[3]])
    return {"task": DIALECT, "actors": actors, "events": events,
            "direct_causes": causes}
def _query(record: dict, capability: str, truth: bool, rng: random.Random) -> dict:
    events = record["events"]
    if capability == "WORLD.ACTOR_OF":
        event = rng.choice(events)
        actor = event["actor"] if truth else next(
            value for value in record["actors"] if value != event["actor"])
        return {"kind": "ACTOR_OF", "left": event["id"], "right": actor}
    if capability == "WORLD.BEFORE":
        a, b = sorted(rng.sample(events, 2), key=lambda item: item["time"])
        return {"kind": "BEFORE", "left": a["id"] if truth else b["id"],
                "right": b["id"] if truth else a["id"]}
    if capability == "WORLD.IS_OCCURRED":
        matching = [event for event in events
                    if (event["state"] == "OCCURRED") is truth]
        if not matching:
            event = rng.choice(events)
            event["state"] = "OCCURRED" if truth else "PENDING"
            matching = [event]
        return {"kind": "IS_OCCURRED", "left": rng.choice(matching)["id"]}
    if capability == "WORLD.DIRECT_CAUSE":
        if truth:
            left, right = rng.choice(record["direct_causes"])
        else:
            pairs = {(a, b) for a, b in record["direct_causes"]}
            left, right = next(
                (a["id"], b["id"]) for a in events for b in events
                if a != b and (a["id"], b["id"]) not in pairs)
        return {"kind": "DIRECT_CAUSE", "left": left, "right": right}
    raise ValueError("WORLD_RULE_CAPABILITY_INVALID")
def _encode(record: dict, graph: dict) -> list[int]:
    symbols = ["micro.syntax.world", "bamf.world.syntax.actors"]
    symbols.extend("bamf.world.actor." + actor for actor in record["actors"])
    symbols.append("development.syntax.events")
    for event in record["events"]:
        symbols.extend(("development.Event." + event["id"],
                        "bamf.world.actor." + event["actor"],
                        "school.number." + str(event["time"]),
                        "cogal.value.true" if event["state"] == "OCCURRED"
                        else "cogal.value.false"))
    symbols.append("bamf.world.syntax.causes")
    for left, right in record["direct_causes"]:
        symbols.extend(("development.Event." + left, "development.Event." + right))
    query = record["query"]
    symbols.extend(("micro.syntax.query", "bamf.world.query." + query["kind"]))
    for side in ("left", "right"):
        value = query.get(side)
        if value is None:
            continue
        if value.startswith("E"):
            symbols.append("development.Event." + value)
        else:
            symbols.append("bamf.world.actor." + value)
    symbols.append("syntax.end")
    ids = {token: index for index, token in enumerate(graph["tokens"])}
    try:
        return [ids[symbol] for symbol in symbols]
    except KeyError as exc:
        raise ValueError("WORLD_RULE_GRAPH_SYMBOL_MISSING") from exc
def draw(source_root=None, graph=None, *, capability: str, seed: int,
         each: int = 12, **_) -> tuple[dict, ...]:
    del source_root
    _VERIFY_SOURCE()
    if (capability not in CAPABILITIES or type(seed) is not int
            or type(each) is not int or not 1 <= each <= 10000
            or not isinstance(graph, dict)):
        raise ValueError("WORLD_RULE_DRAW_INVALID")
    rng = random.Random(digest((GENERATOR, capability, seed)))
    contract = registered_adapter().descriptor.implementation_sha256
    rows = []
    for index in range(each):
        record = _record(rng)
        record["query"] = _query(record, capability, index % 2 == 0, rng)
        gold = answer(record)
        identity = digest(record)
        rows.append({
            "id": identity, "source_id": identity, "capability": capability,
            "answer_kind": "binary", "gold": gold, "record": record,
            "tokens": _encode(record, graph), "generator": GENERATOR,
            "oracle": ORACLE, "source_contract_sha256": contract,
        })
    return tuple(rows)
def check(row: dict, *, graph: dict, **_) -> bool:
    try:
        record = row["record"]
        return (
            row["capability"] in CAPABILITIES
            and row["capability"] == "WORLD." + record["query"]["kind"]
            and row["gold"] == answer(record)
            and row["id"] == row["source_id"] == digest(record)
            and row["tokens"] == _encode(record, graph)
            and row["generator"] == GENERATOR and row["oracle"] == ORACLE
            and row["answer_kind"] == "binary"
            and row["source_contract_sha256"]
            == registered_adapter().descriptor.implementation_sha256
        )
    except (KeyError, TypeError, ValueError, IndexError):
        return False
_CANONICAL_DRAW = draw
_CANONICAL_CHECK = check
def _implementation_sha256() -> str:
    witness = _VERIFY_SOURCE()
    files = (
        ("bilqis_mlx/source_adapters/world_rules.py", Path(__file__)),
        ("bilqis_mlx/source_adapters/_world/oracle.py",
         ROOT / "bilqis_mlx/source_adapters/_world/oracle.py"),
    )
    return digest({"source": witness, "files": tuple(
        (relative, hashlib.sha256(path.read_bytes()).hexdigest())
        for relative, path in files)})
def registered_adapter() -> RegisteredSourceAdapter:
    return RegisteredSourceAdapter(
        SourceAdapter(
            "source.bamf.qualified-world/v1", GENERATOR, (ORACLE,),
            _implementation_sha256(),
            variation_axes=("actor", "time", "state", "direct-cause", "fresh-seed")),
        _CANONICAL_DRAW, _CANONICAL_CHECK,
    )
def require_registered_source(source: RegisteredSourceAdapter) -> None:
    """Reject descriptor cloning with substituted executable behavior."""
    expected = registered_adapter()
    if (type(source) is not RegisteredSourceAdapter
            or source.descriptor != expected.descriptor
            or source.draw is not _CANONICAL_DRAW
            or source.check is not _CANONICAL_CHECK):
        raise ValueError("WORLD_RULE_SOURCE_IMPLEMENTATION_SUBSTITUTED")
