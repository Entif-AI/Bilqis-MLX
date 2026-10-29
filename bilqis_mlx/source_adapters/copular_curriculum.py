"""The first finite Ithkuil realization, expressed as ordinary factory data.

Source compilation and native vocabulary admission precede student-bound JIT
adoption. A token proposal never grants current prerequisite evidence.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

from ..curriculum import AnswerFamily, BINARY
from ..live_grade_c import registry_graph as numeric_registry_graph
from ..semantics.foundation.copular import SYMBOL, SEMANTIC_ID
from ..source_adapters.copular import (
    CAPABILITY, GENERATOR, ORACLE, SENSE_ID, TEXT_SHA256, MEANING, registered_adapter,
)
from ..vocabulary_growth import AdmittedToken, append_catalog, digest
from ..factory.candidate_staging import candidate_source_anchor, compile_candidate_successor
from ..factory.curriculum_definition import CapabilitySpec, CapabilitySourceBinding, GradeSpec
from ..factory.execution import CurriculumProfile


VERSION = "bilqis.ithkuil-reference-identity/20261020-v1"
AUTHORITY = "https://github.com/socr8s/private-ip/issues/349"
REGISTRY_ID = "1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "semantics/copular_registry_v1.json"


def capability_definition() -> CapabilitySpec:
    return CapabilitySpec(CAPABILITY, "finite-reference-identity", (SYMBOL,), (SYMBOL,),
                          ("A.IDENTITY", "A.MAPS"), ("A.IDENTITY", "A.MAPS"),
                          (AnswerFamily("binary", BINARY),))


def token_admission() -> AdmittedToken:
    # Allocation provenance is immutable. Later verified implementation releases
    # must not retroactively change the token's birth receipt or node contract.
    contract = json.loads((REGISTRY_PATH.parent / "copular_admission_v1.json").read_text())
    if (contract.get("authority") != AUTHORITY or contract.get("version") != VERSION or
            contract.get("source_sense") != SENSE_ID or
            contract.get("source_text_sha256") != TEXT_SHA256 or
            digest(contract.get("definition")) != digest(asdict(capability_definition()))):
        raise ValueError("COPULAR_ALLOCATION_SEMANTIC_CONTRACT_DRIFT")
    proof = digest(contract)
    return AdmittedToken(
        token_id=SYMBOL, semantic_id=SEMANTIC_ID,
        meaning=MEANING + "; scoped total finite-reference-map realization; morphology not realized.",
        source_kind="new_ithkuil", representation="compositional",
        source_locator="https://ithkuil.net/New_Ithkuil_Lexicon.pdf",
        source_digest=TEXT_SHA256, lesson_digest=digest(asdict(capability_definition())),
        oracle_digest=contract["provider"]["implementation_sha256"],
        prerequisite_tokens=("micro.compare.EQ", "development.op.MAPS"),
        capability_id=CAPABILITY, admission_receipt=proof,
        signature="Entity*Entity->Boolean", arity=2)


def _registered_parent(parent):
    # Preserve the separately admitted numeric allocation at indices 222..226,
    # including when the current student has not allocated those rows yet.
    registered = numeric_registry_graph()
    n = len(parent["tokens"])
    if (n > len(registered["tokens"]) or parent["tokens"] != registered["tokens"][:n] or
            parent["nodes"] != registered["nodes"][:n] or
            any(parent["row_contract_sha256"][t] != registered["row_contract_sha256"][t]
                for t in parent["tokens"])):
        raise ValueError("COPULAR_PARENT_CATALOG_INCOMPATIBLE")
    return registered


def proposed_graph(parent):
    """Neural-inert source/Registry proposal, following the existing numeric path."""
    return append_catalog(_registered_parent(parent), (token_admission(),),
                          allow_disposable_fixtures=True)[0]


def expanded_graph(parent, evidence=None):
    if evidence is None:
        evidence = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    admission = token_admission()
    if (not isinstance(evidence, dict) or evidence.get("release") != VERSION or
            evidence.get("spreadsheet_id") != REGISTRY_ID or
            evidence.get("admission_receipts") != [admission.admission_receipt] or
            evidence.get("native_rows_sha256") != digest(evidence.get("rows"))):
        raise ValueError("COPULAR_NATIVE_REGISTRY_ADMISSION_NOT_VERIFIED")
    return append_catalog(_registered_parent(parent), (admission,),
                          canonical_registry_rows=evidence["rows"],
                          approved_ledger_version=VERSION,
                          approved_admissions=(admission.admission_receipt,))[0]


def stage_identity(frontier, current, graph, *, source_root, source_registry, answer_registry):
    matches = [c for c in frontier.candidates if c.proposed_capability_id == CAPABILITY and
               c.target_sense_id == SENSE_ID]
    if len(matches) != 1 or CAPABILITY in current.curriculum.capability_map:
        raise ValueError("COPULAR_EXACT_NEW_CANDIDATE_REQUIRED")
    candidate_id = matches[0].candidate_id
    capability = capability_definition()
    curriculum = replace(current.curriculum, grades=(*current.curriculum.grades,
        GradeSpec("D", (capability,), ((CAPABILITY, 12),), ((CAPABILITY,),))))
    bindings = replace(current.source_bindings, bindings=(*current.source_bindings.bindings,
        CapabilitySourceBinding(CAPABILITY, candidate_source_anchor(frontier, candidate_id),
                                GENERATOR, ORACLE)))
    profile = CurriculumProfile("jit/copular-identity/v1", grades=current.profile.grades)
    return compile_candidate_successor(frontier, current, candidate_id,
        curriculum=curriculum, source_bindings=bindings, profile=profile,
        source_registry=source_registry, answer_registry=answer_registry,
        source_root=source_root, graph=graph, verification_seed=2026102007)
