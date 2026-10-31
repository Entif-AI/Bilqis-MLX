"""Read-only calls into the original instruction and batch compiler."""
from copy import deepcopy
import importlib
from pathlib import Path
from .source import _source_stack
from .lessons import _native_output

_GRADE_NOT_IN_SOURCE = "PARITY_PREDECESSOR_GRADE_NOT_IN_SOURCE"


def predecessor_teaching_batch(legacy_root: Path, *, grade="B01",
                               seed=2001, method="standard") -> dict:
    """Execute the original School50 v10 batch compiler, without training.

    It already implemented instruction methods, exact acquisition replays,
    six direct-number answers, paired contrasts and historical rehearsal.
    Carry over its method semantics instead of writing a lookalike sampler.
    Old B codes remain provenance aliases, not admitted MLX grade names.
    """
    import random
    source, arithmetic, _, micro, graph, source_sha = _source_stack(legacy_root)
    library = importlib.import_module("bilqis_school.lessons")
    bridge = importlib.import_module("bilqis_school.spiral_semantic_bridge")
    for module, relative in ((library, "bilqis_school/lessons.py"),
                             (bridge, "bilqis_school/spiral_semantic_bridge.py")):
        if Path(module.__file__).resolve() != Path(legacy_root).resolve() / relative:
            raise ValueError("PARITY_TEACHER_SOURCE_ROOT_DRIFT")
    if grade not in source.GRADES:
        raise ValueError(_GRADE_NOT_IN_SOURCE)
    rows, allocation = source.compile_batch(
        grade, library.TeacherLibrary(), graph, random.Random(seed), method=method)
    source.validate_rows(rows, graph, split="train", expected=48)
    mapping = {token: i for i, token in enumerate(graph["tokens"])}
    converted = []
    for row in rows:
        record = row["input"]
        if record.get("task") == arithmetic.VERSION:
            tokens = arithmetic.encode(record, mapping)
        elif record.get("task") == bridge.VERSION:
            tokens = bridge.encode(record, graph)
        else:
            tokens = library.encode(row, graph)
        kind = "numeric_0_3" if row["answer_kind"] == "numeric" else "evidence"
        gold = str(row["gold"]) if kind == "numeric_0_3" else row["gold"]
        if (kind == "numeric_0_3" and gold not in ("0", "1", "2", "3") or
                kind == "evidence" and gold not in micro.STATES or
                not tokens or len(tokens) > 96 or
                any(type(t) is not int or not 0 <= t < len(mapping) for t in tokens)):
            raise ValueError("PARITY_SOURCE_TEACHER_BATCH_CASTE_OR_CODEC_DRIFT")
        meta = row["course_meta"]
        native = _native_output(kind, gold, mapping)
        converted.append({"id": row["id"], "tokens": tokens,
                          "answer_kind": kind, "gold": gold,
                          **({"native_output": native} if native else {}),
                          "tranche": meta["tranche"],
                          "semantic_source_id": meta.get("semantic_source_id"),
                          "projection": meta.get("projection")})
    numeric_replay = [r["id"] for fold in ("primary", "confirm")
                      for r in source.numeric_panel(graph, fold=fold)]
    truth_replay = [r["id"] for fold in ("primary", "confirm")
                    for r in source.panel(grade, graph, fold=fold)]
    replay_ids = numeric_replay + truth_replay
    if (len(rows) != 48 or len(set(replay_ids)) != 16 or
            not set(replay_ids) <= {r["id"] for r in converted}):
        raise ValueError("PARITY_PREDECESSOR_REPLAY_NOT_TAUGHT")
    return {"source_sha256": source_sha, "method": method,
            "legacy_grade": grade, "rows": converted,
            "allocation": allocation, "replay_ids": replay_ids,
            "scope": "TEACHER_FIXTURE_REPLAY_NOT_NEW_GRADE_ADMISSION",
            "training_authorized": False}


def predecessor_instruction_choice(legacy_root: Path, teacher: dict, *,
                                   grade="B01", seed=9, used=()) -> str:
    """Reuse the original UCB lesson-method selection without teacher writes.

    Old B01 is an archived source label, never an admitted MLX grade.
    New methods and reward semantics require their own source-attested release.
    """
    import random
    source, _, _, _, _, _ = _source_stack(legacy_root)
    staged = importlib.import_module("bilqis_school.spiral_staged_runner")
    if Path(staged.__file__).resolve() != (Path(legacy_root).resolve() /
                                          "bilqis_school/spiral_staged_runner.py"):
        raise ValueError("PARITY_TEACHER_METHOD_SOURCE_ROOT_DRIFT")
    if grade not in source.GRADES:
        raise ValueError(_GRADE_NOT_IN_SOURCE)
    chosen = staged._choose_instruction(
        deepcopy(teacher), grade, random.Random(seed), used=used)
    if chosen not in staged.INSTRUCTIONAL_METHODS:
        raise ValueError("PARITY_PREDECESSOR_METHOD_ABI_DRIFT")
    return chosen
