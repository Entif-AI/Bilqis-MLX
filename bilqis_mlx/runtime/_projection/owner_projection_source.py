"""Private accepted-generation source capability for C10 owner projections."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .akasha_outbox import _invalid


def build_accepted_source_loader():
    """Return a loader and verifier whose issuance registry stays closure-private."""
    issued = {}
    issuer = object()

    @dataclass(frozen=True, init=False)
    class AcceptedGenerationProjectionSource:
        root: Path
        manifest_sha256: str
        student: object
        binding: object
        parent: object | None
        parent_binding: object | None
        _issuance: object

        def __init__(self, *args, **kwargs):
            _invalid("BAMF_C10_ACCEPTED_OWNER_SOURCE_REQUIRED")

    def issue(root, manifest_sha256, student, binding, parent, parent_binding):
        source = object.__new__(AcceptedGenerationProjectionSource)
        for name, value in (
                ("root", root), ("manifest_sha256", manifest_sha256),
                ("student", student), ("binding", binding),
                ("parent", parent), ("parent_binding", parent_binding),
                ("_issuance", issuer)):
            object.__setattr__(source, name, value)
        issued[id(source)] = source
        return source

    def require(source):
        if (type(source) is not AcceptedGenerationProjectionSource
                or issued.get(id(source)) is not source
                or source._issuance is not issuer):
            _invalid("BAMF_C10_ACCEPTED_OWNER_SOURCE_REQUIRED")
        return source

    def load(root: Path):
        from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle
        from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
            accepted_binding_for_manifest,
            accepted_generation,
            parent_acceptance_anchor_from_manifest,
        )

        root = Path(root)
        pointer, student = accepted_generation(root / "bamf-state.json")
        binding = accepted_binding_for_manifest(
            root, pointer["manifest_sha256"], student,
            expected_acceptance_sha256=pointer["acceptance_sha256"])
        parent = None
        parent_binding = None
        if student.parent_manifest_sha256 is not None:
            parent = load_bamf_bundle(
                root / "bamf-bundles" / student.parent_manifest_sha256,
                expected_manifest_sha256=student.parent_manifest_sha256)
            parent_acceptance_sha256 = parent_acceptance_anchor_from_manifest(
                root, pointer["manifest_sha256"])
            if parent_acceptance_sha256 is not None:
                parent_binding = accepted_binding_for_manifest(
                    root, student.parent_manifest_sha256, parent,
                    expected_acceptance_sha256=parent_acceptance_sha256)
        return issue(
            root, pointer["manifest_sha256"], student, binding,
            parent, parent_binding)

    return load, require
