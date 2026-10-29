"""A05.5 source-visible atom semantic-ABI handoff witnesses."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from unittest import TestCase, skipUnless

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasCounts, FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import (
    FrameCompilerConfig, SourceAtom, StreamingAST, atom_evidence_digest,
    compile_prefix,
)
from bilqis_mlx.semantics.source_atom_binding import (
    AtomBindingDisposition, SourceRowWitness, _resolve_visible_atoms,
    require_embedding_ready,
)
from bilqis_mlx.source_adapters.atom_binding import (
    build_source_atom_handoff, require_pinned_embedding_ready,
    revalidate_source_atom_handoff, verify_source_row,
)
from bilqis_mlx.source_adapters.copular import CAPABILITY, SYMBOL
from bilqis_mlx.source_adapters.copular_curriculum import proposed_graph
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.live_grade_c import registry_graph


ROOT = Path(__file__).resolve().parents[3]
RELEASE = "a" * 64
PRINCIPAL = "synthetic:alice"
TENANT = "synthetic:tenant"
REGION = "synthetic:region"
SCOPE = "synthetic:public"
REAL_BUNDLE = os.environ.get("BILQIS_A01_ATLAS_BUNDLE", "")


def _snapshot(tokens: tuple[str, ...]) -> FrozenAtlasSnapshot:
    entries = tuple(
        AbiEntry(index, 0, index, "semantic:" + token, token,
                 "fixture", True, True, "FIXTURE")
        for index, token in enumerate(tokens))
    counts = AtlasCounts(0, 0, 0, len(entries), 1, len(entries), 0, 0, 0, 0)
    return FrozenAtlasSnapshot(
        "bilqis.semantic-atlas-snapshot/v1", "b" * 64, RELEASE, "c" * 64,
        "d" * 64, "e" * 64, "f" * 64, "1" * 64, "2" * 64,
        "3" * 64, "4" * 64, counts, (), entries, (), (), (),
        tuple((entry.semantic_id, entry.index) for entry in entries), ())


def _case(tokens: tuple[str, ...], *, visible_end: int | None = None):
    ast = StreamingAST(
        "source:fixture-row",
        tuple(SourceAtom(index, token, "fixture:atom:" + str(index))
              for index, token in enumerate(tokens)),
        ())
    end = len(tokens) if visible_end is None else visible_end
    task = TaskScope(
        PRINCIPAL, TENANT, "TRAINING", RELEASE, REGION, SCOPE,
        observed_frontier=3, effective_time=5, causal_prefix_end=len(tokens))
    policy = ContextPolicy(
        "fixture:policy", 1, 1, ("TRAINING",), (PUBLIC_FORMAL,),
        (REGION,), (SCOPE,), (PUBLIC_FORMAL,), (), ())
    grants = tuple(sorted((SourceGrant(
        atom.source_reference, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE,
        atom_evidence_digest(ast.source_instance_id, atom, RELEASE),
        ("TRAINING",), (REGION,), (SCOPE,), 1, 1, 2, 0)
        for atom in ast.atoms), key=lambda item: item.source_handle))
    config = FrameCompilerConfig(
        (), SchemaTagMap.from_schemas(RELEASE, ()), None, task,
        SourceFrontier(1, 1, grants), policy)
    return ast, config, compile_prefix(ast, end, RELEASE, config)


def _witness(tokens: tuple[str, ...]) -> SourceRowWitness:
    return SourceRowWitness(
        "source.fixture/v1", "fixture.generator/v1", "fixture.oracle/v1",
        "fixture.capability", "fixture:sense", tuple(range(len(tokens))))


class SourceAtomBindingTests(TestCase):
    def test_candidate_is_explicitly_held_without_raw_source_reference_law(self):
        tokens = ("alpha", "beta")
        _, config, compiled = _case(tokens)
        handoff = _resolve_visible_atoms(
            compiled, config, _snapshot(tokens), _witness(tokens),
            {"tokens": list(tokens)})
        self.assertEqual(len(handoff.bindings), 2)
        first = handoff.bindings[0]
        self.assertEqual(first.candidate_abi_index, 0)
        self.assertEqual(first.candidate_semantic_id, "semantic:alpha")
        self.assertEqual(first.disposition, AtomBindingDisposition.SOURCE_HELD)
        self.assertIn("SOURCE_ATOM_REFERENCE_AUTHORITY_UNAVAILABLE", first.reason_codes)
        self.assertIn("SOURCE_ATOM_INSTANCE_AUTHORITY_UNAVAILABLE", first.reason_codes)
        self.assertIn("SOURCE_ATOM_TYPE_AUTHORITY_UNAVAILABLE", first.reason_codes)
        with self.assertRaises(BilqisError) as caught:
            require_embedding_ready(handoff, compiled, config, _snapshot(tokens),
                                    _witness(tokens), {"tokens": list(tokens)})
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_SOURCE_ATOM_BINDING_HELD")

    def test_binding_digest_is_prefix_stable_and_future_atom_is_absent(self):
        tokens = ("alpha", "beta", "gamma")
        _, config, prefix = _case(tokens, visible_end=1)
        _, _, full = _case(tokens, visible_end=3)
        snapshot, witness, graph = _snapshot(tokens), _witness(tokens), {"tokens": list(tokens)}
        early_config = replace(
            config, task=replace(config.task, causal_prefix_end=1))
        early = _resolve_visible_atoms(prefix, early_config, snapshot, witness, graph)
        later = _resolve_visible_atoms(full, config, snapshot, witness, graph)
        self.assertEqual(early.bindings[0], later.bindings[0])
        self.assertEqual(early.bindings[0].binding_digest,
                         later.bindings[0].binding_digest)
        self.assertEqual(tuple(item.atom_index for item in early.bindings), (0,))
        self.assertEqual(tuple(item.atom_index for item in later.bindings), (0, 1, 2))

    def test_wrong_token_or_row_index_never_becomes_an_abi_binding(self):
        tokens = ("alpha", "beta")
        ast, config, _ = _case(tokens)
        changed_atoms = (replace(ast.atoms[0], token="beta"), ast.atoms[1])
        changed = replace(ast, atoms=changed_atoms)
        grants = tuple(replace(
            grant,
            evidence_digest=atom_evidence_digest(changed.source_instance_id, atom, RELEASE))
            for grant, atom in zip(config.frontier.grants, changed.atoms))
        changed_config = replace(config, frontier=replace(config.frontier, grants=grants))
        compiled = compile_prefix(changed, 2, RELEASE, changed_config)
        handoff = _resolve_visible_atoms(
            compiled, changed_config, _snapshot(tokens), _witness(tokens),
            {"tokens": list(tokens)})
        self.assertEqual(handoff.bindings[0].disposition, AtomBindingDisposition.UNMAPPED)
        self.assertIn("SOURCE_ATOM_ROW_TOKEN_MISMATCH", handoff.bindings[0].reason_codes)

        shifted = SourceRowWitness(
            "source.fixture/v1", "fixture.generator/v1", "fixture.oracle/v1",
            "fixture.capability", "fixture:sense", (1, 0))
        handoff = _resolve_visible_atoms(
            compile_prefix(ast, 2, RELEASE, config), config, _snapshot(tokens),
            shifted, {"tokens": list(tokens)})
        self.assertEqual(handoff.bindings[0].disposition, AtomBindingDisposition.UNMAPPED)
        self.assertIn("SOURCE_ATOM_ROW_TOKEN_MISMATCH", handoff.bindings[0].reason_codes)

    def test_revocation_stale_correction_and_reference_change_hold_and_rekey(self):
        tokens = ("alpha",)
        ast, config, compiled = _case(tokens)
        snapshot, witness, graph = _snapshot(tokens), _witness(tokens), {"tokens": list(tokens)}
        base = _resolve_visible_atoms(compiled, config, snapshot, witness, graph).bindings[0]

        revoked_grant = replace(config.frontier.grants[0], revoked=True)
        revoked = replace(config, frontier=replace(config.frontier, grants=(revoked_grant,)))
        changed = _resolve_visible_atoms(compiled, revoked, snapshot, witness, graph).bindings[0]
        self.assertIn("SOURCE_ATOM_CURRENT_RIGHTS_HELD", changed.reason_codes)
        self.assertNotEqual(changed.binding_digest, base.binding_digest)

        stale = replace(config, frontier=replace(config.frontier, correction_generation=2))
        changed = _resolve_visible_atoms(compiled, stale, snapshot, witness, graph).bindings[0]
        self.assertIn("SOURCE_ATOM_CURRENT_RIGHTS_HELD", changed.reason_codes)
        self.assertNotEqual(changed.binding_digest, base.binding_digest)

        changed_atom = replace(ast.atoms[0], source_reference="forged:atom:0")
        changed_ast = replace(ast, atoms=(changed_atom,))
        forged_grant = replace(
            config.frontier.grants[0], source_handle=changed_atom.source_reference,
            evidence_digest=atom_evidence_digest(changed_ast.source_instance_id,
                                                 changed_atom, RELEASE))
        forged_config = replace(config, frontier=replace(config.frontier, grants=(forged_grant,)))
        forged_compiled = compile_prefix(changed_ast, 1, RELEASE, forged_config)
        changed = _resolve_visible_atoms(
            forged_compiled, forged_config, snapshot, witness, graph).bindings[0]
        self.assertEqual(changed.disposition, AtomBindingDisposition.SOURCE_HELD)
        self.assertIn("SOURCE_ATOM_REFERENCE_AUTHORITY_UNAVAILABLE", changed.reason_codes)
        self.assertNotEqual(changed.binding_digest, base.binding_digest)

    def test_forged_handoff_abi_type_release_bundle_and_duplicate_are_rejected(self):
        tokens = ("alpha", "beta")
        _, config, compiled = _case(tokens)
        snapshot, witness, graph = _snapshot(tokens), _witness(tokens), {"tokens": list(tokens)}
        handoff = _resolve_visible_atoms(compiled, config, snapshot, witness, graph)
        first = handoff.bindings[0]
        for field, value in (
                ("candidate_abi_index", 99),
                ("candidate_type_ids", ("Forged",)),
                ("semantic_release", "9" * 64),
                ("a01_bundle_id", "8" * 64)):
            with self.assertRaises(BilqisError):
                replace(first, **{field: value})
        with self.assertRaises(BilqisError):
            replace(handoff, bindings=(first, first))

    def test_unsupported_or_unreproducible_source_row_has_no_witness(self):
        row = {"generator": "missing.generator", "oracle": "missing.oracle",
               "capability": "x", "tokens": [0]}
        witness, reason = verify_source_row(
            row, {"tokens": ["alpha"]}, source_root=ROOT,
            source_seed=1, source_each=1, course=None,
            source_profile_parameters=None)
        self.assertIsNone(witness)
        self.assertEqual(reason, "SOURCE_ATOM_SOURCE_ADAPTER_UNSUPPORTED")

    @skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
    def test_real_pinned_copular_row_reaches_abi_227_but_remains_source_held(self):
        graph = proposed_graph(registry_graph())
        adapter = live_source_registry().require(
            "bilqis.ithkuil-reference-identity-constructor/v1",
            "bilqis.ithkuil-reference-identity-oracle/v1")
        row = adapter.draw(source_root=ROOT, graph=graph, course=None,
                           capability=CAPABILITY, seed=17, each=1)[0]
        symbols = tuple(graph["tokens"][index] for index in row["tokens"])
        ast, config, compiled = _case(symbols)
        release = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
        ast = replace(ast, source_instance_id=row["source_id"])
        task = replace(config.task, semantic_release=release)
        schema_map = SchemaTagMap.from_schemas(release, ())
        atoms_by_reference = {atom.source_reference: atom for atom in ast.atoms}
        grants = tuple(replace(
            grant, semantic_release=release,
            evidence_digest=atom_evidence_digest(
                ast.source_instance_id, atoms_by_reference[grant.source_handle], release))
            for grant in config.frontier.grants)
        config = replace(config, task=task, schema_map=schema_map,
                         frontier=replace(config.frontier, grants=grants))
        compiled = compile_prefix(ast, len(ast.atoms), release, config)
        selection = AtlasArtifactSelection(
            REAL_BUNDLE,
            "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
            release,
            "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec")
        handoff = build_source_atom_handoff(
            compiled, config, selection, row, graph,
            source_root=ROOT, source_seed=17, source_each=1, course=None)
        operator_offset = symbols.index(SYMBOL)
        binding = handoff.bindings[operator_offset]
        self.assertEqual(binding.candidate_abi_index, 227)
        self.assertEqual(
            binding.candidate_semantic_id,
            "ithkuil:LEXSENSE-5286ade9db42c7/finite-reference-identity/v1")
        self.assertEqual(binding.disposition, AtomBindingDisposition.SOURCE_HELD)
        self.assertIn("SOURCE_ATOM_REFERENCE_AUTHORITY_UNAVAILABLE", binding.reason_codes)
        self.assertIn("SOURCE_ATOM_INSTANCE_AUTHORITY_UNAVAILABLE", binding.reason_codes)
        self.assertIn("SOURCE_ATOM_TYPE_AUTHORITY_UNAVAILABLE", binding.reason_codes)
        self.assertFalse(handoff.embedding_ready)

        revalidate_source_atom_handoff(
            handoff, compiled, config, selection, row, graph,
            source_root=ROOT, source_seed=17, source_each=1, course=None)
        with self.assertRaises(BilqisError) as caught:
            require_pinned_embedding_ready(
                handoff, compiled, config, selection, row, graph,
                source_root=ROOT, source_seed=17, source_each=1, course=None)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_SOURCE_ATOM_BINDING_HELD")

        for changed in (
                replace(selection, release_sha256="9" * 64),
                replace(selection, bundle_id="8" * 64)):
            with self.assertRaises(BilqisError):
                build_source_atom_handoff(
                    compiled, config, changed, row, graph,
                    source_root=ROOT, source_seed=17, source_each=1, course=None)

        with self.assertRaises(BilqisError):
            replace(
                handoff, visible_end=handoff.visible_end + 1,
                bindings=(*handoff.bindings, handoff.bindings[-1]))


if __name__ == "__main__":
    import unittest
    unittest.main()
