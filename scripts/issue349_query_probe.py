"""Read-only, fixed-world query-swap probe for the issue349 event experiment."""
import argparse
import hashlib
import json
from pathlib import Path

from bilqis_mlx.source_adapters import event_frames as frames, event_pairs
from bilqis_mlx.vocabulary_growth import digest


def query_pair_scores(pairs, predictions):
    return dict(opposite_query_pairs=len(pairs),
        both_queries_correct=sum(all(predictions[r['id']] == r['gold'] for r in pair)
                                 for pair in pairs),
        predictions_flip=sum(predictions[a['id']] != predictions[b['id']] for a, b in pairs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--panel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import mlx.core as mx
    from bilqis_mlx.runtime.session import operator_lock
    from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle
    from bilqis_mlx.learning.student_ops import _predictions
    from bilqis_mlx.runtime.experiment_runs import ExperimentRunBudget

    run = args.run_dir.resolve(strict=True)
    ExperimentRunBudget(run.parent).register(run)
    panel_bytes = args.panel.read_bytes()
    panel = json.loads(panel_bytes)
    frames.source_senses()
    mx.set_default_device(mx.gpu)
    with operator_lock(run):
        saved = json.loads((run / 'state.json').read_text())
        params, _, _, graph = load_semantically_bound_bundle(run / saved['model_bundle'])
        ids = {symbol: index for index, symbol in enumerate(graph['tokens'])}
        scores = {}
        for cap, worlds in panel['worlds'].items():
            rows, pairs = [], []
            for events in worlds:
                pair = []
                for event in events:
                    record = dict(task=frames.DIALECT, capability=cap, events=events, query=event[0])
                    identity = digest(record)
                    row = dict(id=identity, source_id=identity, capability=cap, record=record,
                        answer_kind='binary', gold=frames.independent_answer(record),
                        tokens=[ids[s] for s in frames.encode(record)], root=frames.SYMBOLS[cap],
                        generator=event_pairs.GENERATOR, oracle=frames.ORACLE,
                        source_sense_id=frames.SPECS[cap][0])
                    if not event_pairs.check(row, graph=graph):
                        raise ValueError('Query probe row failed its source check')
                    pair.append(row)
                rows.extend(pair)
                if pair[0]['gold'] != pair[1]['gold']:
                    pairs.append(pair)
            predictions = _predictions(mx, params, rows, saved['config'], saved['answer_ids'])
            scores[cap] = dict(correct=sum(predictions[r['id']] == r['gold'] for r in rows),
                               total=len(rows), **query_pair_scores(pairs, predictions))
        result = dict(checkpoint=saved['school']['current_student'], scores=scores,
                      panel_sha256=hashlib.sha256(panel_bytes).hexdigest(),
                      training_exposure_overlap='NOT_MEASURED')
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
