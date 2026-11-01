"""Target-free structural feedback and active tied semantic identity."""
import numpy as np
import mlx.core as mx
from bilqis_mlx.learning.frame_embeddings.composition import _factor_vector
from bilqis_mlx.learning.frame_embeddings.common import FactorGate, POSITION_BASE
from bilqis_mlx.semantics.atlas_features import _factor_overflow
from bilqis_mlx.semantics.frame_schema import ConceptRef, RoleOccurrence
from ..control import ControlAction
from ..records import RoleCandidate, invalid
from ..output_sources import require_active_value
from ..causal_training import encode_feedback_value


def encode_value(value, semantics, plan, parameters):
    if type(value) is ConceptRef:
        require_active_value(plan.snapshot,value)
    elif type(value) not in (ControlAction, RoleCandidate, RoleOccurrence, str):
        invalid()
    return encode_feedback_value(value,snapshot=plan.snapshot,banks=semantics.banks)


def occurrence_vector(occurrence):
    if type(occurrence) is not int or occurrence<0:
        invalid()
    frequencies=np.power(POSITION_BASE,-np.arange(0,768,2)/768)
    angles=occurrence*frequencies
    values=np.empty(768,dtype=np.float32)
    values[0::2],values[1::2]=np.sin(angles),np.cos(angles)
    return mx.array(values)


def role_vector(decision,semantics,parameters):
    identifier=decision.role_id if decision.role_id is not None else 'NONE'
    rows=dict(semantics.features.role_map)
    if identifier not in rows:
        invalid()
    row=rows[identifier]
    overflow=(_factor_overflow('role',identifier)
              if row==0 and identifier!='UNKNOWN' else None)
    vector=_factor_vector(parameters['features.role'],row,overflow)
    return mx.sigmoid(parameters['features.gates'][FactorGate.ROLE])*(
        vector@parameters['features.project_role'].T)
