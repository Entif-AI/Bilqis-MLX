"""One shared bounded attention decoder; hidden prefix is computed upstream."""
from dataclasses import dataclass
import mlx.core as mx
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.learning.frame_embeddings.composition import _validate_feature_parameters
from ..records import invalid
from .feedback import occurrence_vector, role_vector
from ..causal_training import decision_hidden
from ..parameters import bind_readout_parameters


@dataclass(frozen=True)
class PreparedMemory:
    keys: mx.array
    values: mx.array


def validate_parameters(parameters,semantics):
    _validate_feature_parameters(parameters,semantics.features,semantics.extents)
    bind_readout_parameters({name:value for name,value in parameters.items()
                             if name.startswith('readout.')},ModelTopologySpecV2(),semantics.extents)


def prepare_memory(memory,parameters,semantics):
    validate_parameters(parameters,semantics)
    hidden=memory.hidden[:len(memory.compiled.positions)]
    return PreparedMemory(hidden@parameters['readout.key'].T,
                          hidden@parameters['readout.value'].T)


def _norm(value,gamma):
    return value*mx.rsqrt(mx.mean(value*value)+ModelTopologySpecV2.rms_norm_epsilon)*gamma


def decision_state(memory,decision,state,semantics,parameters,prepared):
    anchor=dict(memory.anchors).get(decision.decision_id,len(memory.compiled.positions)-1)
    visible_anchor=(memory.hidden[anchor]+role_vector(decision,semantics,parameters)
                    +occurrence_vector(decision.occurrence))
    normalized=decision_hidden(visible_anchor,state,decision.decision_id,parameters,
                               snapshot=state.plan.snapshot,banks=semantics.banks)
    normalized=normalized*parameters['readout.state_norm']
    query=normalized@parameters['readout.query'].T
    weights=mx.softmax((query@prepared.keys.T)/(192**.5),axis=-1)
    attended=(weights@prepared.values)@parameters['readout.output'].T
    return _norm(normalized+attended,parameters['readout.output_norm'])
