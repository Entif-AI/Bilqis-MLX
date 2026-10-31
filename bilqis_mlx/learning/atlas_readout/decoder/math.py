"""One shared bounded attention decoder; hidden prefix is computed upstream."""
from dataclasses import dataclass
import mlx.core as mx
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.learning.frame_embeddings.composition import _validate_feature_parameters
from ..records import invalid
from .feedback import encode_value, occurrence_vector, role_vector


@dataclass(frozen=True)
class PreparedMemory:
    keys: mx.array
    values: mx.array


def validate_parameters(parameters,semantics):
    _validate_feature_parameters(parameters,semantics.features,semantics.extents)
    expected={p.name:p.shape for p in expected_bamf_shapes(ModelTopologySpecV2(),semantics.extents)
              if p.name.startswith('readout.')}
    if {name for name in parameters if name.startswith('readout.')}!=set(expected):
        invalid()
    for name,shape in expected.items():
        value=parameters[name]
        if (not isinstance(value,mx.array) or value.shape!=shape or value.dtype!=mx.float32
                or not bool(mx.all(mx.isfinite(value)))):
            invalid()


def prepare_memory(memory,parameters,semantics):
    validate_parameters(parameters,semantics)
    hidden=memory.hidden[:len(memory.compiled.positions)]
    return PreparedMemory(hidden@parameters['readout.key'].T,
                          hidden@parameters['readout.value'].T)


def _norm(value,gamma):
    return value*mx.rsqrt(mx.mean(value*value)+ModelTopologySpecV2.rms_norm_epsilon)*gamma


def decision_state(memory,decision,parents,semantics,plan,parameters,prepared):
    feedback=(mx.mean(mx.stack(tuple(encode_value(v,semantics,plan,parameters) for v in parents)),axis=0)
              if parents else mx.zeros((768,),dtype=mx.float32))
    anchor=dict(memory.anchors).get(decision.decision_id,len(memory.compiled.positions)-1)
    state=_norm(memory.hidden[anchor]+role_vector(decision,semantics,parameters)
                +occurrence_vector(decision.occurrence)+feedback@parameters['readout.feedback'].T,
                parameters['readout.state_norm'])
    query=state@parameters['readout.query'].T
    weights=mx.softmax((query@prepared.keys.T)/(192**.5),axis=-1)
    attended=(weights@prepared.values)@parameters['readout.output'].T
    return _norm(state+attended,parameters['readout.output_norm'])
