"""Behavior and compatibility witnesses for semantic import-boundary repair."""
import pickle
import unittest

from bilqis_mlx.semantics.source_numeric_decode import decode as frame_decode
from bilqis_mlx.source_adapters.numeric import decode as source_decode, encode
from bilqis_mlx.semantics.numeric import calculate, number
from bilqis_mlx.semantics.source_structure import inspect_source_query as frame_inspect
from bilqis_mlx.source_adapters.structure import SourceExpressionShape, inspect_source_query


class BoundaryParityTests(unittest.TestCase):
    def test_frozen_source_numeric_codec_matches_frame_decoder(self):
        expressions = [number(n) for n in range(4)]
        expressions += [calculate(op, number(3), number(2))
                        for op in ("ADD", "SUB", "MUL")]
        expressions.append(calculate("DIV", number(4), number(2)))
        for expression in expressions:
            with self.subTest(expression=expression):
                symbols = encode(expression)
                self.assertEqual(frame_decode(symbols), source_decode(symbols))
        for symbols in ([], ["bad"], ["school.syntax.math", "school.op.BAD", "syntax.end"],
                        ["school.syntax.math", "school.number.00", "syntax.end"],
                        ["school.syntax.math", "school.number.1"]):
            with self.subTest(symbols=symbols):
                with self.assertRaises(ValueError) as source_error:
                    source_decode(symbols)
                with self.assertRaises(ValueError) as frame_error:
                    frame_decode(symbols)
                self.assertEqual(str(frame_error.exception), str(source_error.exception))

    def test_structure_shape_source_identity_and_pickle(self):
        query = {"kind": "compare", "operator": "EQ", "args": [
            {"kind": "literal"}, {"kind": "literal"}]}
        shape = inspect_source_query(query)
        self.assertIs(inspect_source_query, frame_inspect)
        self.assertIs(type(shape), SourceExpressionShape)
        self.assertEqual(pickle.loads(pickle.dumps(shape)), shape)
        self.assertEqual(shape, frame_inspect(query))
