#!/usr/bin/env python3
"""Disposable C05 profile splitting source-start host graph construction."""
from __future__ import annotations

import json
import time
from unittest.mock import patch

import bilqis_mlx.learning.source_atoms.backbone as backbone
import bilqis_mlx.learning.source_atoms.encoding as encoding
import bilqis_mlx.runtime.factory_evaluation_batching as batching
from bilqis_mlx.runtime.tests.capability.factory.retention import (
    retention_throughput_profile as profile,
)


def main() -> int:
    original_source_vectors = encoding.source_atom_vectors
    original_encode_frames = encoding.encode_frames
    original_start_encoded = backbone._start_encoded_source_backbone_producer
    original_start = batching.start_source_backbone_producer

    source_vector_seconds: list[float] = []
    frame_encode_seconds: list[float] = []
    producer_build_seconds: list[float] = []
    source_start_seconds: list[float] = []

    def timed_source_vectors(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_source_vectors(*args, **kwargs)
        finally:
            source_vector_seconds.append(time.perf_counter() - started)

    def timed_encode_frames(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_encode_frames(*args, **kwargs)
        finally:
            frame_encode_seconds.append(time.perf_counter() - started)

    def timed_start_encoded(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_start_encoded(*args, **kwargs)
        finally:
            producer_build_seconds.append(time.perf_counter() - started)

    def timed_start(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_start(*args, **kwargs)
        finally:
            source_start_seconds.append(time.perf_counter() - started)

    start_globals = original_start.__globals__
    encode_globals = encoding.encode_source_compiled_with_handoffs.__globals__
    with patch.dict(
            start_globals,
            {
                "encode_source_compiled_with_handoffs":
                    encoding.encode_source_compiled_with_handoffs,
                "_start_encoded_source_backbone_producer": timed_start_encoded,
            }), patch.dict(
                encode_globals,
                {
                    "source_atom_vectors": timed_source_vectors,
                    "encode_frames": timed_encode_frames,
                }), patch.object(
                    batching, "start_source_backbone_producer",
                    side_effect=timed_start):
        result = profile.main()

    print("ISSUE1566_C05_SOURCE_START_SPLIT " + json.dumps({
        "schema": "bilqis.bamf.issue1566-c05-source-start-split/v1",
        "source_start_seconds": source_start_seconds,
        "source_vector_seconds": source_vector_seconds,
        "frame_encode_seconds": frame_encode_seconds,
        "producer_build_seconds": producer_build_seconds,
        "source_start_total_seconds": sum(source_start_seconds),
        "source_vector_total_seconds": sum(source_vector_seconds),
        "frame_encode_total_seconds": sum(frame_encode_seconds),
        "producer_build_total_seconds": sum(producer_build_seconds),
    }, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
