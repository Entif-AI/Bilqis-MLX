"""Operator error and operational-term explanations."""
from __future__ import annotations


def _explain_code(code: str) -> int:
    from bilqis_mlx.operator_vocabulary import BY_OPERATIONAL_CODE
    term = BY_OPERATIONAL_CODE.get(code)
    if term is not None:
        print("OPERATIONAL TERM: " + term.code)
        print("KIND: " + term.kind.value)
        print("OWNER: " + term.owner)
        print("MEANING: " + term.meaning)
        print("NEURAL EFFECT: " + term.neural_effect)
        print("NEXT ACTION: " + term.next_action)
        if term.aliases:
            print("ALIASES: " + ", ".join(term.aliases))
        return 0
    from bilqis_mlx.errors import ErrorBus
    reports = ErrorBus.explain(code)
    if len(reports) > 1:
        print(
            "LEGACY ERROR AMBIGUITY: " + code + " historically collapsed " +
            str(len(reports)) + " distinct invariants.")
    for index, report in enumerate(reports):
        if index:
            print()
        for line in report.cli_lines():
            print(line)
    return 0
