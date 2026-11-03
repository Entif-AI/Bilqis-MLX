"""Literal compatibility witnesses derived from the pre-extraction public owners."""
from dataclasses import dataclass
import importlib
import inspect
import json
from pathlib import Path
import unittest


class PublicModuleIdentityTests(unittest.TestCase):
    def test_original_declared_callables_keep_public_module(self):
        fixture = json.loads(Path(__file__).with_name('public_callables.json').read_text())
        for case in fixture['callables']:
            with self.subTest(case=case):
                module = importlib.import_module(case['module'])
                cls = getattr(module, case['class'])
                member = vars(cls)[case['member']]
                function = member if case['accessor'] == 'function' else getattr(member, case['accessor'])
                self.assertEqual(function.__module__, case['module'])

    def test_generated_record_methods_keep_public_module(self):
        from bilqis_mlx.semantics.frame_schema import FrameSchema
        for name in ('__init__', '__repr__', '__eq__', '__hash__', '__setattr__', '__delattr__'):
            with self.subTest(name=name):
                self.assertEqual(vars(FrameSchema)[name].__module__,
                                 'bilqis_mlx.semantics.frame_schema')

    def test_serialized_method_uses_the_original_public_global(self):
        import pickle
        import pickletools
        from bilqis_mlx.semantics.frame_schema import FrameSchema
        payload = pickle.dumps(FrameSchema.canonical_bytes, protocol=4)
        names = [argument for opcode, argument, _ in pickletools.genops(payload)
                 if opcode.name in ('SHORT_BINUNICODE', 'BINUNICODE')]
        self.assertEqual(names, ['bilqis_mlx.semantics.frame_schema',
                                 'FrameSchema.canonical_bytes'])
        self.assertIs(pickle.loads(payload), FrameSchema.canonical_bytes)

    def test_descriptors_change_without_mutating_external_or_inherited_functions(self):
        from bilqis_mlx.semantics._public_identity.module_identity import restore_public_module
        external = json.dumps

        class Parent:
            def inherited(self):
                return 'parent'

        class Contract(Parent):
            foreign = staticmethod(external)

            @property
            def value(self):
                return 7

            @classmethod
            def create(cls):
                return cls()

            @staticmethod
            def constant():
                return 11

        inherited_module = Parent.inherited.__module__
        getter = Contract.value.fget
        def foreign_collision():
            return 'foreign'
        foreign_collision.__module__ = 'external.contracts'
        foreign_collision.__qualname__ = Contract.__qualname__ + '.collision'
        Contract.collision = staticmethod(foreign_collision)
        self.assertIs(restore_public_module(Contract, 'public.contract'), Contract)
        self.assertIs(Contract.value.fget, getter)
        self.assertEqual(getter.__module__, 'public.contract')
        self.assertEqual(Contract.create.__func__.__module__, 'public.contract')
        self.assertEqual(Contract.constant.__module__, 'public.contract')
        self.assertEqual(Contract().value, 7)
        self.assertEqual(Contract.constant(), 11)
        self.assertIs(Contract.foreign, external)
        self.assertEqual(external.__module__, 'json')
        self.assertEqual(foreign_collision.__module__, 'external.contracts')
        self.assertEqual(Parent.inherited.__module__, inherited_module)

    def test_wrapped_generated_methods_keep_identity_signature_and_behavior(self):
        from bilqis_mlx.semantics._public_identity.module_identity import restore_public_module

        @dataclass(frozen=True)
        class Contract:
            value: int

        original = Contract.__repr__
        signature = inspect.signature(Contract)
        restore_public_module(Contract, 'public.record')
        self.assertIs(Contract.__repr__, original)
        self.assertEqual(original.__module__, 'public.record')
        self.assertEqual(original.__wrapped__.__module__, 'public.record')
        self.assertEqual(inspect.signature(Contract), signature)
        self.assertEqual(Contract(3).value, 3)

    def test_function_export_retains_its_object_signature_and_docstring(self):
        from bilqis_mlx.semantics._public_identity.module_identity import restore_public_module

        def public(value: int) -> int:
            """Return the supplied value."""
            return value

        signature = inspect.signature(public)
        self.assertIs(restore_public_module(public, 'public.functions'), public)
        self.assertEqual(public.__module__, 'public.functions')
        self.assertEqual(inspect.signature(public), signature)
        self.assertEqual(public.__doc__, 'Return the supplied value.')
        self.assertEqual(public(9), 9)
