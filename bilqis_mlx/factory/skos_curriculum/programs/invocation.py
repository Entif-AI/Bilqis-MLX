"""Source-specific invocation under an existing verified Factory binding."""
from inspect import signature

from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from ..common import _fail
from .contracts import SourceFamilyBatch


def _atlas_identity(selection):
    if type(selection) is not AtlasArtifactSelection:
        _fail("BAMF_FAMILY_PROGRAM_ATLAS_INVALID")
    return selection.bundle_id, selection.release_sha256, selection.source_bundle_id


def _arguments(function, args, kwargs):
    try:
        return signature(function).bind(*args, **kwargs).arguments
    except TypeError as exc:
        _fail("BAMF_FAMILY_PROGRAM_ARGUMENTS_INVALID")


def invoke_formal(registration, binding, source, atlas,
                  construct_args, construct_kwargs, check_args, check_kwargs):
    """Bind a pinned ABI symbol to the release's declared examined roots."""
    parameters = _arguments(registration.construct, construct_args, construct_kwargs)
    if _atlas_identity(parameters.get("atlas")) != _atlas_identity(atlas):
        _fail("BAMF_FAMILY_PROGRAM_ATLAS_DRIFT")
    snapshot = load_pinned_atlas_snapshot(atlas)
    allowed = {entry.semantic_id for entry in snapshot.abi_entries
               if entry.active and entry.symbol in binding.semantic_roots}
    if parameters.get("semantic_id") not in allowed:
        _fail("BAMF_FAMILY_PROGRAM_SEMANTIC_BINDING_DRIFT")
    artifact = registration.construct(*construct_args, **construct_kwargs)
    checked_parameters = _arguments(registration.check, (artifact, *check_args), check_kwargs)
    if _atlas_identity(checked_parameters.get("atlas")) != _atlas_identity(atlas):
        _fail("BAMF_FAMILY_PROGRAM_ATLAS_DRIFT")
    if registration.check(artifact, *check_args, **check_kwargs) is not True:
        _fail("BAMF_FAMILY_PROGRAM_CHECK_FAILED")
    return artifact


def _source_arguments(kwargs, binding):
    result = dict(kwargs)
    expected = {"generator_id": binding.generator_id, "oracle_id": binding.oracle_id,
                "capability": binding.capability_id}
    for name, value in expected.items():
        if name in result and result.pop(name) != value:
            _fail("BAMF_FAMILY_PROGRAM_SOURCE_ARGUMENT_DRIFT")
    return result


def invoke_source_batch(registration, binding, source, atlas,
                        construct_args, construct_kwargs, check_args, check_kwargs):
    """Keep native source identity separate from the Factory capability label."""
    if not registration.native_capability_id:
        _fail("BAMF_FAMILY_PROGRAM_NATIVE_SOURCE_SCOPE_MISSING")
    kwargs = _source_arguments(construct_kwargs, binding)
    kwargs["capability"] = registration.native_capability_id
    rows = registration.construct(source, *construct_args, **kwargs)
    if type(rows) is not tuple or not rows or any(type(row) is not dict for row in rows):
        _fail("BAMF_FAMILY_PROGRAM_SOURCE_BATCH_INVALID")
    artifact = SourceFamilyBatch(
        binding.capability_id, binding.source_adapter_id,
        registration.native_capability_id, binding.generator_id, binding.oracle_id, rows)
    kwargs = _source_arguments(check_kwargs, binding)
    if registration.check(source, artifact, *check_args,
                          capability_id=binding.capability_id, **kwargs) is not True:
        _fail("BAMF_FAMILY_PROGRAM_CHECK_FAILED")
    return artifact
