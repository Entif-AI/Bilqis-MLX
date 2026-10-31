"""Target-free structural feedback and active tied semantic identity."""
from dataclasses import asdict
import hashlib
import math
import numpy as np
import mlx.core as mx
from lib.ithkuil.src.skos.publication import json_bytes
from bilqis_mlx.learning.frame_embeddings.composition import _factor_vector
from bilqis_mlx.learning.frame_embeddings.common import FactorGate, POSITION_BASE
from bilqis_mlx.semantics.atlas_features import _factor_overflow
from bilqis_mlx.semantics.frame_schema import ConceptRef, RoleOccurrence
from ..control import ControlAction
from ..records import RoleCandidate, invalid
from ..output_sources import require_active_value


def encode_value(value, semantics, plan, parameters):
    if type(value) is ConceptRef:
        require_active_value(plan.snapshot,value)
        index,row=divmod(value.abi_index,8192)
        if index>=len(semantics.banks) or row not in semantics.banks[index].active_rows:
            invalid()
        return semantics.banks[index].weights[row]
    tags={ControlAction:'CONTROL',RoleCandidate:'ROLE',RoleOccurrence:'BINDING',str:'LITERAL_STRING'}
    if type(value) not in tags:
        invalid()
    data=(value.value if type(value) is ControlAction else asdict(value)
          if type(value) in (RoleCandidate,RoleOccurrence) else value)
    encoded=json_bytes({'type':tags[type(value)],'value':data})
    raw=b''.join(hashlib.sha256(b'bamf.decoder.value/v1|'+encoded+b'|'+str(i).encode()).digest()
                 for i in range(3))
    bits=np.unpackbits(np.frombuffer(raw,dtype=np.uint8),bitorder='big').astype(np.float32)
    return mx.array((bits*2-1)/math.sqrt(768),dtype=mx.float32)


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
