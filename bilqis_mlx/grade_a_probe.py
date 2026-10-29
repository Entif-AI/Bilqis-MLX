"""Source-attested draft of six flat Grade A predicates, no neural training.

This *draft* uses the unchanged legacy code and both of its independently
written reference oracles, never imported from an unpinned downloaded copy.
It is not an admitted/approved complete school curriculum: the original token
namespace, deeper source prerequisites and operator training adapter require
additional review. The CLI emits a report, no models or lessons are written.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import types

from .curriculum import AnswerFamily, BINARY, Capability, Course, Grade, ExamItem, validate_exam_item
from .grade_a_oracle import VERSION as INDEPENDENT_ORACLE, evaluate as third_oracle
from .source import AUDITED_PARENT
from .semantics.foundation.abi import HISTORICAL_ABI
from .backup import digest_file

SCHEMA = "bilqis.mlx.direct-grade-a-source-probe/v2"
PINNED_SOURCES = {
    "bilqis_development/kernel.py": "1c73e1987a38e9612ffa84b12895c8a5a9841a8b595fe200ce933831c37d8ba4",
    "bilqis_development/registry.py": "5f0c80d797a98868bfe2c585160ad5d95c9ef3a529e55d8bcba54d4bd0c8de9a",
    "bilqis_logic/kernel.py": "9b73993d042cebb9d46656884966ca92b024fccdd0d32e89b0071b0718fb2c6c",
    "bilqis_micro/graph.py": "04898206f76c7a5fae27a03c3a2c01f2c684e076c5771b169397d6bf12afb31b",
    "bilqis_micro/kernel.py": "1355d914cda4200503ac8aa5cac4fd8601ebaca33ae9531d963d8cc47451503d",
}
PINNED_GRAPH_SHA256 = "67a582c803c7365429c1b30e97c33365a5c2e7081808759afa49dc8949923de7"
PINNED_FULL_STUDENT_GRAPH_SHA256 = HISTORICAL_ABI.graph_sha256
FAMILIES = (
    ("A.IDENTITY", "micro.compare.EQ", "bilqis_micro.kernel", "compare"),
    ("A.PARENT", "micro.relation.PARENT", "bilqis_micro.kernel", "relation"),
    ("A.LINK", "micro.relation.LINK", "bilqis_micro.kernel", "relation"),
    ("A.MEMBER", "development.op.MEMBER", "bilqis_development.kernel", "op"),
    ("A.EDGE", "development.op.EDGE", "bilqis_development.kernel", "op"),
    ("A.MAPS", "development.op.MAPS", "bilqis_development.kernel", "op"),
)
SEED = 20261015

# Preserve source-probe error identities while making their contracts explicit.
SOURCE_PROBE_NEURAL_GEOMETRY_ERROR = "GRADE_A_SOURCE_PROBE_NEURAL_GEOMETRY_FORBIDDEN"
HISTORICAL_GRAPH_DRIFT_ERROR = "GRADE_A_HISTORICAL_GRAPH_DRIFT"
HISTORICAL_ABI_BINDING_DRIFT_ERROR = "GRADE_A_HISTORICAL_ABI_BINDING_DRIFT"


def _source_only_tensor_hash(*_args, **_kwargs):
    """Fail closed if a source-only probe reaches legacy neural geometry."""
    raise RuntimeError(SOURCE_PROBE_NEURAL_GEOMETRY_ERROR)


def _import_source_interpreters(root: Path):
    """Import pinned symbolic interpreters without requiring PyTorch.

    `bilqis_micro.graph` imports `tensor_hash` at module import time, although
    the symbolic kernels used by this probe never call it. Portable source
    verification should not need the historical neural stack merely to import
    those constants. When torch is absent, provide only that imported name;
    any accidental embedding/tensor path still fails closed immediately.
    """
    geometry_name = "bilqis_logic.geometry"
    try:
        torch_available = importlib.util.find_spec("torch") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        torch_available = False
    previous_geometry = sys.modules.get(geometry_name)
    inserted = False
    if not torch_available and previous_geometry is None:
        source_only_geometry = types.ModuleType(geometry_name)
        source_only_geometry.tensor_hash = _source_only_tensor_hash
        sys.modules[geometry_name] = source_only_geometry
        inserted = True
    try:
        micro = importlib.import_module("bilqis_micro.kernel")
        development = importlib.import_module("bilqis_development.kernel")
        registry = importlib.import_module("bilqis_development.registry")
    finally:
        if inserted:
            sys.modules.pop(geometry_name, None)
    return micro, development, registry


def read_sources(root: Path):
    root = Path(root).resolve(strict=True)
    for name in PINNED_SOURCES:
        if not (root/name).is_file():
            raise ValueError("GRADE_A_LEGACY_ORACLE_SOURCE_MISSING:"+name)
    sources = {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
               for name in PINNED_SOURCES}
    if sources != PINNED_SOURCES:
        raise ValueError("GRADE_A_HISTORICAL_ORACLE_SOURCE_DRIFT")
    sys.path.insert(0,str(root)) if str(root) not in sys.path else None
    sys.dont_write_bytecode = True
    micro, development, registry = _import_source_interpreters(root)
    if (Path(micro.__file__).resolve() != root/"bilqis_micro/kernel.py" or
            Path(development.__file__).resolve() != root/"bilqis_development/kernel.py"):
        raise ValueError("GRADE_A_LEGACY_IMPORT_ROOT_MISMATCH")
    graph = registry.extended_catalog()
    graph_hash = hashlib.sha256(json.dumps(graph,sort_keys=True,separators=(",", ":"))
                               .encode()).hexdigest()
    if graph_hash != PINNED_GRAPH_SHA256:
        raise ValueError(HISTORICAL_GRAPH_DRIFT_ERROR)
    return micro,development,graph,sources,graph_hash


def candidate_course() -> Course:
    capabilities=[]
    for cap,root,module,symbol in FAMILIES:
        capabilities.append(Capability(id=cap,difficulty="direct-predicate",
          source_anchor=f"repo:{module.replace('.', '/')}.py::{symbol}",
          taught_roots=(root,),examined_roots=(root,),prerequisites=(),
          composed_of=(),answer_families=(AnswerFamily("binary",BINARY),),
          lesson_generator="bilqis_mlx.grade_a_probe.make_record",
          independent_oracle=INDEPENDENT_ORACLE))
    # Deliberately no attestation signatures. A successful structural/source
    # report is not yet authorization to teach or claim mastered grade A.
    return Course(grades=(Grade("A",tuple(capabilities),
                                exam_item_counts=tuple((name, 12) for name,_,_,_
                                                       in FAMILIES)),),
                  version="bilqis.mlx.grade-a-direct-proposal/v2")


def make_record(identifier: str, rng: random.Random, positive: bool,
                *, split: str, micro, development, universe_size: int | None = None):
    if identifier not in {row[0] for row in FAMILIES}:
        raise ValueError("GRADE_A_UNKNOWN_CAPABILITY")
    if split not in ("train","exam"):
        raise ValueError("GRADE_A_UNKNOWN_SPLIT")
    # Test on the same demonstrated universe sizes, never on an unintroduced
    # cardinality or structural form. Hold out semantic world/query identities
    # rather than reserving an entirely untaught shape for examination.
    n = universe_size if universe_size is not None else rng.choice((3,4))
    if n not in (3,4):
        raise ValueError("GRADE_A_UNTAUGHT_WORLD_SIZE")
    universe = sorted(rng.sample(tuple("ABCDE"), n))
    a,b = rng.sample(universe,2)
    c = next(x for x in universe if x not in (a,b))
    if identifier == "A.IDENTITY":
        w=micro.world(universe)
        q=micro.compare("EQ",micro.entity(a),micro.entity(a if positive else b))
        return micro.record(w,q),micro
    if identifier == "A.PARENT":
        w=micro.world(universe,[("PARENT",a,b)] if positive else [("PARENT",b,a)])
        return micro.record(w,micro.relation("PARENT",micro.entity(a),micro.entity(b))),micro
    if identifier == "A.LINK":
        # Direction of an asserted LINK changes without changing symmetric truth.
        edge=(b,a) if rng.randrange(2) else (a,b)
        w=micro.world(universe,[("LINK",*edge)] if positive else [("LINK",a,c)])
        return micro.record(w,micro.relation("LINK",micro.entity(a),micro.entity(b))),micro
    if identifier == "A.MEMBER":
        # Equal set cardinality across TRUE/FALSE: membership, not the
        # number of elements, must decide the answer.
        items=[a,c] if positive else [b,c]
        w=development.world(universe,sets={"K0":items})
        q=development.op("MEMBER",development.const("Entity",a),
                         development.const("Set","K0"))
    elif identifier == "A.EDGE":
        w=development.world(universe,edges=[[a,b]] if positive else [[b,a]])
        q=development.op("EDGE",development.const("Entity",a),
                         development.const("Entity",b))
    else:
        w=development.world(universe,functions={"F0":[[a,b if positive else c]]})
        q=development.op("MAPS",development.const("Function","F0"),
                         development.const("Entity",a),development.const("Entity",b))
    return development.record(w,q),development


def _draw(identifier, split, *, count, micro, development, graph, past_ids: set[str]):
    if count < 2 or count%2:
        raise ValueError("GRADE_A_REQUIRES_EVEN_POSITIVE_AND_NEGATIVE_EXAMPLES")
    seed=SEED+997*next(i for i,f in enumerate(FAMILIES) if f[0]==identifier)+\
         (0 if split=="train" else 1000003)
    rng=random.Random(seed)
    result=[]
    seen=set(past_ids)
    for i in range(count):
        positive=(i%2==0)
        universe_size=3 if (i//2)%2==0 else 4
        for _ in range(3000):
            record,library=make_record(identifier,rng,positive,split=split,
                                       micro=micro,development=development,
                                       universe_size=universe_size)
            gold=library.evaluate(record)
            independent=library.independent_evaluate(record)
            third=third_oracle(record,identifier)
            if (gold != independent or gold != third or gold not in BINARY or
                    (gold=="TRUE") != positive):
                raise ValueError("GRADE_A_INDEPENDENT_ORACLE_OR_PREDICATE_DRIFT:"+identifier)
            encoded=tuple(library.encode(record))
            source_id=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(",", ":"))
                                     .encode()).hexdigest()
            if source_id in seen:
                continue
            if not encoded or len(encoded)>96 or min(encoded)<0 or max(encoded)>=len(graph["tokens"]):
                raise ValueError("GRADE_A_LEGACY_TOKEN_CONTEXT_OR_VOCAB_DRIFT")
            seen.add(source_id)
            result.append({"id":source_id,"capability":identifier,
                           "gold":gold,"kind":"binary", "tokens":encoded,
                           "universe_size":universe_size,
                           "root":next(f[1] for f in FAMILIES if f[0]==identifier),
                           "oracle":INDEPENDENT_ORACLE,
                           "record":record})
            break
        else:
            raise ValueError("GRADE_A_EXHAUSTED_DISTINCT_SEMANTIC_RECORDS:"+identifier)
    return result


def parent_graph_binding(checkpoint: Path, source_graph: dict) -> dict:
    """Bind the exact audited parent checkpoint without loading its torch payload.

    The checkpoint bytes, full historical graph digest, and vocabulary size are
    already pinned by the historical ABI. Requiring PyTorch merely to reopen
    those immutable bytes during every runtime startup makes an MLX-native
    verifier depend on the retired neural framework. Verify the exact checkpoint
    digest and exact source graph instead, then project the previously audited
    immutable binding.
    """
    checkpoint=Path(checkpoint).resolve(strict=True)
    if digest_file(checkpoint) != AUDITED_PARENT.sha256:
        raise ValueError("GRADE_A_STUDENT_CHECKPOINT_SHA_MISMATCH")
    source_digest=hashlib.sha256(
        json.dumps(source_graph,sort_keys=True,separators=(",",":")).encode()
    ).hexdigest()
    if source_digest != PINNED_GRAPH_SHA256:
        raise ValueError(HISTORICAL_GRAPH_DRIFT_ERROR)
    if (AUDITED_PARENT.sha256 != HISTORICAL_ABI.checkpoint_sha256 or
            PINNED_FULL_STUDENT_GRAPH_SHA256 != HISTORICAL_ABI.graph_sha256):
        raise ValueError(HISTORICAL_ABI_BINDING_DRIFT_ERROR)
    if len(source_graph["tokens"]) > HISTORICAL_ABI.prefix_tokens:
        raise ValueError("GRADE_A_SOURCE_TOKENS_NOT_A_STUDENT_PREFIX")
    return {"checkpoint_sha256":AUDITED_PARENT.sha256,
            "full_student_graph_sha256":HISTORICAL_ABI.graph_sha256,
            "student_vocab_size":HISTORICAL_ABI.prefix_tokens,
            "preserved_legacy_semantic_prefix":len(source_graph["tokens"]),
            "prefix_identity_preserved":True,
            "checkpoint_written":False,
            "optimizer_updated":False}


def probe(legacy_root: Path, *, train_each=24, exam_each=12,
          champion_checkpoint: Path | None = None) -> dict:
    micro,development,graph,source_hashes,graph_hash=read_sources(legacy_root)
    course=candidate_course()
    report={}
    all_row_ids=set()
    for identifier,_,_,_ in FAMILIES:
        trained=_draw(identifier,"train",count=train_each,micro=micro,
                      development=development,graph=graph,past_ids=set())
        exam=_draw(identifier,"exam",count=exam_each,micro=micro,
                   development=development,graph=graph,
                   past_ids={r["id"] for r in trained})
        if any(r["id"] in all_row_ids for r in trained+exam):
            raise ValueError("GRADE_A_CROSS_CAPABILITY_SOURCE_REUSED")
        all_row_ids.update(r["id"] for r in trained+exam)
        train_tokens={i for row in trained for i in row["tokens"]}
        exam_tokens={i for row in exam for i in row["tokens"]}
        if not exam_tokens <= train_tokens:
            extra=sorted(exam_tokens-train_tokens)
            raise ValueError("GRADE_A_EXAM_HAS_TOKEN_NOT_IN_ITS_LESSONS:"+
                             identifier+":"+str(extra))
        if set(r["universe_size"] for r in exam) - set(r["universe_size"] for r in trained):
            raise ValueError("GRADE_A_EXAM_HAS_UNTAUGHT_WORLD_STRUCTURE")
        for row in exam:
            item=ExamItem(identifier,"binary",row["gold"],(row["root"],),(),
                          row["oracle"],row["id"])
            validate_exam_item(course,"A",item)
        for partition,rows in (("train",trained),("exam",exam)):
            if set(r["gold"] for r in rows) != set(BINARY):
                raise ValueError("GRADE_A_MISSING_TRUE_FALSE:"+identifier+":"+partition)
        report[identifier]={"source_root":next(r[1] for r in FAMILIES if r[0]==identifier),
             "train_rows":len(trained),"exam_rows":len(exam),
             "train_truth_counts":dict(Counter(r["gold"] for r in trained)),
             "exam_truth_counts":dict(Counter(r["gold"] for r in exam)),
             "max_context_tokens":max(len(r["tokens"]) for r in trained+exam),
             "train_exam_input_overlap":len(set(r["id"] for r in trained)&set(r["id"] for r in exam)),
             "unintroduced_exam_tokens":len(exam_tokens-train_tokens),
             "train_world_sizes":sorted(set(r["universe_size"] for r in trained)),
             "exam_world_sizes":sorted(set(r["universe_size"] for r in exam)),
             "train_identity_digest":hashlib.sha256(''.join(r["id"] for r in trained).encode()).hexdigest(),
             "exam_identity_digest":hashlib.sha256(''.join(r["id"] for r in exam).encode()).hexdigest()}
    binding = parent_graph_binding(champion_checkpoint,graph) if champion_checkpoint else None
    return {"schema":SCHEMA,"state":"SOURCE_ATTESTED_DRAFT_NOT_TRAINING_ADMITTED",
            "course":course.digest(),"legacy_graph_sha256":graph_hash,
            "original_source_sha256_by_file":source_hashes,
            "historic_student_graph_binding":binding,
            "capability_count":len(FAMILIES),"capabilities":report,
            "all_independent_oracle_pairs_agree":True,
            "three_source_interpreters_agree":True,
            "all_exam_semantic_tokens_taught":True,
            "neural_updates":0,"training_permission_granted":False}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-code-root",type=Path,required=True)
    parser.add_argument("--train-each",type=int,default=24)
    parser.add_argument("--exam-each",type=int,default=12)
    parser.add_argument("--champion-checkpoint",type=Path)
    args=parser.parse_args(argv)
    sys.dont_write_bytecode=True
    print(json.dumps(probe(args.legacy_code_root,train_each=args.train_each,
                           exam_each=args.exam_each,
                           champion_checkpoint=args.champion_checkpoint),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
