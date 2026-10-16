"""Neural-inert evaluation of the *actual* complete historical student.

The 72 candidate Grade A examination inputs are source-attested, frozen and
never learned here. This is a diagnostic baseline, not a released New Ithkuil
curriculum, a lesson loop or permission for an optimizer update.
"""
from __future__ import annotations

from collections import Counter
import argparse
import json
from pathlib import Path
import sys

from .backup import digest_file
from .champions import Checkpoint
from .grade_a_evaluator import score_predictions
from .grade_a_manifest import verify_manifest
from .grade_a_probe import candidate_course
from .mlx_parity import forward
from .source import AUDITED_PARENT
from .semantics.abi import HISTORICAL_PREFIX_SIZE


def _fixed_batch(rows: list[dict]):
    import numpy as np
    if not rows:
        raise ValueError("GRADE_A_BASELINE_EMPTY_BATCH")
    lengths = np.asarray([len(row["tokens"]) for row in rows], dtype=np.int32)
    if min(lengths) < 1 or max(lengths) > 96:
        raise ValueError("GRADE_A_BASELINE_INVALID_CONTEXT")
    ids = np.zeros((len(rows), int(max(lengths))), dtype=np.int32)
    for i, row in enumerate(rows):
        ids[i, :lengths[i]] = row["tokens"]
    return ids, lengths


def _summarize(rows: list[dict], predictions: dict[str, str]) -> dict:
    result = {}
    for cap in candidate_course().grades[0].capabilities:
        current = [row for row in rows if row["capability"] == cap.id]
        result[cap.id] = {
            "correct": sum(predictions[r["id"]] == r["gold"] for r in current),
            "total": len(current),
            "predicted_label_counts": dict(sorted(Counter(
                predictions[r["id"]] for r in current).items())),
        }
    return result


def evaluate_parent(manifest: dict, legacy_root: Path, checkpoint: Path,
                    *, device: str = "cpu", batch_size: int = 12,
                    parity_tolerance: float = 2e-3) -> dict:
    """Score the pinned model with both full-five-state and constrained binary heads."""
    if device not in ("cpu", "gpu") or type(batch_size) is not int or not 1 <= batch_size <= 72:
        raise ValueError("GRADE_A_BASELINE_INVALID_DEVICE_OR_BATCH")
    checkpoint = Path(checkpoint).resolve(strict=True)
    legacy_root = Path(legacy_root).resolve(strict=True)
    source_check = verify_manifest(manifest, legacy_root, checkpoint)

    import mlx.core as mx
    import numpy as np
    import torch
    from bilqis_development.continuation import load
    from bilqis_micro.graph import STATES

    mx.set_default_device(mx.cpu if device == "cpu" else mx.gpu)
    model, optimizer, payload = load(checkpoint)
    model.eval()
    if (payload["config"]["precision"] != "fp32" or
            len(payload["graph"]["tokens"]) != HISTORICAL_PREFIX_SIZE or
            tuple(STATES[:2]) != ("FALSE", "TRUE")):
        raise ValueError("GRADE_A_BASELINE_SOURCE_OR_LABEL_ABI_DRIFT")
    answer_ids = model.answer_ids.cpu().numpy().tolist()
    if len(answer_ids) != len(STATES):
        raise ValueError("GRADE_A_BASELINE_FULL_ANSWER_HEAD_CHANGED")
    tensors = {name: mx.array(t.detach().cpu().numpy(), dtype=mx.float32)
               for name, t in model.state_dict().items()}
    c = payload["config"]
    records = manifest["examination_rows"]
    raw = {}
    binary = {}
    max_error = 0.0
    for offset in range(0, len(records), batch_size):
        chosen = records[offset:offset+batch_size]
        ids, lengths = _fixed_batch(chosen)
        with torch.no_grad():
            native = model(torch.tensor(ids, dtype=torch.long),
                           torch.tensor(lengths, dtype=torch.long)).cpu().numpy()
        alternative = forward(mx, tensors, ids, lengths, heads=c["heads"],
                              layers=c["layers"], answer_ids=answer_ids)
        if (native.shape != alternative.shape or not np.isfinite(native).all()
                or not np.isfinite(alternative).all()):
            raise ValueError("GRADE_A_BASELINE_LOGIT_SHAPE_OR_FINITENESS_DRIFT")
        error = float(np.max(np.abs(native-alternative)))
        max_error = max(max_error, error)
        if max_error > parity_tolerance:
            raise ValueError("GRADE_A_BASELINE_MLX_PYTORCH_INFERENCE_MISMATCH")
        for row, logits in zip(chosen, alternative):
            raw[row["id"]] = STATES[int(np.argmax(logits))]
            # Report separately, not as if the model's full five-state
            # answer had magically become a correct Boolean answer.
            binary[row["id"]] = STATES[int(np.argmax(logits[:2]))]
    checkpoint_pointer = Checkpoint(AUDITED_PARENT.sha256, checkpoint.name,
                                    AUDITED_PARENT.optimizer_step, True)
    assessment = score_predictions(
        manifest, candidate_course(), checkpoint_pointer, binary,
        legacy_root=legacy_root, source_checkpoint=checkpoint)
    if (set(raw) != set(binary) or len(raw) != 72 or
            source_check["verified_items"] != 216 or
            digest_file(checkpoint) != AUDITED_PARENT.sha256):
        raise ValueError("GRADE_A_BASELINE_SOURCE_OR_EXAM_CUSTODY_CHANGED")
    native_steps = {int(cell["step"].item())
                    for cell in optimizer.state.values() if "step" in cell}
    if native_steps != {AUDITED_PARENT.optimizer_step}:
        raise ValueError("GRADE_A_BASELINE_OPTIMIZER_STEP_CHANGED")
    return {
        "status": "HISTORICAL_STUDENT_READ_ONLY_CANDIDATE_GRADE_A_EXAM",
        "source_checkpoint_sha256": AUDITED_PARENT.sha256,
        "source_optimizer_step": AUDITED_PARENT.optimizer_step,
        "source_token_count": len(payload["graph"]["tokens"]),
        "source_manifest_sha256": manifest["manifest_sha256"],
        "exam_rubric_sha256": assessment.rubric_digest,
        "exam_count": len(raw),
        "full_five_state_predictions": _summarize(records, raw),
        "binary_constrained_predictions": _summarize(records, binary),
        "binary_constrained_total_correct": sum(s.correct for s in assessment.scores.values()),
        "full_five_state_total_correct": sum(raw[row["id"]] == row["gold"] for row in records),
        "mlx_device": device,
        "mlx_pytorch_max_logit_abs_error": max_error,
        "mlx_pytorch_parity_tolerance": parity_tolerance,
        "source_checkpoint_unchanged": True,
        "actual_student_optimizer_updates": 0,
        "training_permission_granted": False,
        "new_ithkuil_forms_certified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-code-root", type=Path, required=True)
    parser.add_argument("--champion-checkpoint", type=Path, required=True)
    parser.add_argument("--grade-a-manifest", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--batch-size", type=int, default=12)
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    manifest = json.loads(args.grade_a_manifest.read_text(encoding="utf-8"))
    result = evaluate_parent(
        manifest, args.legacy_code_root, args.champion_checkpoint,
        device=args.device, batch_size=args.batch_size)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
