"""Independent stdlib AtlasFeatures reference implementation."""
import hashlib
import argparse
import json
import math
from pathlib import Path


FACTOR_DIM = 128
GRAPH_DIM = 64
BROADER = "http://www.w3.org/2004/02/skos/core#broader"
OVERFLOW_IDS = ("urn:type:0510", "urn:type:0511")
COLLISION_TYPES = ("urn:type:collision-016", "urn:type:collision-020")


def _sha(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def _factor(kind: str, identifier: str) -> dict:
    raw = b"".join(
        _sha("bamf.factor.v2|" + kind + "|" + identifier + "|" + str(block))
        for block in range(4)
    )
    return {
        "bytes_hex": raw.hex(),
        "f128": [(byte / 127.5 - 1.0) / math.sqrt(FACTOR_DIM)
                 for byte in raw],
    }


def _graph_signature(direction: str, predicate: str, neighbor: str) -> dict:
    signature = direction + "|" + predicate + "|" + neighbor
    digest = _sha("bamf.graph.v2|" + signature)
    return {
        "signature": signature,
        "sha256": digest.hex(),
        "channel": 8 + int.from_bytes(digest[:8], "little") % 56,
        "sign": 1 if digest[8] & 1 == 0 else -1,
    }


def build_fixture() -> dict:
    disconnected = [0.0] * GRAPH_DIM
    disconnected[4] = math.log1p(1) / math.log(1025)
    collisions = [
        _graph_signature("out", BROADER, identifier)
        for identifier in COLLISION_TYPES
    ]
    return {
        "schema": "bilqis.atlas-feature-reference-fixture/v1",
        "disconnected_graph64": disconnected,
        "overflow": {
            identifier: _factor("type", identifier)
            for identifier in OVERFLOW_IDS
        },
        "collision": {
            "signatures": collisions,
            "combined_channel": collisions[0]["channel"],
            "combined_value": sum(item["sign"] for item in collisions) / 2,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(
        build_fixture(), sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False,
    ) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    else:
        print(payload, end='')


if __name__ == '__main__':
    main()
