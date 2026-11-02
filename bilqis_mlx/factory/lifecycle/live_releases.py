"""Deprecated import shim for historical live-release compatibility.

Current executable authority is CurriculumProfile -> ExecutionPlan ->
ExecutableFactoryRelease. Historical callers may continue importing this path
while they migrate; implementation lives under bilqis_mlx.compatibility.
"""
from ..compatibility.live_releases import *  # noqa: F401,F403
