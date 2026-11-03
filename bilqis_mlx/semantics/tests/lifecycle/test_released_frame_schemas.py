"""A03.4 released schema bodies must be checked against a pinned source artifact.

Focused tests now live beside the released-schema module boundaries.
"""
from bilqis_mlx.semantics.tests.released_schemas.fixtures import (
    RELEASE, _snapshot, _schema, _release,
)
