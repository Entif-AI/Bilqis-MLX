"""Evidence-only cross-domain bridge for the protected School50 FP32 student.

There are NO numeric-answer targets in this experiment. Computations appear
inside independently verified EQ/order, Boolean and finite-set propositions.
The purpose is to test whether bridge semantics can be retained before
asking the existing 101-way readout to emit numerical answers.
"""
from __future__ import annotations

import copy
import random

from bilqis_logic.kernel import digest
from bilqis_micro.graph import STATES
from . import arithmetic, lessons, spiral_primitive_lessons as primitive
from . import spiral_numeric_lessons as mathcourse
from . import spiral_semantic_bridge as bridge

VERSION = "bilqis.school50.bridge-foundation-lessons/v1"
ALLOCATION = {"novelty":30,"random_old":6,"nonlocal":12}
STAGES = ("identity", "successor")


def _meta(stage, n, expression, difficulty, tranche, projection, family):
    return {"grade":"B01", "concept":stage, "source_number":n,
            "difficulty":difficulty, "tranche":tranche,
            "triplet_id":bridge.source_id(expression),
            "semantic_source_id":bridge.source_id(expression),
            "split":bridge.split_of(expression),
            "source_number_split":primitive.source_split(stage,n),
            "projection":projection,"bridge_family":family,
            "mutation_mode":"bridge_relation_contrast"}


def _relation(expression, op, target, stage, n, difficulty, tranche, projection):
    question=arithmetic.row(arithmetic.operation(op,copy.deepcopy(expression),
                                                   arithmetic.atom(target)),20)
    return dict(question,answer_kind="evidence",course_meta=_meta(
        stage,n,expression,difficulty,tranche,projection,"eq_math"))


def novelty_triplet(stage,n,expression,*,tranche="novelty",opposite=False):
    """Paired exact/false equality and sensitive order, no direct numeral."""
    value=mathcourse._numeric(expression)
    if value>=arithmetic.MAX_NUMBER:
        raise ValueError("BRIDGE_FOUNDATION_RESULT_OUTSIDE_RELATIONAL_ABI")
    rows=[_relation(expression,"EQ",value,stage,n,"low",tranche,"equality_true"),
          _relation(expression,"EQ",value+1,stage,n,"medium",tranche,"equality_false")]
    rows.append(_relation(expression,"LE" if opposite else "LT",
       value-1 if opposite else value+1,stage,n,"hard",tranche,
       "order_false" if opposite else "order_true"))
    if [r["gold"] for r in rows] != ["TRUE","FALSE","FALSE" if opposite else "TRUE"]:
        raise ValueError("BRIDGE_FOUNDATION_PAIRED_ORACLE_DRIFT")
    if len({r["id"] for r in rows})!=3:
        raise ValueError("BRIDGE_FOUNDATION_DUPLICATE_PROJECTION")
    return rows


def nonlocal_triplet(stage,n,expression,family,graph,rng,*,tranche="nonlocal",split="train"):
    """Three Boolean views of one source; the numeric projection is omitted."""
    linked=bridge.linked_triplet("M01",stage,expression,family,graph,rng,
                                 tranche=tranche,split=split)
    medium,hard=linked[1:]
    expected=mathcourse._numeric(expression)
    true_count=sum(row["gold"]=="TRUE" for row in (medium,hard))
    # A balanced relation negates any two-answer class bias.
    target=(expected+int(medium["gold"]=="TRUE") if family=="iff_math" else
            expected if true_count==0 else expected+1 if true_count==2 else
            expected if bool(rng.randrange(2)) else expected+1)
    low=_relation(expression,"EQ",target,stage,n,"low",tranche,
                  "equality_true" if target==expected else "equality_false")
    low["course_meta"]["bridge_family"]=family
    result=[low,medium,hard]
    for row in result:
        row["course_meta"]["source_number"]=n
    labels={row["gold"] for row in result}
    if labels!={"TRUE","FALSE"} or len({row["id"] for row in result})!=3:
        raise ValueError("BRIDGE_FOUNDATION_NONLOCAL_CONTRAST_INVALID")
    return result


def _size(node):
    return 1 if node["kind"]=="number" else 1+sum(_size(x) for x in node["args"])


def _choose_pairs(rng,stage,split,used_numbers,*,mode="standard",previous_number=None):
    candidates=[(n,expr) for n,expr in primitive._bridge_options(stage,split)
                if (stage,n) not in used_numbers]
    rng.shuffle(candidates)
    if mode=="structural_equivalence":
        # Prioritize the deeper representation of the same semantic source.
        candidates.sort(key=lambda pair:_size(pair[1]),reverse=True)
    if mode=="minimal_counterfactual" and previous_number is not None:
        # Adjacent x versus x+1 proves the numeric factor matters.
        candidates.sort(key=lambda pair:abs(pair[0]-previous_number))
    return candidates


def _unique_add(output,used,rows):
    names=[row["id"] for row in rows]
    if len(set(names))!=len(names) or any(key in used for key in names):
        return False
    output.extend(rows)
    used.update(names)
    return True


def compile_batch(library,graph,rng,*,method="standard"):
    """10 new, 2 real School50 rehearsal, 4 nonlocal triplets; all evidence."""
    if method not in ("standard","structural_equivalence","minimal_counterfactual"):
        raise ValueError("BRIDGE_FOUNDATION_UNKNOWN_INSTRUCTION")
    result=[];used=set();source_numbers=set();recent={}
    # Deliberately balance neutral identity with one-step successor.
    for index in range(10):
        stage=STAGES[index%2]
        candidates=_choose_pairs(rng,stage,"train",source_numbers,mode=method,
                                 previous_number=recent.get(stage))
        for n,expression in candidates:
            rows=novelty_triplet(stage,n,expression,
                opposite=(index//2)%2==1)
            if _unique_add(result,used,rows):
                source_numbers.add((stage,n))
                recent[stage]=n
                break
        else:
            raise ValueError("BRIDGE_FOUNDATION_NOVELTY_SOURCE_EXHAUSTED")
    for index,family in enumerate(bridge.FAMILIES):
        stage=STAGES[index%2]
        for n,expression in _choose_pairs(rng,stage,"train",source_numbers,mode=method):
            try:
                rows=nonlocal_triplet(stage,n,expression,family,graph,rng)
            except ValueError as error:
                if str(error) in ("BRIDGE_SET_PARTITION_EXHAUSTED",
                                  "BRIDGE_96_TOKEN_CONTEXT_OVERFLOW",
                                  "BRIDGE_FOUNDATION_NONLOCAL_CONTRAST_INVALID"):
                    continue
                raise
            if _unique_add(result,used,rows):
                source_numbers.add((stage,n))
                break
        else:
            raise ValueError("BRIDGE_FOUNDATION_NONLOCAL_SOURCE_EXHAUSTED")
    for prior in ("G09","G10"):
        for _ in range(300):
            rows=mathcourse.earlier_triplet(library,graph,rng,(prior,),depth=2)
            if not all(row["answer_kind"]=="evidence" and
                       primitive.admissible_rehearsal(row) for row in rows):
                continue
            if _unique_add(result,used,rows):
                for row in rows:
                    row["course_meta"]["retention"]=True
                break
        else:
            raise ValueError("BRIDGE_FOUNDATION_HISTORICAL_REHEARSAL_EXHAUSTED")
    validate_rows(result,graph,split="train")
    counts={tag:sum(row["course_meta"]["tranche"]==tag for row in result)
            for tag in ALLOCATION}
    if counts!=ALLOCATION or len(result)!=48:
        raise ValueError("BRIDGE_FOUNDATION_ALLOCATION_CHANGED")
    return result,counts


def panel(graph,*,split,fold="primary",seed=20261013,per_family=2):
    """Development primary and confirmation use disjoint *number* sources."""
    if split not in ("development","sealed") or fold not in ("primary","confirm"):
        raise ValueError("BRIDGE_FOUNDATION_UNKNOWN_PANEL")
    if not 1<=per_family<=2:
        raise ValueError("BRIDGE_FOUNDATION_INVALID_PANEL_SIZE")
    rng=random.Random(seed+ (1 if fold=="confirm" else 0)*771903 +
                      (9 if split=="sealed" else 0)*100003)
    numbers=sorted({n for stage in STAGES for n,_ in
                    primitive._bridge_options(stage,split)})
    numbers=numbers[::2] if fold=="primary" else numbers[1::2]
    output=[];used=set()
    for family in bridge.FAMILIES:
        for count in range(per_family):
            stage=STAGES[(bridge.FAMILIES.index(family)+count)%2]
            options=[(n,expr) for n,expr in primitive._bridge_options(stage,split)
                     if n in numbers]
            rng.shuffle(options)
            for n,expression in options:
                try:rows=nonlocal_triplet(stage,n,expression,family,graph,rng,
                       tranche="exam",split=split)
                except ValueError as error:
                    if str(error) in ("BRIDGE_SET_PARTITION_EXHAUSTED",
                                      "BRIDGE_96_TOKEN_CONTEXT_OVERFLOW",
                                      "BRIDGE_FOUNDATION_NONLOCAL_CONTRAST_INVALID"):
                        continue
                    raise
                if _unique_add(output,used,rows):break
            else:raise ValueError("BRIDGE_FOUNDATION_EXAM_SOURCE_EXHAUSTED")
    validate_rows(output,graph,split=split)
    if len(output)!=3*per_family*len(bridge.FAMILIES):
        raise ValueError("BRIDGE_FOUNDATION_EXAM_COUNT_DRIFT")
    return output


def validate_rows(rows,graph,*,split):
    if not rows or len({r["id"] for r in rows})!=len(rows):
        raise ValueError("BRIDGE_FOUNDATION_EMPTY_OR_DUPLICATE")
    for row in rows:
        if row["answer_kind"]!="evidence" or row["gold"] not in STATES or (
                row["course_meta"]["tranche"]!="random_old" and
                row["gold"] not in ("TRUE","FALSE")):
            raise ValueError("BRIDGE_FOUNDATION_NUMERIC_TARGET_LEAK")
        record=row["input"]
        metadata=row["course_meta"]
        if record["task"]==arithmetic.VERSION:
            value=arithmetic.evaluate(record["expression"])
            if type(value) is not bool or row["gold"] != ("TRUE" if value else "FALSE"):
                raise ValueError("BRIDGE_FOUNDATION_RELATION_ORACLE_DRIFT")
            lessons.valid_rows([row],graph)
        elif record["task"]==bridge.VERSION:
            bridge.validate_rows([row],graph,partition=split)
        else:
            lessons.valid_rows([row],graph)
        if metadata.get("source_number") is not None:
            if primitive.source_split("identity",metadata["source_number"])!=split:
                raise ValueError("BRIDGE_FOUNDATION_NUMBER_SOURCE_LEAK")
        if metadata.get("split",split)!=split:
            raise ValueError("BRIDGE_FOUNDATION_EXPRESSION_SOURCE_LEAK")
        if not primitive.admissible_rehearsal(row) and split=="train":
            raise ValueError("BRIDGE_FOUNDATION_HISTORICAL_ALIAS_LEAK")
