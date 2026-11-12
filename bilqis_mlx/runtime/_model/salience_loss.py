"""Present-label ordinal objectives over the exact B11 prefix query."""
from dataclasses import dataclass
import mlx.core as mx

from bilqis_mlx.learning.atlas_salience import project_salience_heads
from bilqis_mlx.learning.salience_contracts import _invalid

SALIENCE_ORDINAL_CLASS_COUNT = 5


@dataclass(frozen=True)
class SalienceLossComponents:
    impact: object
    exigency: object
    novelty: object
    heads: tuple[str, ...]

    @property
    def total(self):
        return self.impact + self.exigency + self.novelty


def salience_loss_components(parameters, hidden, topology, extents, labels):
    names = ('impact', 'exigency', 'novelty')
    if (not isinstance(labels, dict) or not set(labels) <= set(names)
            or any(type(value) is not int
                   or not 0 <= value < SALIENCE_ORDINAL_CLASS_COUNT
                   for value in labels.values())
            or tuple(hidden.shape) != (topology.width,)):
        _invalid('BAMF_SALIENCE_LOSS_LABELS_INVALID')
    zero = mx.array(0., dtype=mx.float32)
    if not labels:
        return SalienceLossComponents(zero, zero, zero, ())
    logits = project_salience_heads(parameters, hidden, topology, extents, array_api=mx)
    losses = []
    for name in names:
        if name not in labels:
            losses.append(zero)
            continue
        values = getattr(logits, name)
        losses.append(.05 * (mx.logsumexp(values) - values[labels[name]]))
    return SalienceLossComponents(*losses, tuple(name for name in names if name in labels))
