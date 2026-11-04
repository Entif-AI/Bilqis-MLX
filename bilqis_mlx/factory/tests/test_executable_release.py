"""Compatibility fixtures for split executable-release tests."""
from ._executable_release_fixtures import (
    BaseExecutableFactoryReleaseTests as ExecutableFactoryReleaseTests,
    _answers,
    _boolean_answers,
)

__all__ = ("ExecutableFactoryReleaseTests", "_answers", "_boolean_answers")
