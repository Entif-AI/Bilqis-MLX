"""Original Grade A command metadata for historical operator receipts."""
from ...paths import REPO_ROOT


def grade_a_manifest_path():
    return REPO_ROOT / 'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json'


def start_behavior(resume):
    return 'EXPLICIT_SAVED_STATE_RESUME' if resume else 'GRADE_A_NEW_RUN'
