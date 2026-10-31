"""Repository and historical source locations for operator commands."""
from bilqis_mlx.compatibility.operator_cli.defaults import grade_a_manifest_path
from bilqis_mlx.source import AUDITED_PARENT
from bilqis_mlx.paths import REPO_ROOT, LEGACY_SOURCE, LEGACY_CHECKPOINTS, active_run_dir

ROOT = REPO_ROOT
DEFAULT_RUN = active_run_dir()
GRADE_A_MANIFEST = grade_a_manifest_path()
LEGACY_ROOT = LEGACY_SOURCE
ORIGINAL_CHECKPOINT = LEGACY_CHECKPOINTS / AUDITED_PARENT.basename
