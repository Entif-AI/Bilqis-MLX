"""Source-grounded finite reference identity, registered through the factory.

The codec preserves existing entity/function syntax and uses one distinct query
operator. This is a formal semantic adapter, not natural Ithkuil surface text.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import random

from ..factory.adapters import RegisteredSourceAdapter
from ..factory.model import SourceAdapter
from ..semantics.foundation.copular import (
    SYMBOL, ENTITIES, ReferentWorld, bind_operation, identify, evaluate, references,
)
ORACLE = "bilqis.ithkuil-reference-identity-oracle/v1"
from ..vocabulary_growth import digest


CAPABILITY = "D.COPULAR_IDENTITY"
GENERATOR = "bilqis.ithkuil-reference-identity-constructor/v1"
DIALECT = "bilqis.ithkuil-reference-identity/v1"
SENSE_ID = "LEXSENSE-5286ade9db42c7"
TEXT_SHA256 = "e3fa6604b5892a9095955e152cca40a441a56ccbff394a4bd411bf41e318da9e"
PDF_SHA256 = "1c60e40374cf6ffd16791b89983db8f6584c2e1feac7a9c965fc8255b2f95609"
MEANING = "(to be ontologically the) self-same entity (as) (i.e., [to be] simply another name for the self-same entity)"


def _expected_witness():
    return dict(sense_id=SENSE_ID, scope="finite-reference-identity",
                meaning=MEANING, source_text_sha256=TEXT_SHA256,
                source_url="https://ithkuil.net/New_Ithkuil_Lexicon.pdf",
                tracked_pdf_sha256=PDF_SHA256,
                section="1.3", printed_page=5, pdf_page=2,
                morphology="NOT_REALIZED")


def verify_source(repo_root: Path) -> dict:
    root = Path(repo_root) / "lib/ithkuil/_data"
    with (root / "csv/lexicon_root_senses.csv").open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row["lexicon_sense_id"] == SENSE_ID]
    if len(rows) != 1:
        raise ValueError("COPULAR_SOURCE_SENSE_MISSING_OR_AMBIGUOUS")
    row = rows[0]
    expected = dict(root_form_raw="-Č-", stem="STEM 1", specification="BSC",
                    lexicon_section="1.3", source_pdf_page="2", source_printed_page="5",
                    sense_summary=MEANING, source_text_sha256=TEXT_SHA256,
                    tracked_pdf_sha256=PDF_SHA256,
                    source_url="https://ithkuil.net/New_Ithkuil_Lexicon.pdf")
    if (any(row.get(key) != value for key, value in expected.items()) or
            hashlib.sha256(MEANING.encode()).hexdigest() != TEXT_SHA256):
        raise ValueError("COPULAR_SOURCE_SENSE_DRIFT")
    pdf = root / "pdf" / row["tracked_pdf_name"]
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != PDF_SHA256:
        raise ValueError("COPULAR_SOURCE_PDF_DRIFT")
    return _expected_witness()


def _record(world, expression):
    return dict(task=DIALECT, entities=list(world.entities),
                denotations=[list(pair) for pair in world.denotations],
                query=dict(operator=SYMBOL, arguments=list(references(expression))))


def encode(world, expression) -> list[str]:
    evaluate(world, expression)
    entity = lambda value: "micro.entity." + value
    return ["micro.syntax.world", "micro.syntax.entities",
            *(entity(value) for value in world.entities), "micro.syntax.section_end",
            "development.syntax.functions", "development.Function.F0",
            *(entity(value) for pair in world.denotations for value in pair),
            "micro.syntax.query", SYMBOL,
            *(entity(value) for value in references(expression)), "syntax.end"]


def decode(symbols: list[str], graph: dict):
    if (not isinstance(symbols, list) or not 16 <= len(symbols) <= 96 or
            any(not isinstance(s, str) for s in symbols) or
            symbols[:2] != ["micro.syntax.world", "micro.syntax.entities"]):
        raise ValueError("COPULAR_CODEC_INVALID_INPUT")
    operation = bind_operation(graph)
    def entity(symbol):
        if not symbol.startswith("micro.entity.") or symbol.removeprefix("micro.entity.") not in ENTITIES:
            raise ValueError("COPULAR_CODEC_UNKNOWN_ENTITY")
        return symbol.removeprefix("micro.entity.")
    try:
        end = symbols.index("micro.syntax.section_end", 2)
        entities = tuple(entity(s) for s in symbols[2:end])
        if symbols[end+1:end+3] != ["development.syntax.functions", "development.Function.F0"]:
            raise ValueError("COPULAR_CODEC_INVALID_FUNCTION")
        query = end + 3 + 2 * len(entities)
        pairs = tuple((entity(symbols[i]), entity(symbols[i+1]))
                      for i in range(end+3, query, 2))
        if (len(symbols) != query + 5 or symbols[query:query+2] != ["micro.syntax.query", SYMBOL] or
                symbols[-1] != "syntax.end"):
            raise ValueError("COPULAR_CODEC_INVALID_QUERY")
        world = ReferentWorld(entities, pairs)
        expression = identify(operation, entity(symbols[query+2]), entity(symbols[query+3]))
        evaluate(world, expression)
        return world, expression
    except (IndexError, TypeError) as exc:
        raise ValueError("COPULAR_CODEC_INCOMPLETE") from exc


def _pattern(world, expression):
    left, right = references(expression)
    if left == right:
        return "same-reference"
    return "distinct-coreferent" if evaluate(world, expression) else "distinct-referent"


def _row(graph, world, expression):
    record = _record(world, expression)
    ids = {token: i for i, token in enumerate(graph["tokens"])}
    identity = digest(record)
    return dict(id=identity, source_id=identity, capability=CAPABILITY,
                answer_kind="binary", gold="TRUE" if evaluate(world, expression) else "FALSE",
                record=record, tokens=[ids[s] for s in encode(world, expression)],
                root=SYMBOL, generator=GENERATOR, oracle=ORACLE, source_sense_id=SENSE_ID,
                reference_pattern=_pattern(world, expression), universe_size=len(world.entities))


def draw(source_root, graph, *, seed: int, each: int = 12,
         capability: str = CAPABILITY, **_) -> tuple[dict, ...]:
    if (type(seed) is not int or type(each) is not int or not 1 <= each <= 10000 or
            capability != CAPABILITY):
        raise ValueError("COPULAR_INVALID_DRAW")
    verify_source(Path(__file__).resolve().parents[2])
    operation = bind_operation(graph)
    rng = random.Random(digest((GENERATOR, seed)))
    rows, seen = [], set()
    attempts = 0
    while len(rows) < each:
        attempts += 1
        if attempts > 2 * each + 32:
            raise ValueError("COPULAR_VARIATION_EXHAUSTED")
        cycle = []
        for slot in range(8):
            n = 3 + slot % 3
            entities = list(rng.sample(ENTITIES, n))
            left, right = rng.sample(entities, 2)
            targets = {entity: rng.choice(entities) for entity in entities}
            targets[right] = targets[left]
            rng.shuffle(entities)
            order = rng.sample(entities, n)
            expression = identify(operation, left, right)
            true_world = ReferentWorld(tuple(entities), tuple((e, targets[e]) for e in order))
            if slot < 4:
                # Matched queries differ by one denotation fact. Query-only
                # classification cannot get both members of a pair correct.
                cycle.append(_row(graph, true_world, expression))
                targets[right] = rng.choice([e for e in entities if e != targets[left]])
                false_world = ReferentWorld(tuple(entities), tuple((e, targets[e]) for e in order))
                cycle.append(_row(graph, false_world, expression))
            elif slot < 6:
                cycle.append(_row(graph, true_world, identify(operation, left, left)))
            else:
                targets[right] = rng.choice([e for e in entities if e != targets[left]])
                cycle.append(_row(graph, ReferentWorld(tuple(entities),
                    tuple((e, targets[e]) for e in order)), expression))
        if len({row["id"] for row in cycle}) != len(cycle) or any(r["id"] in seen for r in cycle):
            continue
        rows.extend(cycle)
        seen.update(r["id"] for r in cycle)
    return tuple(rows[:each])


def check_copular(row, *, graph, **_):
    from ..vocabulary_growth import digest
    try:
        record = row["record"]
        tokens = row["tokens"]
        if (not isinstance(tokens, list) or
                any(type(index) is not int or not 0 <= index < len(graph["tokens"]) for index in tokens)):
            return False
        world, expression = decode([graph["tokens"][index] for index in tokens], graph)
        gold = "TRUE" if evaluate(world, expression) else "FALSE"
        return (record == _record(world, expression) and
                row["gold"] == gold and row["id"] == row["source_id"] == digest(record) and
                row["capability"] == CAPABILITY and row["root"] == SYMBOL and
                row["generator"] == GENERATOR and row["oracle"] == ORACLE and
                row["answer_kind"] == "binary" and row["source_sense_id"] == SENSE_ID and
                row["universe_size"] == len(world.entities) and
                row["reference_pattern"] == _pattern(world, expression))
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


check = check_copular


def registered_adapter() -> RegisteredSourceAdapter:
    home = Path(__file__).resolve().parents[1]
    files = (
        ("source_adapters/copular.py", "source_adapters/copular.py"),
        ("semantics/copular.py", "semantics/foundation/copular.py"),
        ("verification/copular.py", "verification/copular.py"),
        ("factory/verification.py", "factory/verification.py"),
    )
    implementation = digest(dict(
        source=_expected_witness(),
        files={logical: hashlib.sha256((home / physical).read_bytes()).hexdigest()
               for logical, physical in files}))
    return RegisteredSourceAdapter(SourceAdapter(
        adapter_id="source.ithkuil-reference-identity/v1", generator_id=GENERATOR,
        accepted_oracle_ids=(ORACLE,), implementation_sha256=implementation,
        variation_axes=("reference-identity", "denotation", "universe-size", "fact-order", "fresh-seed")),
        draw, check, witness=witness)


def witness(row, obligation, *, graph, **_) -> bool:
    """Denotation lookup followed by identity witnesses both declared edges."""
    if not check(row, graph=graph) or obligation.capability_id != CAPABILITY:
        return False
    kind = getattr(obligation.kind, "value", None)
    if kind not in ("PREREQUISITE", "COMPOSITION"):
        raise ValueError("COPULAR_EVIDENCE_KIND_UNSUPPORTED")
    if obligation.key not in ("A.IDENTITY", "A.MAPS"):
        return False
    return row["reference_pattern"] != "same-reference"
