"""Re-measure an artifact's tone from its verified source and write it as the current format.

Format 1.2 added `tone.colourfulness`. Re-encoding a source to get it would rewrite the whole
description, which changes the render along with the tone and ruins a comparison. This script
keeps every model-written field and only re-measures `tone` from the source pixels, the same step
the encoder performs. It refuses a source whose SHA-256 differs from the one the artifact records.
The header is rewritten for the current release, since this release wrote the new tone.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from PIL import Image

from llmpeg.artifact import Artifact, FormatHeader, source_digest
from llmpeg.encoder import measure_tone


def upgrade(artifact_path: Path, source_path: Path, output_path: Path, overwrite: bool) -> Artifact:
    artifact = Artifact.from_file_bytes(artifact_path.read_bytes())
    content = source_path.read_bytes()
    if source_digest(content) != artifact.source.sha256:
        raise SystemExit(f"{source_path} is not the source recorded in {artifact_path}")
    with Image.open(source_path) as image:
        tone = measure_tone(image)
    upgraded = replace(artifact, header=FormatHeader(), tone=tone)
    upgraded.write(output_path, overwrite=overwrite, compress=True)
    return upgraded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    upgraded = upgrade(args.artifact, args.source, args.output, args.overwrite)
    print(f"wrote {args.output}: tone {upgraded.tone}")


if __name__ == "__main__":
    main()
