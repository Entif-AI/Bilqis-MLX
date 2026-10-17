"""M01 as a source-verifiable staircase of small arithmetic primitives.

All neural inputs use existing School50 ADD/SUB/EQ/LT/LE tokens and the
unchanged 0..100 output ABI. GT and GTE are projections of LT/LE with
operands exchanged; signed unary negation is deliberately NOT invented.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import random

from bilqis_logic.kernel import digest
from . import arithmetic, lessons, spiral_numeric_lessons as mathcourse
from . import spiral_semantic_bridge as bridge

VERSION = "bilqis.school50.m01-primitives/v1"
STAGES = ("identity", "successor", "order", "inverse", "compose", "addition")
SPLITS = {"train": range(6), "development": (6,7), "sealed": (8,9)}


def _n(x):
    return arithmetic.atom(x)


def _op(name,*children):
    return arithmetic.operation(name,*children)


def source_split(stage, n):
    if stage not in STAGES or type(n) is not int or not 1 <= n <= 70:
        raise ValueError("PRIMITIVE_INVALID_SEMANTIC_SOURCE")
    # Source partition is shared *across primitive stages*. For example,
    # ADD(n,1) is used both by successor and order: it cannot be seen during
    # successor training and then masquerade as held-out order transfer.
    bucket=int(digest(["school50-primitive-source/v1",n])[:12],16)%10
    return "train" if bucket<6 else "development" if bucket<8 else "sealed"


def expression(stage, n, difficulty):
    """One n and one law across the low/medium/hard triplet."""
    if stage not in STAGES or difficulty not in mathcourse.DIFFICULTIES:
        raise ValueError("PRIMITIVE_UNKNOWN_STAGE_OR_DIFFICULTY")
    if not 1 <= n <= 70:
        raise ValueError("PRIMITIVE_NUMBER_OUTSIDE_SOURCE_DOMAIN")
    d=mathcourse.DIFFICULTIES.index(difficulty)
    if stage=="identity":
        forms=(_op("ADD",_n(n),_n(0)), _op("ADD",_n(0),_n(n)),
               _op("ADD",_op("ADD",_n(n),_n(0)),_n(0)))
    elif stage in ("successor","order"):
        forms=(_op("ADD",_n(n),_n(1)),
               _op("ADD",_op("ADD",_n(n),_n(0)),_n(1)),
               _op("ADD",_n(n),_op("ADD",_n(0),_n(1))))
    elif stage=="inverse":
        # SUB is a partial inverse on nonnegative integers. Every expression
        # retains n as its answer, without requiring negative output tokens.
        forms=(_op("SUB",_op("ADD",_n(n),_n(1)),_n(1)),
               _op("ADD",_op("SUB",_n(n),_n(1)),_n(1)),
               _op("SUB",_op("ADD",_op("ADD",_n(n),_n(1)),_n(1)),_n(2)))
    elif stage=="compose":
        forms=(_op("ADD",_n(n),_n(2)),
               _op("ADD",_op("ADD",_n(n),_n(1)),_n(1)),
               _op("ADD",_n(n),_op("ADD",_n(1),_n(1))))
    else:
        forms=(_op("ADD",_n(n),_n(3)),
               _op("ADD",_op("ADD",_n(n),_n(1)),_n(2)),
               _op("ADD",_n(n),_op("ADD",_n(1),_n(2))))
    answer=mathcourse._numeric(forms[d])
    expected=n+(0 if stage in ("identity","inverse") else
                1 if stage in ("successor","order") else
                2 if stage=="compose" else 3)
    if answer!=expected:
        raise ValueError("PRIMITIVE_ORACLE_IDENTITY_FAILED")
    return forms[d]


def _meta(stage,n,difficulty,tranche,projection):
    return {"grade":"M01","concept":stage,"difficulty":difficulty,
            "tranche":tranche,"triplet_id":digest([VERSION,stage,n]),
            "semantic_source_id":digest([VERSION,stage,n]),
            "source_number":n,"split":source_split(stage,n),
            "mutation_mode":"primitive_semantic_projection",
            "projection":projection}


def _numeric_row(stage,n,difficulty,tranche):
    expr=expression(stage,n,difficulty)
    row=mathcourse._row("M01",expr,difficulty=difficulty,tranche=tranche,
                        triplet=digest([VERSION,stage,n]),mode="primitive")
    row["course_meta"]=_meta(stage,n,difficulty,tranche,"direct_number")
    return row


def _comparison(stage,n,difficulty,tranche):
    """EQ/LT/LE plus the semantically equivalent mirrored GT/GTE views."""
    expr=expression(stage,n,"low")
    val=mathcourse._numeric(expr)
    if difficulty=="medium":
        # TRUE and FALSE equalities/strict order. Relevant operand changes
        # flip the answer; no candidate answer becomes a direct-number input.
        alternatives=(
            _op("EQ",copy.deepcopy(expr),_n(val)),
            _op("EQ",copy.deepcopy(expr),_n(val-1)),
            _op("LT",copy.deepcopy(expr),_n(val+1)),
            _op("LE",copy.deepcopy(expr),_n(val-1)),
        )
        operator_label=("EQ","EQ","LT","LE")[n%4]
    elif difficulty=="hard":
        alternatives=(
            _op("LT",_n(val-1),copy.deepcopy(expr)), # GT mirrored
            _op("LT",copy.deepcopy(expr),_n(val-1)), # false LT
            _op("LE",_n(val),copy.deepcopy(expr)), # GTE mirrored
            _op("LE",_n(val+1),copy.deepcopy(expr)), # false GTE mirrored
        )
        operator_label=("GT(mirrored)","LT","GTE(mirrored)","GTE(mirrored)")[n%4]
    else:
        raise ValueError("PRIMITIVE_COMPARISON_NEEDS_PROPOSITION")
    item=arithmetic.row(alternatives[n%4],20)
    result=dict(item,answer_kind="evidence")
    result["course_meta"]=_meta(stage,n,difficulty,tranche,operator_label)
    return result


def triplet(stage,n,*,tranche="novelty",mode="standard"):
    if source_split(stage,n)!="train" and tranche!="exam":
        raise ValueError("PRIMITIVE_HELD_OUT_SOURCE_IN_TRAINING")
    result=[_numeric_row(stage,n,"low",tranche)]
    for difficulty in ("medium","hard"):
        result.append(_comparison(stage,n,difficulty,tranche)
                      if stage=="order" else _numeric_row(stage,n,difficulty,tranche))
    if len({row["id"] for row in result})!=3:
        raise ValueError("PRIMITIVE_DUPLICATE_LINKED_VARIANT")
    if mode=="structural_equivalence":
        # Explicitly teach the no-op program combinator. This is the same
        # numerical source under a different, oracle-checked AST.
        for row in result:
            if row["answer_kind"]=="numeric" and row["course_meta"]["difficulty"]=="hard":
                expr=row["input"]["expression"]
                transformed=_op("ADD",copy.deepcopy(expr),_n(0))
                if mathcourse._numeric(transformed)!=row["gold"]:
                    raise ValueError("PRIMITIVE_INVARIANT_REWRITE_CHANGED_VALUE")
                row["input"]["expression"]=transformed
                row["id"]=digest(row["input"])
                row["course_meta"]["mutation_mode"]="structural_equivalence"
    elif mode=="minimal_counterfactual":
        for row in result:
            row["course_meta"]["mutation_mode"]="paired_numeric_counterfactual"
    elif mode!="standard":
        raise ValueError("PRIMITIVE_INVALID_TEACHING_METHOD")
    return result


def _bridge_source_variants(stage,n):
    """Distinct ABI-safe neutral rewrites, all owned by the SAME source n."""
    base=expression(stage,n,"low")
    forms=(base,_op("ADD",copy.deepcopy(base),_n(0)),
           _op("ADD",_n(0),copy.deepcopy(base)),
           _op("SUB",copy.deepcopy(base),_n(0)),
           _op("ADD",_op("ADD",copy.deepcopy(base),_n(0)),_n(0)),
           _op("ADD",_n(0),_op("ADD",copy.deepcopy(base),_n(0))),
           _op("SUB",_op("ADD",copy.deepcopy(base),_n(0)),_n(0)),
           _op("ADD",_op("SUB",copy.deepcopy(base),_n(0)),_n(0)))
    for candidate in forms:
        if mathcourse._numeric(candidate)!=mathcourse._numeric(base):
            raise ValueError("PRIMITIVE_BRIDGE_REWRITE_NOT_EQUIVALENT")
        yield candidate


def _source_options(stage,split):
    for n in range(1,71):
        if source_split(stage,n)!=split:
            continue
        yield n


def _bridge_options(stage,split):
    for n in _source_options(stage,split):
        for expr in _bridge_source_variants(stage,n):
            if bridge.split_of(expr)==split:
                yield n,expr


@lru_cache(maxsize=1)
def _known_primitive_sources():
    """Known exact primitive ASTs across every stage, with source owners."""
    result={}
    for stage in STAGES:
        for n in range(1,71):
            for difficulty in mathcourse.DIFFICULTIES:
                result.setdefault(digest(expression(stage,n,difficulty)),n)
            for expr in _bridge_source_variants(stage,n):
                result.setdefault(digest(expr),n)
    return result


def admissible_expression_for_split(expr,split):
    """A known primitive AST retains its number-owner across every grade."""
    if split not in SPLITS:
        raise ValueError("PRIMITIVE_UNKNOWN_SPLIT")
    known=_known_primitive_sources()
    pending=[expr]
    while pending:
        node=pending.pop()
        if node["kind"]=="op":
            owner=known.get(digest(node))
            if owner is not None and source_split("identity",owner)!=split:
                return False
            pending.extend(node["args"])
    return True


def admissible_rehearsal(row):
    """Exclude historical math exposures of held-out primitive source ASTs."""
    if not mathcourse.admissible_legacy_math(row):
        return False
    record=row["input"]
    if record.get("task")==arithmetic.VERSION:
        return admissible_expression_for_split(record["expression"],"train")
    if record.get("task")==bridge.VERSION:
        return admissible_expression_for_split(record["math_expression"],"train")
    return True


def compile_batch(stage,library,graph,rng,*,previous,mode="standard"):
    """Keep exactly 10/2/4 concept triplets; use current prerequisites."""
    if stage not in STAGES:
        raise ValueError("PRIMITIVE_UNKNOWN_STAGE")
    options=list(_source_options(stage,"train"))
    rng.shuffle(options)
    if len(options)<10:
        raise ValueError("PRIMITIVE_INSUFFICIENT_TRAIN_CONCEPTS")
    rows=[]
    if mode=="minimal_counterfactual":
        # Show adjacent source numbers together, allowing answer-changing
        # interventions without abandoning the shared concept identity.
        pairs=[(n,n+1) for n in options if n+1 in options]
        rng.shuffle(pairs)
        selected=[]
        for a,b in pairs:
            if a not in selected and b not in selected:
                selected.extend((a,b))
            if len(selected)==10:break
        if len(selected)<10:
            selected=list(options[:10])
    else:
        selected=options[:10]
    for n in selected:
        rows.extend(triplet(stage,n,mode=mode))
    seen={row["id"] for row in rows}
    bridge_options=list(_bridge_options(stage,"train"))
    rng.shuffle(bridge_options)
    if len(bridge_options)<4:
        raise ValueError("PRIMITIVE_INSUFFICIENT_NONLOCAL_CONCEPTS")
    bridge_options=[(n,expr) for n,expr in bridge_options if n not in selected]
    if len(bridge_options)<4:
        raise ValueError("PRIMITIVE_NONLOCAL_SOURCE_COLLIDES_WITH_NOVELTY")
    for family in bridge.FAMILIES:
        for _n_value,source in bridge_options:
            linked=bridge.linked_triplet("M01",stage,source,family,graph,rng,
                                         tranche="nonlocal",split="train")
            identities={r["id"] for r in linked}
            if len(identities)!=3 or seen.intersection(identities):
                continue
            rows.extend(linked)
            seen.update(identities)
            break
        else:
            raise ValueError("PRIMITIVE_NONLOCAL_SOURCE_COLLISION_EXHAUSTED")
    for _ in range(2):
        for _attempt in range(300):
            earlier=mathcourse.earlier_triplet(library,graph,rng,previous,depth=2)
            if not all(admissible_rehearsal(row) for row in earlier):
                continue
            identities={r["id"] for r in earlier}
            if len(identities)!=3 or seen.intersection(identities):
                continue
            rows.extend(earlier)
            seen.update(identities)
            break
        else:
            raise ValueError("PRIMITIVE_OLD_REHEARSAL_IDENTITY_EXHAUSTED")
    if len(rows)!=48 or len({row["id"] for row in rows})!=48:
        raise ValueError("PRIMITIVE_BATCH_ALLOCATION_OR_IDENTITY_DRIFT")
    counts={name:sum(row["course_meta"]["tranche"]==name for row in rows)
            for name in mathcourse.ALLOC}
    if counts!={"novelty":30,"random_old":6,"nonlocal":12}:
        raise ValueError("PRIMITIVE_10_2_4_VIOLATION")
    numbers=[row for row in rows if row["answer_kind"]=="numeric"]
    mathcourse.validate_rows(numbers,graph)
    old=[r for r in rows if r["answer_kind"]=="evidence" and
         r["input"].get("task")!=bridge.VERSION]
    if old:lessons.valid_rows(old,graph)
    composites=[r for r in rows if r["input"].get("task")==bridge.VERSION]
    if composites:bridge.validate_rows(composites,graph,partition="train")
    return rows,counts


def panel(stage,graph,*,split,seed,count=4,exclude=()):
    """Stable, untouched source-number identities across train/dev/sealed."""
    if split not in SPLITS:
        raise ValueError("PRIMITIVE_UNKNOWN_SPLIT")
    rng=random.Random(seed+STAGES.index(stage)*15101)
    options=[n for n in _source_options(stage,split) if n not in exclude]
    rng.shuffle(options)
    if len(options)<count:
        raise ValueError("PRIMITIVE_PANEL_SOURCE_EXHAUSTED")
    rows=[]
    for n in options[:count]:
        rows.extend(triplet(stage,n,tranche="exam"))
    if len(rows)!=3*count or len({r["id"] for r in rows})!=3*count:
        raise ValueError("PRIMITIVE_EXAM_DIVERSITY_DRIFT")
    for r in rows:
        if r["course_meta"]["split"]!=split:
            raise ValueError("PRIMITIVE_EXAM_SOURCE_LEAK")
    return rows


def bridge_panel(stage,graph,*,split,seed,count=2,exclude=()):
    rng=random.Random(seed+STAGES.index(stage)*997)
    choices=[(n,expr) for n,expr in _bridge_options(stage,split)
             if bridge.source_id(expr) not in exclude]
    rng.shuffle(choices)
    if len(choices)<count*3:
        raise ValueError("PRIMITIVE_BRIDGE_PANEL_DIVERSITY")
    rows=[]
    for i,(n,expr) in enumerate(choices[:count*3]):
        family=bridge.FAMILIES[i%len(bridge.FAMILIES)]
        linked=bridge.linked_triplet("M01",stage,expr,
                    family,graph,rng,tranche="exam",split=split)
        for row in linked[1:]:
            row["course_meta"]["source_number"]=n
            rows.append(row)
    if len(rows)!=count*6 or len({r["id"] for r in rows})!=len(rows):
        raise ValueError("PRIMITIVE_BRIDGE_EXAM_ALIAS")
    return rows
