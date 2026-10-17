"""Independent domain-soup and hybrid candidate verification for School50 v5.

These are frozen models, never a student with inherited AdamW moments.
No soup is promoted without exact readback and independent domain exams.
"""
from __future__ import annotations

import os
from pathlib import Path
import uuid

import torch

from bilqis_logic.kernel import digest
from bilqis_ref.model import state_hash
from . import engine

VERSION = "bilqis.school50.fusion/v1"


def average(source, out, members, weights, device):
    """Verify ingredients, then perform a streaming weight-space average."""
    if len(members)!=len(weights) or not members or any(
            not isinstance(w,(float,int)) or w<=0 for w in weights):
        raise ValueError("FUSION_INVALID_INGREDIENT_WEIGHTS")
    total=float(sum(weights))
    aggregate={}
    constants={}
    base_config=base_graph=None
    for ingredient,weight in zip(members,weights):
        if ingredient["location"] not in ("source","research"):
            raise ValueError("FUSION_UNTRUSTED_LOCATION")
        path=(source["source_dir"] if ingredient["location"]=="source" else out)/ingredient["checkpoint"]
        if engine._sha(path)!=ingredient["checkpoint_sha256"]:
            raise ValueError("FUSION_INGREDIENT_HASH_DRIFT")
        model,optimizer,payload=engine.load_checkpoint(path)
        del optimizer
        graph=digest(payload["graph"])
        if base_config is None:
            base_config,base_graph=model.config,graph
        elif model.config!=base_config or graph!=base_graph:
            raise ValueError("FUSION_INCOMPATIBLE_MODEL_ABI")
        for name,tensor in model.state_dict().items():
            value=tensor.detach().cpu()
            if torch.is_floating_point(value):
                if name not in aggregate:aggregate[name]=value.float()*weight
                else:aggregate[name].add_(value.float(),alpha=weight)
            elif name in constants:
                if not torch.equal(constants[name],value):
                    raise ValueError("FUSION_NONFLOAT_STATE_CONFLICT")
            else:
                constants[name]=value.clone()
        del model,payload
    # Use the first model as the exact-state constructor; never borrow optimizer.
    first=members[0]
    location=(source["source_dir"] if first["location"]=="source" else out)
    model,optimizer,payload=engine.load_checkpoint(location/first["checkpoint"])
    del optimizer
    weights_dict={name:(value/total).to(model.state_dict()[name].dtype)
                  for name,value in aggregate.items()}
    weights_dict.update(constants)
    model.load_state_dict(weights_dict,strict=True)
    model.to(device).eval()
    for parameter in model.parameters():parameter.requires_grad_(False)
    manifest={"version":VERSION,"members":members,"weights":list(weights),
              "model_sha256":state_hash(model),"graph_sha256":base_graph}
    return model,payload["graph"],manifest


def save_frozen(out, name, model, graph, manifest):
    path=out/(name+".pt")
    temp=out/("."+name+"."+uuid.uuid4().hex+".tmp")
    torch.save({"weights":{k:v.detach().cpu() for k,v in model.state_dict().items()},
                "manifest":manifest,"graph_sha256":digest(graph)},temp)
    os.replace(temp,path)
    result={"file":path.name,"sha256":engine._sha(path),"manifest":manifest}
    content=torch.load(path,map_location="cpu",weights_only=True)
    if content["manifest"]!=manifest or content["graph_sha256"]!=digest(graph):
        raise ValueError("FUSION_FROZEN_READBACK_MISMATCH")
    return result
