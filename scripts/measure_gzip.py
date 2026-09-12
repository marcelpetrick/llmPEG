"""Measure what the gzip envelope saves on every checked-in artifact.

Fully offline: it reads the artifacts already in this repository and never calls a model.
Every size is a whole stored file, so the 228-byte format header and gzip's own header and
trailer are charged in every ratio. For comparison it also records what the other
compressors in the Python standard library achieve on the same bytes.

Usage:
    uv run python scripts/measure_gzip.py --output docs/gzip-measurement.json
"""

from __future__ import annotations

import argparse
import bz2
import gzip
import json
import lzma
import sys
from compression import zstd
from pathlib import Path

from llmpeg.artifact import Artifact

REPO = Path(__file__).resolve().parent.parent
ARTIFACT_GLOBS = ("examples/*.llmpeg.json", "survey/artifacts/*.llmpeg.json")


def measure_file(path: Path) -> dict[str, object]:
    """Measure one artifact as stored on disk, plain and inside the gzip envelope."""
    stored = path.read_bytes()
    artifact = Artifact.from_file_bytes(stored)
    if stored != artifact.to_bytes():
        raise SystemExit(f"{path} is not canonical; re-serialize it before measuring")
    packed = artifact.to_gzip_bytes()
    if gzip.decompress(packed) != stored:
        raise SystemExit(f"{path} does not survive a gzip round trip")
    source = artifact.source.byte_size
    return {
        "artifact": path.relative_to(REPO).as_posix(),
        "profile": artifact.profile.value,
        "source_bytes": source,
        "plain_bytes": len(stored),
        "gzip_bytes": len(packed),
        "gzip_fraction": round(len(packed) / len(stored), 3),
        "plain_ratio": round(source / len(stored), 1),
        "gzip_ratio": round(source / len(packed), 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    paths = sorted(path for pattern in ARTIFACT_GLOBS for path in REPO.glob(pattern))
    cases = [measure_file(path) for path in paths]
    blobs = [path.read_bytes() for path in paths]
    source = sum(int(str(case["source_bytes"])) for case in cases)
    plain = sum(len(blob) for blob in blobs)
    packed = sum(int(str(case["gzip_bytes"])) for case in cases)
    report = {
        "method": (
            "Sizes are whole stored files: canonical JSON with its 228-byte header, and the "
            "same bytes in a gzip member written by Artifact.to_gzip_bytes() (level 9, zero "
            "mtime, no file name; 18 bytes of gzip header and trailer). Ratios divide the "
            "recorded source byte size by those file sizes."
        ),
        "artifact_count": len(cases),
        "totals": {
            "source_bytes": source,
            "plain_bytes": plain,
            "gzip_bytes": packed,
            "gzip_fraction": round(packed / plain, 3),
            "plain_ratio": round(source / plain, 1),
            "gzip_ratio": round(source / packed, 1),
        },
        "smallest_gzip_fraction": min(float(str(case["gzip_fraction"])) for case in cases),
        "largest_gzip_fraction": max(float(str(case["gzip_fraction"])) for case in cases),
        "alternatives_total_bytes": {
            "gzip_level_9": packed,
            "bz2_level_9": sum(len(bz2.compress(blob, 9)) for blob in blobs),
            "xz_preset_9_extreme": sum(
                len(lzma.compress(blob, preset=9 | lzma.PRESET_EXTREME)) for blob in blobs
            ),
            "zstd_level_22": sum(len(zstd.compress(blob, level=22)) for blob in blobs),
        },
        "cases": cases,
    }

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
