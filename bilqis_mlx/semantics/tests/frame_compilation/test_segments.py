"""Segments compiler regressions."""
import unittest
from bilqis_mlx.semantics.tests.frame_compilation.helpers import (BilqisError, LawfulSourceSegment, PRINCIPAL, PUBLIC_FORMAL, REGION, RELEASE, SCOPE, SourceAtom, SourceGrant, SourceSpan, StreamingAST, TENANT, _case, _with_atom_grants, boundary_evidence_digest, compile_lawful_segments, replace)


class SegmentsTests(unittest.TestCase):
    def test_lawful_source_boundaries_split_without_truncation(self):
        _, config = _case()
        segments = []
        for index, (start, end) in enumerate(((0, 800), (800, 1500))):
            ast = StreamingAST(
                f"synthetic:segment:{index}",
                tuple(SourceAtom(
                    local, f"token:{global_index}",
                    f"source:token:{global_index}")
                    for local, global_index in enumerate(
                        range(start, end))), ())
            scoped = replace(
                config, approved=None,
                task=replace(
                    config.task, causal_prefix_end=end - start))
            scoped = _with_atom_grants(ast, scoped)
            segment = LawfulSourceSegment(
                "synthetic:original", SourceSpan(start, end),
                f"source:lawful-boundary:{end}", ast, scoped)
            grant = SourceGrant(
                segment.boundary_source_handle, PRINCIPAL, TENANT,
                PUBLIC_FORMAL, RELEASE, boundary_evidence_digest(segment),
                ("TRAINING",), (REGION,), (SCOPE,),
                rights_epoch=1, correction_generation=1,
                observed_at=2, effective_from=0)
            scoped = replace(
                scoped, frontier=replace(
                    scoped.frontier, grants=tuple(sorted(
                        (*scoped.frontier.grants, grant),
                        key=lambda item: item.source_handle))))
            segments.append(replace(segment, config=scoped))
        compiled = compile_lawful_segments(tuple(segments), RELEASE)
        self.assertEqual(compiled.total_source_atoms, 1500)
        self.assertEqual(compiled.total_neural_positions, 1500)
        self.assertEqual(
            tuple(len(item.positions) for item in compiled.segments),
            (800, 700))
        self.assertEqual(
            compiled.segments[0].positions[0].atom.source_reference,
            "source:token:0")
        self.assertEqual(
            compiled.segments[-1].positions[-1].atom.source_reference,
            "source:token:1499")
        with self.assertRaises(BilqisError):
            compile_lawful_segments((
                segments[0], replace(
                    segments[1], global_span=SourceSpan(801, 1501))),
                RELEASE)
        with self.assertRaises(BilqisError):
            compile_lawful_segments((
                segments[0], replace(
                    segments[1], config=replace(
                        segments[1].config, task=replace(
                            segments[1].config.task,
                            tenant_id="synthetic:other")))),
                RELEASE)
        second = segments[1]
        changed_generation = replace(
            second, config=replace(
                second.config, frontier=replace(
                    second.config.frontier, correction_generation=2,
                    grants=tuple(
                        replace(grant, correction_generation=2)
                        for grant in second.config.frontier.grants))))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments(
                (segments[0], changed_generation), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_SPLIT_BOUNDARY_INVALID")
        backdated_view = replace(
            second, config=replace(
                second.config, task=replace(
                    second.config.task, observed_frontier=4)))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments(
                (segments[0], backdated_view), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_SPLIT_BOUNDARY_INVALID")
        ungranted = replace(
            segments[0], config=replace(
                segments[0].config, frontier=replace(
                    segments[0].config.frontier,
                    grants=tuple(
                        grant for grant in segments[0].config.frontier.grants
                        if grant.source_handle
                        != segments[0].boundary_source_handle))))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments((ungranted, segments[1]), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_SPLIT_SOURCE_UNAUTHORIZED")
        overlong_ast = StreamingAST(
            "synthetic:overlong",
            tuple(SourceAtom(i, f"token:{i}", f"source:token:{i}")
                  for i in range(1025)), ())
        overlong_config = replace(
            config, approved=None,
            task=replace(config.task, causal_prefix_end=1025))
        overlong = LawfulSourceSegment(
            "synthetic:overlong-origin", SourceSpan(0, 1025),
            "source:overlong-boundary", overlong_ast, overlong_config)
        grant = SourceGrant(
            overlong.boundary_source_handle, PRINCIPAL, TENANT,
            PUBLIC_FORMAL, RELEASE, boundary_evidence_digest(overlong),
            ("TRAINING",), (REGION,), (SCOPE,),
            rights_epoch=1, correction_generation=1,
            observed_at=2, effective_from=0)
        overlong = replace(
            overlong, config=replace(
                overlong_config, frontier=replace(
                    overlong_config.frontier, grants=tuple(sorted(
                        (*overlong_config.frontier.grants, grant),
                        key=lambda item: item.source_handle)))))
        with self.assertRaises(BilqisError) as caught:
            compile_lawful_segments((overlong,), RELEASE)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
