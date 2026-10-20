"""Candidate-only post-Boolean research staircase; never an admission path."""
from ..factory.development import (DevelopmentalStaircase, DevelopmentalTarget, RepresentationLayer, UnderstandingProjection)


def post_boolean_staircase() -> DevelopmentalStaircase:
    """Candidate developmental DAG beginning after compositional Boolean identity.

    The sequence keeps semantic identity, structural composition, and surface
    realization distinct.  Branches open only where the semantic novelty can be
    isolated without forcing morphology to carry unresolved reasoning burdens.
    """
    S = RepresentationLayer
    P = UnderstandingProjection
    targets = (
        DevelopmentalTarget(
            "DEV.LAW_SCHEMA", 1, "Law identity and metavariable schema",
            ("B.IDBOOLOPS", "B.COMPOSITE"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("independent formal-law source with law identity and rewrite oracle",),
            "Recognize one invariant transformation across renamed symbols and "
            "instantiate it over unseen expressions."),
        DevelopmentalTarget(
            "DEV.TYPE_DISCIPLINE", 2, "Typed argument discipline",
            ("DEV.LAW_SCHEMA",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.DISCRIMINATE, P.TRANSFER, P.COMPOSE, P.COUNTERFACTUAL),
            ("typed source signatures with independently checkable legal and illegal applications",),
            "Treat argument/result categories as semantic constraints rather than "
            "surface labels."),
        DevelopmentalTarget(
            "DEV.ORDERED_ROLES", 3, "Ordered argument roles",
            ("DEV.TYPE_DISCIPLINE",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source relation whose argument permutation can change denotation",),
            "Bind values to stable semantic roles instead of treating inputs as an "
            "unordered bag."),
        DevelopmentalTarget(
            "DEV.SCOPE", 4, "Hierarchy and scope",
            ("DEV.ORDERED_ROLES", "DEV.LAW_SCHEMA"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.COMPOSE, P.INVERT,
             P.COUNTERFACTUAL),
            ("source-grounded nested expressions with contrastive attachment or scope",),
            "Recover and manipulate hierarchical attachment when token inventory is "
            "held constant."),
        DevelopmentalTarget(
            "DEV.FEATURE_DIMENSION", 4, "Orthogonal feature dimension",
            ("DEV.TYPE_DISCIPLINE",),
            (S.SEMANTIC_IDENTITY,),
            (P.DISCRIMINATE, P.TRANSFER, P.COUNTERFACTUAL),
            ("finite source-declared category with mutually exclusive values",),
            "Learn category/value identity independently from lexical or surface form."),
        DevelopmentalTarget(
            "DEV.FEATURE_BUNDLE", 5, "Productive feature bundles",
            ("DEV.FEATURE_DIMENSION",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.TRANSFER, P.COMPOSE, P.INVERT, P.COUNTERFACTUAL),
            ("two or more independently attested feature dimensions with held-out legal combinations",),
            "Compose known dimensions into unseen combinations without memorizing "
            "whole bundles."),
        DevelopmentalTarget(
            "DEV.RELATION_FRAME", 5, "Relational and event frames",
            ("DEV.ORDERED_ROLES",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-grounded n-ary relation or event-role inventory",),
            "Generalize ordered roles into reusable participant frames."),
        DevelopmentalTarget(
            "DEV.REALIZATION", 6, "Semantic identity to surface realization",
            ("DEV.FEATURE_BUNDLE",),
            (S.SEMANTIC_IDENTITY, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested mapping from underlying feature identity to surface exponent",),
            "Keep what a feature means distinct from how that feature is realized."),
        DevelopmentalTarget(
            "DEV.ALLOMORPHY", 7, "Context-conditioned realization",
            ("DEV.REALIZATION",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested underlying identity, conditioning context, and alternate surface forms",),
            "Predict a surface alternant from context without changing the underlying "
            "semantic identity."),
        DevelopmentalTarget(
            "DEV.ROLE_BINDING", 7, "Overt role binding",
            ("DEV.RELATION_FRAME", "DEV.REALIZATION"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested role marking whose interpretation is separable from linear order",),
            "Map semantic participant roles to overt structure while resisting "
            "position-only heuristics."),
        DevelopmentalTarget(
            "DEV.MULTIFEATURE_COMPOSITION", 8, "Reversible multi-feature composition",
            ("DEV.ALLOMORPHY", "DEV.SCOPE", "DEV.FEATURE_BUNDLE"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.TRANSFER, P.COMPOSE, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested multi-component forms with recoverable component contributions",),
            "Generate and parse unseen combinations while preserving scope and "
            "context-conditioned realization."),
        DevelopmentalTarget(
            "DEV.COUNTERFACTUAL_EXPLANATION", 9,
            "Counterfactual rule transfer and structured explanation",
            ("DEV.MULTIFEATURE_COMPOSITION", "DEV.ROLE_BINDING", "DEV.LAW_SCHEMA"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.TRANSFER, P.COUNTERFACTUAL, P.EXPLAIN),
            ("source rules with perturbable conditions plus an inspectable causal derivation trace",),
            "Predict the consequence of one changed rule or feature and emit the "
            "rule/binding/result trace that explains it."),
    )
    return DevelopmentalStaircase(
        version="bilqis.mlx.post-boolean-development/v1",
        baseline_capabilities=("B.IDBOOLOPS", "B.COMPOSITE"),
        targets=targets,
    )
