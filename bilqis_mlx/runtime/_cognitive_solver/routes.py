"""C04.1 ordered exact, cached, neural and deterministic fallback routes."""
from __future__ import annotations
from .execution import _public


_CONTINUE = object()


def exact(session):
    exact = session.evaluate(session.task)
    if exact.answer.state is _public().ValueState.VALUE:
        return session.result(exact.answer, _public().RouteKind.EXACT, 0)
    session.unresolved_answer = exact.answer
    session.unresolved_signature = (
        exact.receipt.unresolved_signature or "UNRESOLVED")
    return _CONTINUE


def cached(session):
    for cached in session.ordered_cache:
        if not session.qualified(cached):
            continue
        try:
            solved = session.evaluate(cached.goal)
        except _public().BilqisError:
            session.fallback_reason = "BAMF_C04_CACHED_DAG_REJECTED"
            continue
        if solved.answer.state is _public().ValueState.VALUE:
            return session.result(
                solved.answer, _public().RouteKind.CACHED_COMPOSITION, 0)
    return _CONTINUE


def neural(session):
    if session.context.neural_proposer is None or session.budget.max_neural_calls == 0:
        return _CONTINUE
    request = _public().NeuralRequest(
        session.task.goal_id, session.unresolved_signature,
        session.source_digest, session.generation.generation_digest,
        session.task.allowed_operator_ids)
    session.neural_calls = 1
    neural, session.fallback_reason = session.execute_proposal(
        session.decode(session.context.neural_proposer, request), request)
    if neural is not None and neural.answer.state is _public().ValueState.VALUE:
        return session.result(
            neural.answer, _public().RouteKind.NEURAL_COMPOSITION, session.neural_calls)
    if neural is not None:
        session.unresolved_answer = neural.answer
    if session.context.local_refiner is not None:
        for attempt in range(1, session.budget.max_local_refinements + 1):
            session.local_refinement_calls += 1
            refined, reason = session.execute_proposal(
                session.decode(session.context.local_refiner, request, attempt), request)
            if refined is not None:
                session.unresolved_answer = refined.answer
            if refined is not None and (
                    refined.answer.state is _public().ValueState.VALUE):
                session.fallback_reason = None
                return session.result(
                    refined.answer, _public().RouteKind.NEURAL_COMPOSITION,
                    session.neural_calls)
            session.fallback_reason = reason
    return _CONTINUE


def fallback(session):
    cached = session.context.deterministic_fallback
    if cached is None or not session.qualified(cached):
        return _CONTINUE
    try:
        fallback = session.evaluate(cached.goal)
    except _public().BilqisError:
        session.fallback_reason = "BAMF_C04_FALLBACK_DAG_REJECTED"
        return _CONTINUE
    if fallback.answer.state is _public().ValueState.VALUE:
        return session.result(
            fallback.answer, _public().RouteKind.DETERMINISTIC_FALLBACK,
            session.neural_calls)
    return _CONTINUE
