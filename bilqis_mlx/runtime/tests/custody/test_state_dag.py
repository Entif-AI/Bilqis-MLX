"""Mirrored state-DAG tests split by production ownership."""
from bilqis_mlx.runtime.tests.custody.state_dag.test_fields import StateDagFieldTests as _FieldTests
from bilqis_mlx.runtime.tests.custody.state_dag.test_migration import StateDagMigrationTests as _MigrationTests
from bilqis_mlx.runtime.tests.custody.state_dag.test_persistence import StateDagPersistenceTests as _PersistenceTests


class StateDagFieldTests(_FieldTests):
    pass


class StateDagMigrationTests(_MigrationTests):
    pass


class StateDagPersistenceTests(_PersistenceTests):
    pass
