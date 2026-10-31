"""Execution of a bound family program without learner admission."""
from ..common import _fail
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from .contracts import BoundFamilyProgram, FamilyProgramRegistry

def execute_bound_family_program(
    registry: FamilyProgramRegistry,
    binding: BoundFamilyProgram,
    *,
    construct_args: tuple = (),
    construct_kwargs: dict | None = None,
    check_args: tuple = (),
    check_kwargs: dict | None = None,
    source_registry: SourceAdapterRegistry | None = None,
    atlas=None,
):
    """Execute one already-bound family program without inventing a uniform ABI."""
    if type(registry) is not FamilyProgramRegistry or type(binding) is not BoundFamilyProgram:
        _fail("BAMF_FAMILY_PROGRAM_EXECUTION_INPUT_INVALID")
    registration = registry.require(binding.family_id)
    if (registration.constructor_ref != binding.constructor_ref
            or registration.checker_ref != binding.checker_ref
            or binding.source_adapter_id not in registration.accepted_source_adapter_ids):
        _fail("BAMF_FAMILY_PROGRAM_EXECUTION_AUTHORITY_MISMATCH")
    if registration.invoke_bound is not None:
        if type(source_registry) is not SourceAdapterRegistry:
            _fail("BAMF_FAMILY_PROGRAM_SOURCE_CONTEXT_MISSING")
        source = source_registry.require(binding.generator_id, binding.oracle_id)
        if (source.descriptor.adapter_id != binding.source_adapter_id
                or source.descriptor.implementation_sha256 != binding.source_implementation_sha256):
            _fail("BAMF_FAMILY_PROGRAM_EXECUTION_PROVIDER_DRIFT")
        return registration.invoke_bound(
            registration, binding, source, atlas, construct_args,
            {} if construct_kwargs is None else dict(construct_kwargs),
            check_args, {} if check_kwargs is None else dict(check_kwargs))
    artifact = registration.construct(
        *construct_args, **({} if construct_kwargs is None else construct_kwargs))
    checked = registration.check(
        artifact, *check_args, **({} if check_kwargs is None else check_kwargs))
    if checked is not True:
        _fail("BAMF_FAMILY_PROGRAM_CHECK_FAILED")
    return artifact
