"""Independent Boolean verification fixture adapters."""
class SourceBooleanBackend:
    identity = "original-boolean-source-interpreter"

    def __init__(self, original, named):
        self.original = original
        self.named = named

    def invoke(self, operation, values, world_contract):
        if operation.token_index not in self.named:
            raise ValueError("BACKEND_UNKNOWN_TOKEN_INDEX")
        name = self.named[operation.token_index]
        expr = self.original.apply(
            name, *(self.original.literal(v) for v in values))
        truth = self.original.evaluate(expr, {})
        if truth != self.original.independent_evaluate(expr, {}):
            raise ValueError("BACKEND_SOURCE_DISAGREEMENT")
        return truth


class SymbolicBooleanBackend:
    identity = "sympy-symbolic-backend"

    def __init__(self, named):
        import sympy
        self.named = named
        self.functions = {
            "NOT": sympy.Not,
            "AND": sympy.And,
            "OR": sympy.Or,
            "XOR": sympy.Xor,
            "IMPLIES": sympy.Implies,
            "IFF": sympy.Equivalent,
        }

    def invoke(self, operation, values, world_contract):
        return bool(self.functions[self.named[operation.token_index]](*values))


class FaultyBooleanBackend(SymbolicBooleanBackend):
    identity = "deliberately-faulty-symbolic-backend"

    def invoke(self, operation, values, world_contract):
        return not super().invoke(operation, values, world_contract)
