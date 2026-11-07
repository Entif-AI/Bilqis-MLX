"""Source-context helpers for the C02 Factory training composition seam."""
from __future__ import annotations

from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, TaskScope,
)
from bilqis_mlx.semantics.frame_schema import FrameInstance, FrameTree


def training_answer_plan(prefix, release, kind, generation_binding):
    head = next(item for item in release.answer_heads if item.kind == kind)
    return {
        "modalityID": head.modality_id,
        "input_prefix_end": prefix.visible_end,
        "decisions": [
            {"id": "value", "roleID": "answer", "occurrence": 0,
             "kind": "VALUE", "legalValues": list(head.values),
             "depends_on": []},
            {"id": "end", "roleID": "end", "occurrence": 0,
             "kind": "CONTROL", "legalValues": ["END_FRAME"],
             "depends_on": ["value"]},
        ],
        "allowedOutputSchema": "factory-training/v1",
        "maximum_decisions": 2,
        "generation_binding": generation_binding,
    }


def public_training_context(release: str, capability: str, prefix_end: int):
    task = TaskScope(
        "bamf-factory-trainer", "bamf-factory", "TRAINING", release,
        "LOCAL", capability, 0, 0, prefix_end)
    policy = ContextPolicy(
        "bamf-factory-public-formal/v1", 1, 1,
        ("TRAINING",), (PUBLIC_FORMAL,), ("LOCAL",), (capability,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        tuple((PUBLIC_FORMAL,) * count for count in range(3, 25)))
    return task, SourceFrontier(1, 1, ()), policy


def schemas_cover_tree(tree: FrameTree, schema_ids: frozenset[str]) -> bool:
    root = tree.root
    return ((isinstance(root, FrameInstance)
             and root.frame_schema_id in schema_ids)
            and all(schemas_cover_tree(child, schema_ids) for child in tree.children))


__all__ = (
    "public_training_context", "schemas_cover_tree", "training_answer_plan",
)
