"""Replayable source selections, not semantic or neural admission tokens."""
from dataclasses import dataclass
from pathlib import Path

from ...semantics.atlas_snapshot import AtlasArtifactSelection


@dataclass(frozen=True)
class SourceAtomRow:
    selection: AtlasArtifactSelection
    source_row: dict
    graph: dict
    source_root: Path
    source_seed: int
    source_each: int
    course: object = None
    source_profile_parameters: dict | None = None

    def replay_arguments(self) -> dict:
        return dict(
            source_root=self.source_root, source_seed=self.source_seed,
            source_each=self.source_each, course=self.course,
            source_profile_parameters=self.source_profile_parameters)
