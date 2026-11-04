"""FactoryRelease v2: one immutable executable curriculum authority."""
from .admission import admit_executable_factory_release, answer_heads_from_executable_release
from .common import SCHEMA, _digest
from .compile import compile_executable_factory_release, compile_successor_profile_release
from .records import (
    AnswerHeadBinding, CapabilityVerificationReceipt, ExecutableAdmissionReceipt,
    ExecutableVerificationReceipt, VerifiedAssessmentSeal,
)
from .release import ExecutableFactoryRelease

__all__ = (
    "AnswerHeadBinding", "CapabilityVerificationReceipt", "ExecutableAdmissionReceipt",
    "ExecutableFactoryRelease", "ExecutableVerificationReceipt", "VerifiedAssessmentSeal",
    "admit_executable_factory_release", "answer_heads_from_executable_release",
    "compile_executable_factory_release", "compile_successor_profile_release", "SCHEMA", "_digest",
)
