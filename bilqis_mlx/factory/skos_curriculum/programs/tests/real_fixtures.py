"""Pinned A01 and genuine source providers; disposable formal operand grants."""
import json
import os

from bilqis_mlx.factory.live_releases import boolean_successor
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.paths import REPO_ROOT, LEGACY_SOURCE
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.factory.tests.curriculum.formal_lesson_fixtures import _case

ARTIFACT = os.environ.get("BILQIS_A01_ATLAS_BUNDLE", "")


def selection():
    return AtlasArtifactSelection(
        ARTIFACT, "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
        "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306",
        "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec")


def full_boolean_release():
    path = REPO_ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"
    course = boolean_successor(accepted_grade_a(json.loads(path.read_text())), LEGACY_SOURCE)
    registry = live_source_registry()
    return compile_factory_release(course, registry), registry


def formal_case(operator, *values):
    return _case(operator, *values, release=selection().release_sha256)


def numeric_factory_release():
    from bilqis_mlx.live_grade_c import REGISTRY_COUNTING_TARGET
    from bilqis_mlx.factory.live_releases import (
        boolean_composite_successor, boolean_identification_successor, numeric_successor,
    )
    release, registry = full_boolean_release()
    composite = boolean_composite_successor(release.course, LEGACY_SOURCE)
    identified = boolean_identification_successor(composite, LEGACY_SOURCE)
    course, _ = numeric_successor(identified, maximum=REGISTRY_COUNTING_TARGET)
    return compile_factory_release(course, registry), registry
