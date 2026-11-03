"""Portable cognitive package staging; no learner or optimizer writes."""
from .contracts import PackageArtifact, PackageBinding, PackageKind, SourceRights
from .records import CognitivePackage, ExportSnapshot, ImportPlan
from .staging import export_capability, stage_import
from .delta import (
    DeltaSlice, DisposableDeltaCandidate, ReceiverTensor, ScreenedDeltaCandidate,
    apply_plastic_delta, encode_plastic_delta, screen_delta_candidate,
    receiver_parameter_schema_digest, receiver_weight_digest,
)
from .adoption import PackageImportOutcome, adopt_screened_delta

__all__ = [
    'PackageArtifact', 'PackageBinding', 'PackageKind', 'SourceRights',
    'CognitivePackage', 'ExportSnapshot', 'ImportPlan', 'export_capability', 'stage_import',
    'DeltaSlice', 'DisposableDeltaCandidate', 'ReceiverTensor', 'ScreenedDeltaCandidate',
    'apply_plastic_delta', 'encode_plastic_delta', 'screen_delta_candidate',
    'receiver_parameter_schema_digest', 'receiver_weight_digest',
    'PackageImportOutcome', 'adopt_screened_delta',
]
