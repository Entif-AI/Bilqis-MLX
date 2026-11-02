"""Training rows and hidden target isolation."""
from __future__ import annotations
from .common import (COMPILED_ROWS_SCHEMA, HIDDEN_TARGET_SCHEMA, MAX_NEURAL_POSITIONS, ROW_COMPILER_INPUT_ARITY, TRAINING_EXAMPLE_SCHEMA, _invalid, dataclass)
from .source import (FrameCompilerConfig, StreamingAST)
from .positions import (CompiledFrameBatch, CompiledPosition)
from .prefix import (compile_prefix)

@dataclass(frozen=True)
class CompiledFrameRows:
    rows: tuple[CompiledFrameBatch, ...]
    padded_positions: tuple[tuple[CompiledPosition | None, ...], ...]
    padding_mask: tuple[tuple[bool, ...], ...]
    schema_version: str = COMPILED_ROWS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.rows, tuple)
                or any(not isinstance(row, CompiledFrameBatch)
                       for row in self.rows)
                or not isinstance(self.padded_positions, tuple)
                or not isinstance(self.padding_mask, tuple)
                or len(self.rows) != len(self.padded_positions)
                or len(self.rows) != len(self.padding_mask)
                or self.schema_version != COMPILED_ROWS_SCHEMA):
            _invalid("BAMF_PREFIX_ROWS_INVALID")
        width = max((len(row.positions) for row in self.rows), default=0)
        for row, padded, mask in zip(
                self.rows, self.padded_positions, self.padding_mask):
            if (not isinstance(padded, tuple)
                    or not isinstance(mask, tuple)
                    or len(padded) != width or len(mask) != width
                    or padded[:len(row.positions)] != row.positions
                    or padded[len(row.positions):]
                    != (None,) * (width - len(row.positions))
                    or mask != (
                        (True,) * len(row.positions)
                        + (False,) * (width - len(row.positions)))):
                _invalid("BAMF_PREFIX_ROWS_PADDING_INVALID")


@dataclass(frozen=True)
class HiddenAnswerTargets:
    """Teacher-only target indices, never a member of CompiledFrameBatch."""
    source_instance_id: str
    target_indices: tuple[int, ...]
    target_mask: tuple[bool, ...]
    schema_version: str = HIDDEN_TARGET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.target_indices, tuple)
                or len(self.target_indices) > MAX_NEURAL_POSITIONS
                or any(type(item) is not int or item < 0
                       for item in self.target_indices)
                or not isinstance(self.target_mask, tuple)
                or any(type(item) is not bool for item in self.target_mask)
                or len(self.target_indices) != len(self.target_mask)
                or self.schema_version != HIDDEN_TARGET_SCHEMA):
            _invalid("BAMF_PREFIX_TARGETS_INVALID")


@dataclass(frozen=True)
class CompiledTrainingExample:
    input_view: CompiledFrameBatch
    target_view: HiddenAnswerTargets
    schema_version: str = TRAINING_EXAMPLE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.input_view, CompiledFrameBatch)
                or not isinstance(self.target_view, HiddenAnswerTargets)
                or self.input_view.source_instance_id
                != self.target_view.source_instance_id
                or self.schema_version != TRAINING_EXAMPLE_SCHEMA):
            _invalid("BAMF_PREFIX_TRAINING_EXAMPLE_INVALID")


def compile_training_example(
    ast: StreamingAST, targets: HiddenAnswerTargets,
    visible_end: int, release: str,
    config: FrameCompilerConfig,
) -> CompiledTrainingExample:
    """Keep hidden answer tensors outside the model-input/cache contract."""
    if (not isinstance(targets, HiddenAnswerTargets)
            or targets.source_instance_id != ast.source_instance_id):
        _invalid("BAMF_PREFIX_TARGET_SOURCE_MISMATCH")
    return CompiledTrainingExample(
        compile_prefix(ast, visible_end, release, config), targets)


def compile_prefix_rows(
    rows: tuple[tuple[StreamingAST, int, FrameCompilerConfig], ...],
    release: str,
) -> CompiledFrameRows:
    """Compile each source row in isolation; padding is never source."""
    if (not isinstance(rows, tuple)
            or any(not isinstance(row, tuple)
                   or len(row) != ROW_COMPILER_INPUT_ARITY
                   for row in rows)):
        _invalid("BAMF_PREFIX_ROWS_INPUT_INVALID")
    compiled = tuple(
        compile_prefix(ast, end, release, config)
        for ast, end, config in rows)
    width = max((len(row.positions) for row in compiled), default=0)
    return CompiledFrameRows(
        compiled,
        tuple(row.positions + (None,) * (width - len(row.positions))
              for row in compiled),
        tuple((True,) * len(row.positions)
              + (False,) * (width - len(row.positions))
              for row in compiled))
